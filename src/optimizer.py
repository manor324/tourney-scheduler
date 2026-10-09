"""
Stage 3: Optimize a feasible schedule (from Stage 2) to minimize total
travel distance, without breaking any of Stage 2's hard constraints.

Approach: LOCAL SEARCH via SIMULATED ANNEALING.

Stage 2's CP-SAT solver is great at finding *a* schedule that satisfies
every constraint, but it isn't optimizing for anything else once it finds
one. To improve it, we repeatedly:

  1. Pick two games at random and swap their days.
  2. Check the swap still satisfies every hard constraint (no double
     booking, min rest, streak limits). If not, reject it immediately.
  3. If it's valid, check whether it reduces total travel distance.
     - If yes: keep it.
     - If no: usually reject it, but SOMETIMES accept it anyway (this
       is the "annealing" part) -- early on we're more willing to accept
       a worse swap, because that helps us escape local optima (schedules
       that look good but aren't the best possible). As the search
       progresses, we get stricter, until by the end we only accept
       improvements. This mirrors metal annealing: hot metal atoms move
       around freely, and as it cools they settle into a low-energy
       (good) configuration.

This is a heuristic, not an exact optimizer -- it doesn't guarantee the
mathematically best possible schedule, but it reliably finds a much
better one than the first feasible schedule Stage 2 hands back, which is
exactly the trade-off real scheduling systems make at this scale.
"""

import copy
import math
import random
from typing import List, Dict, Tuple

from constrained_scheduler import ScheduledGame, Constraints
from travel_cost import total_travel_distance


def _games_by_team(games: List[ScheduledGame], team: str) -> List[ScheduledGame]:
    return sorted(
        [g for g in games if g.home == team or g.away == team], key=lambda g: g.day
    )


def _team_schedule_is_valid(
    games: List[ScheduledGame], team: str, constraints: Constraints
) -> bool:
    """Check no-double-booking, min-rest, and streak constraints for one team."""
    team_games = _games_by_team(games, team)

    # No double booking.
    days = [g.day for g in team_games]
    if len(days) != len(set(days)):
        return False

    # Minimum rest.
    if constraints.min_rest_days > 0:
        gap_needed = constraints.min_rest_days + 1
        for i in range(len(team_games) - 1):
            if team_games[i + 1].day - team_games[i].day < gap_needed:
                return False

    # Consecutive streak limits (games are already sorted by day, so this
    # is just a straightforward sliding-window check -- no need for the
    # rank-variable trick we needed inside the CP-SAT model).
    away_streak = 0
    home_streak = 0
    for g in team_games:
        if g.away == team:
            away_streak += 1
            home_streak = 0
            if away_streak > constraints.max_consecutive_away:
                return False
        else:
            home_streak += 1
            away_streak = 0
            if home_streak > constraints.max_consecutive_home:
                return False

    return True


def _is_valid_schedule(
    games: List[ScheduledGame], teams: List[str], constraints: Constraints
) -> bool:
    return all(_team_schedule_is_valid(games, team, constraints) for team in teams)


def optimize_schedule(
    games: List[ScheduledGame],
    teams: List[str],
    constraints: Constraints,
    city_lookup: Dict[str, Tuple[float, float]],
    iterations: int = 5000,
    start_temp: float = 50.0,
    seed: int = 42,
) -> Tuple[List[ScheduledGame], List[float]]:
    """
    Run simulated annealing on `games` to reduce total travel distance,
    while never breaking a Stage 2 constraint.

    Returns (optimized_games, cost_history) where cost_history is the
    total travel distance recorded periodically -- useful for plotting
    "did this actually improve things" afterward.
    """
    rng = random.Random(seed)
    current = copy.deepcopy(games)
    current_cost = total_travel_distance(current, teams, city_lookup)

    best = copy.deepcopy(current)
    best_cost = current_cost

    cost_history = [current_cost]

    for step in range(iterations):
        # Temperature decreases over time -> less willing to accept
        # worse swaps as the search progresses.
        temp = start_temp * (1 - step / iterations)
        temp = max(temp, 1e-6)

        i, j = rng.sample(range(len(current)), 2)

        # Try swapping the days of games i and j.
        candidate = copy.deepcopy(current)
        candidate[i].day, candidate[j].day = candidate[j].day, candidate[i].day

        affected_teams = {
            candidate[i].home, candidate[i].away,
            candidate[j].home, candidate[j].away,
        }
        if not all(_team_schedule_is_valid(candidate, t, constraints) for t in affected_teams):
            continue  # invalid swap, skip it

        candidate_cost = total_travel_distance(candidate, teams, city_lookup)
        delta = candidate_cost - current_cost

        if delta < 0:
            accept = True
        else:
            # Accept a worse swap with probability that shrinks as temp
            # cools -- classic simulated annealing acceptance rule.
            accept = rng.random() < math.exp(-delta / temp)

        if accept:
            current = candidate
            current_cost = candidate_cost
            if current_cost < best_cost:
                best = copy.deepcopy(current)
                best_cost = current_cost

        if step % max(1, iterations // 20) == 0:
            cost_history.append(current_cost)

    cost_history.append(best_cost)
    # Sort by day before returning -- swaps during the search change each
    # game's day but don't reorder the underlying list, so without this
    # the returned schedule can come back with days out of order (e.g.
    # day 12, then 34, then 0 ...), which is confusing to read even
    # though the schedule itself is perfectly valid.
    best.sort(key=lambda g: g.day)
    return best, cost_history
