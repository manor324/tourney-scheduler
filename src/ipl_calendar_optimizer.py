"""
Travel optimization for ipl_calendar mode.

This can't just reuse optimizer.py as-is: that optimizer swaps two
games' `.day` values freely, which would silently break calendar-aware
rules that don't exist in the plain Stage 2/3 model --

  - Swapping the opening-day game (slot 0) would knock the defending
    champion off the opening slot.
  - Swapping days without checking calendar structure could put a team
    in both slots of a double-header day.
  - Rest needs to be checked in real HOURS using each slot's actual
    time, not a flat "days apart" assumption.

So this is the same simulated-annealing approach as optimizer.py --
pick two games, swap them, keep the swap if it's valid and doesn't
increase travel, sometimes accept a worse swap early on to escape local
optima -- but the validity check and the "what can be swapped" rules
are calendar-aware, and the opening-day game (slot 0) is never touched.
"""

import copy
import math
import random
from typing import List, Dict, Tuple, Optional

from ipl_calendar import Slot
from ipl_calendar_scheduler import ScheduledMatch
from travel_cost import total_travel_distance


class _DaySurrogate:
    """Thin wrapper so travel_cost.total_travel_distance (which expects
    objects with .day/.home/.away) can work on ScheduledMatch objects
    without duplicating the travel-distance logic. slot_index is used
    as the sort key -- it's already in chronological order by
    construction, so this is a safe stand-in for "day"."""
    __slots__ = ("day", "home", "away")

    def __init__(self, match: ScheduledMatch):
        self.day = match.slot_index
        self.home = match.home
        self.away = match.away


def _travel_distance(games: List[ScheduledMatch], teams, city_lookup) -> float:
    return total_travel_distance([_DaySurrogate(g) for g in games], teams, city_lookup)


def calendar_travel_distance(games: List[ScheduledMatch], teams, city_lookup) -> float:
    """Public entry point for computing total travel distance on a
    ScheduledMatch list (e.g. from the CLI, before/after optimizing)."""
    return _travel_distance(games, teams, city_lookup)


def _refresh_from_slot(match: ScheduledMatch, slot_by_index: Dict[int, Slot]) -> None:
    """After changing match.slot_index, keep day_number/weekday/time_label
    consistent with the new slot -- these are derived fields, not
    independent state."""
    s = slot_by_index[match.slot_index]
    match.day_number = s.day_number
    match.weekday = s.weekday
    match.time_label = s.time_label


def _team_games(games: List[ScheduledMatch], team: str) -> List[ScheduledMatch]:
    return sorted(
        [g for g in games if g.home == team or g.away == team], key=lambda g: g.slot_index
    )


def _team_calendar_schedule_is_valid(
    games: List[ScheduledMatch], team: str,
    max_consecutive_away: int, max_consecutive_home: int, min_rest_hours: int,
) -> bool:
    team_games = _team_games(games, team)

    # No double-header conflict: no two games on the same calendar day.
    days = [g.day_number for g in team_games]
    if len(days) != len(set(days)):
        return False

    # Hour-based rest.
    def minutes(g):
        base = g.day_number * 24 * 60
        return base + (15 * 60 + 30 if g.time_label == "Afternoon" else 19 * 60 + 30)

    min_rest_minutes = min_rest_hours * 60
    for i in range(len(team_games) - 1):
        if minutes(team_games[i + 1]) - minutes(team_games[i]) < min_rest_minutes:
            return False

    # Streak limits.
    away_streak = home_streak = 0
    for g in team_games:
        if g.away == team:
            away_streak += 1
            home_streak = 0
            if away_streak > max_consecutive_away:
                return False
        else:
            home_streak += 1
            away_streak = 0
            if home_streak > max_consecutive_home:
                return False

    return True


def is_valid_calendar_schedule(games, teams, max_away, max_home, min_rest_hours) -> bool:
    return all(
        _team_calendar_schedule_is_valid(games, t, max_away, max_home, min_rest_hours)
        for t in teams
    )


def optimize_ipl_calendar_schedule(
    games: List[ScheduledMatch],
    teams: List[str],
    calendar: List[Slot],
    city_lookup: Dict[str, Tuple[float, float]],
    max_consecutive_away: int = 2,
    max_consecutive_home: int = 3,
    min_rest_hours: int = 48,
    defending_champion: Optional[str] = None,
    iterations: int = 4000,
    start_temp: float = 60.0,
    seed: int = 42,
) -> Tuple[List[ScheduledMatch], List[float]]:
    """
    Simulated annealing over a feasible ipl_calendar schedule, minimizing
    total travel distance without ever breaking a calendar-aware
    constraint (double-header conflicts, hour-based rest, streak limits)
    or moving the opening-day game off slot 0.
    """
    slot_by_index = {s.index: s for s in calendar}
    rng = random.Random(seed)

    current = copy.deepcopy(games)
    current_cost = _travel_distance(current, teams, city_lookup)

    best = copy.deepcopy(current)
    best_cost = current_cost

    cost_history = [current_cost]

    # The opening-day game (slot 0) is never touched, if there is one --
    # swapping it would knock the defending champion off the opening slot.
    swappable_indices = [
        i for i, g in enumerate(current) if g.slot_index != 0
    ] if defending_champion else list(range(len(current)))

    if len(swappable_indices) < 2:
        return best, cost_history

    for step in range(iterations):
        temp = max(start_temp * (1 - step / iterations), 1e-6)

        i, j = rng.sample(swappable_indices, 2)

        candidate = copy.deepcopy(current)
        candidate[i].slot_index, candidate[j].slot_index = (
            candidate[j].slot_index, candidate[i].slot_index,
        )
        _refresh_from_slot(candidate[i], slot_by_index)
        _refresh_from_slot(candidate[j], slot_by_index)

        affected_teams = {
            candidate[i].home, candidate[i].away,
            candidate[j].home, candidate[j].away,
        }
        if not all(
            _team_calendar_schedule_is_valid(
                candidate, t, max_consecutive_away, max_consecutive_home, min_rest_hours
            )
            for t in affected_teams
        ):
            continue

        candidate_cost = _travel_distance(candidate, teams, city_lookup)
        delta = candidate_cost - current_cost

        accept = delta < 0 or rng.random() < math.exp(-delta / temp)
        if accept:
            current = candidate
            current_cost = candidate_cost
            if current_cost < best_cost:
                best = copy.deepcopy(current)
                best_cost = current_cost

        if step % max(1, iterations // 20) == 0:
            cost_history.append(current_cost)

    cost_history.append(best_cost)
    best.sort(key=lambda g: g.slot_index)
    return best, cost_history
