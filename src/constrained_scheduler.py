"""
Stage 2: Constraint-based day assignment using Google OR-Tools (CP-SAT).

Stage 1 (round_robin.py) tells us WHO plays WHO. This stage decides
WHEN each game happens -- assigning each matchup to a specific day
within the season, subject to real scheduling constraints:

  - A team can't play two games on the same day.
  - A team can't have more than `max_consecutive_away` road games in a row.
  - A team can't have more than `max_consecutive_home` home games in a row.
  - A team needs at least `min_rest_days` between consecutive games.

This is a FEASIBILITY problem: we're not optimizing for anything yet
(like minimizing travel) -- we just want ANY valid day assignment that
satisfies every constraint. That's what CP-SAT is built for: it searches
the space of day assignments using constraint propagation (ruling out
huge chunks of impossible combinations at once) instead of brute force.

Optimization (minimizing travel, balancing rest) is Stage 3.

--- How the "consecutive streak" constraint works ---

A team's games don't have a fixed order until we assign days -- so we
can't directly say "games 3, 4, 5 in a row must include a home game"
because we don't know which games will land next to each other in time
until the solver decides.

The fix: for each team, we compute a RANK for every one of its games,
where rank 0 = earliest game (by day) that season, rank 1 = second
earliest, and so on. Rank is derived FROM the day assignment using
comparison variables (game A is ranked before game B if day_A < day_B).

Once every game has a rank, we know the *order* the team's games happen
in, regardless of what specific calendar days they land on. Then we can
finally ask straightforward questions like "in any 3 consecutive ranks,
is there at least one home game?" -- which is exactly what limits away
streaks.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
from ortools.sat.python import cp_model

from round_robin import Matchup, generate_round_robin


@dataclass
class ScheduledGame:
    day: int
    home: str
    away: str


@dataclass
class Constraints:
    season_days: int
    max_consecutive_away: int = 2
    max_consecutive_home: int = 3
    min_rest_days: int = 0  # 0 means "can play the very next day"


def _add_no_double_booking(model, day_vars, games_by_team):
    """A team can only play one game per day -> all its game-days must differ."""
    for team, game_indices in games_by_team.items():
        model.AddAllDifferent([day_vars[i] for i in game_indices])


def _add_min_rest(model, day_vars, games_by_team, min_rest_days):
    """Any two games for the same team must be at least `gap` days apart."""
    if min_rest_days <= 0:
        return
    gap = min_rest_days + 1
    for team, game_indices in games_by_team.items():
        for a in range(len(game_indices)):
            for b in range(a + 1, len(game_indices)):
                i, j = game_indices[a], game_indices[b]
                i_before_j = model.NewBoolVar(f"rest_order_{i}_{j}")
                model.Add(day_vars[j] - day_vars[i] >= gap).OnlyEnforceIf(i_before_j)
                model.Add(day_vars[i] - day_vars[j] >= gap).OnlyEnforceIf(i_before_j.Not())


def _add_streak_limits(model, day_vars, matchups, games_by_team, max_away, max_home, horizon, min_rest_days):
    """
    For every team, order its games by day (using rank variables), then
    make sure no window of (max_away + 1) consecutive games is all-away,
    and no window of (max_home + 1) consecutive games is all-home.

    NOTE on scaling (Stage 5 investigation): this is O(k^2) helper
    variables per team, where k = games that team plays. We tried
    replacing this with a cheaper calendar-day-window approximation to
    scale better, but it turned out to be WRONG, not just approximate --
    "consecutive away games" is a concept about game ORDER (no home game
    happened in between), not calendar closeness. A team's games can be
    spaced arbitrarily far apart in the calendar, so no fixed-size
    calendar window can correctly detect order-based streaks in general.
    We reverted to this correct-but-quadratic approach. Making this scale
    to full NBA density (76+ games/team) without sacrificing correctness
    is future work -- e.g. only comparing games within a bounded local
    neighborhood instead of every pair, since two games far apart in the
    schedule can never be part of the same streak anyway.
    """
    for team, game_indices in games_by_team.items():
        k = len(game_indices)
        if k <= 1:
            continue

        is_home_const = [
            1 if matchups[i].home == team else 0 for i in game_indices
        ]

        # --- Step 1: pairwise "is game a's day before game b's day" bools ---
        before = {}
        for a in range(k):
            for b in range(k):
                if a == b:
                    continue
                i, j = game_indices[a], game_indices[b]
                key = (a, b)
                if key not in before:
                    bvar = model.NewBoolVar(f"before_{team}_{a}_{b}")
                    model.Add(day_vars[i] < day_vars[j]).OnlyEnforceIf(bvar)
                    model.Add(day_vars[i] > day_vars[j]).OnlyEnforceIf(bvar.Not())
                    before[key] = bvar

        # --- Step 2: rank of each game = how many other games come before it ---
        rank = []
        for a in range(k):
            r = model.NewIntVar(0, k - 1, f"rank_{team}_{a}")
            others_before = [before[(b, a)] for b in range(k) if b != a]
            model.Add(r == sum(others_before))
            rank.append(r)

        # --- Step 3: home_by_rank[r] = 1 if the game at rank r is a home game ---
        home_by_rank = [model.NewBoolVar(f"home_at_rank_{team}_{r}") for r in range(k)]
        for a in range(k):
            for r in range(k):
                at_rank_r = model.NewBoolVar(f"is_rank_{team}_{a}_{r}")
                model.Add(rank[a] == r).OnlyEnforceIf(at_rank_r)
                model.Add(rank[a] != r).OnlyEnforceIf(at_rank_r.Not())
                model.Add(home_by_rank[r] == is_home_const[a]).OnlyEnforceIf(at_rank_r)

        # --- Step 4: sliding window streak limits over the ordered sequence ---
        away_window = max_away + 1
        if k >= away_window:
            for start in range(k - away_window + 1):
                window = home_by_rank[start:start + away_window]
                model.Add(sum(window) >= 1)  # can't be all-away

        home_window = max_home + 1
        if k >= home_window:
            for start in range(k - home_window + 1):
                window = home_by_rank[start:start + home_window]
                model.Add(sum(window) <= home_window - 1)  # can't be all-home


def assign_days(
    matchups: List[Matchup],
    teams: List[str],
    constraints: Constraints,
    time_limit_seconds: float = 30.0,
) -> Optional[List[ScheduledGame]]:
    """
    Given matchups (from Stage 1) and a set of constraints, find a valid
    day (0..season_days-1) for every game. Returns None if no feasible
    assignment is found within the time limit.
    """
    model = cp_model.CpModel()
    num_games = len(matchups)
    horizon = constraints.season_days

    day_vars = [model.NewIntVar(0, horizon - 1, f"day_{i}") for i in range(num_games)]

    games_by_team: Dict[str, List[int]] = {t: [] for t in teams}
    for i, m in enumerate(matchups):
        games_by_team[m.home].append(i)
        games_by_team[m.away].append(i)

    _add_no_double_booking(model, day_vars, games_by_team)
    _add_min_rest(model, day_vars, games_by_team, constraints.min_rest_days)
    _add_streak_limits(
        model, day_vars, matchups, games_by_team,
        constraints.max_consecutive_away, constraints.max_consecutive_home,
        horizon, constraints.min_rest_days,
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    result = [
        ScheduledGame(day=solver.Value(day_vars[i]), home=m.home, away=m.away)
        for i, m in enumerate(matchups)
    ]
    result.sort(key=lambda g: g.day)
    return result


def print_scheduled_games(games: List[ScheduledGame]) -> None:
    for g in games:
        print(f"Day {g.day:3d}: {g.away} @ {g.home}")


if __name__ == "__main__":
    teams = ["Warriors", "Lakers", "Celtics", "Bulls"]
    matchups = generate_round_robin(teams, double_round=True)
    print(f"Generated {len(matchups)} matchups from Stage 1.\n")

    constraints = Constraints(
        season_days=40,
        max_consecutive_away=2,
        max_consecutive_home=3,
        min_rest_days=1,
    )

    scheduled = assign_days(matchups, teams, constraints)

    if scheduled is None:
        print("No feasible schedule found within the time limit.")
    else:
        print_scheduled_games(scheduled)
