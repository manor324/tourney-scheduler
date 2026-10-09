"""
Calendar-aware IPL scheduling: assigns each game to a real SLOT (a
specific day + time), rather than an abstract day number, and enforces
IPL's real scheduling rules on top of everything Stage 2 already does:

  - Opening day: a single evening match, day 0, ideally the defending
    champion playing at home.
  - Double-headers happen on Saturdays (early season) and Sundays, with
    an afternoon (3:30 PM) and evening (7:30 PM) slot -- never on
    weekdays.
  - A team can't play in both slots of a double-header day.
  - Minimum rest is enforced in real HOURS (e.g. 48-72h), not just
    "days apart" -- because slots aren't evenly spaced in time (a
    Saturday evening to Monday evening gap is 48 hours; a Sunday
    afternoon to Sunday evening gap is only ~4 hours).
  - Each physical slot can host at most one match, across ALL teams --
    this is a new constraint Stage 2 didn't need, because Stage 2's
    abstract "days" had no cap on how many games could share a day.

This builds on top of constrained_scheduler.py: streak-limit logic
(_add_streak_limits) is reused unchanged, because it only compares slot
indices with < and > -- and since the calendar is built in chronological
order, slot index order IS real time order, so the comparison stays
correct without any changes.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
from collections import defaultdict
from ortools.sat.python import cp_model

from round_robin import Matchup
from ipl_calendar import Slot
from constrained_scheduler import _add_streak_limits


@dataclass
class ScheduledMatch:
    slot_index: int
    day_number: int
    weekday: str
    time_label: str
    home: str
    away: str


def _add_global_slot_uniqueness(model, slot_vars):
    """Each physical slot hosts at most one match, across every team --
    unlike Stage 2's abstract days, a slot here is a specific real
    broadcast time, so two different games can never share one."""
    model.AddAllDifferent(slot_vars)


def _add_no_double_header_conflict(model, slot_vars, games_by_team, calendar):
    """A team can't play in both slots of the same double-header day."""
    slots_by_day: Dict[int, List[int]] = defaultdict(list)
    for s in calendar:
        slots_by_day[s.day_number].append(s.index)

    multi_slot_days = {day: idxs for day, idxs in slots_by_day.items() if len(idxs) > 1}

    for team, game_indices in games_by_team.items():
        for day, slot_indices_for_day in multi_slot_days.items():
            indicators = []
            for i in game_indices:
                in_day = model.NewBoolVar(f"team_{team}_g{i}_day{day}")
                # in_day == True iff this game's slot is one of the two
                # slots on this double-header day.
                member_bools = []
                for s in slot_indices_for_day:
                    b = model.NewBoolVar(f"g{i}_slot{s}")
                    model.Add(slot_vars[i] == s).OnlyEnforceIf(b)
                    model.Add(slot_vars[i] != s).OnlyEnforceIf(b.Not())
                    member_bools.append(b)
                model.AddMaxEquality(in_day, member_bools)
                indicators.append(in_day)
            model.Add(sum(indicators) <= 1)


def _add_hour_based_rest(model, slot_vars, games_by_team, calendar, min_rest_hours):
    """Minimum rest enforced in real hours, using each slot's actual
    time-from-season-start rather than assuming evenly spaced days."""
    minutes_lookup = [s.minutes_from_start for s in calendar]
    min_rest_minutes = min_rest_hours * 60

    minutes_vars = {}
    for i in range(len(slot_vars)):
        mv = model.NewIntVar(0, max(minutes_lookup), f"minutes_{i}")
        model.AddElement(slot_vars[i], minutes_lookup, mv)
        minutes_vars[i] = mv

    for team, game_indices in games_by_team.items():
        for a in range(len(game_indices)):
            for b in range(a + 1, len(game_indices)):
                i, j = game_indices[a], game_indices[b]
                i_before_j = model.NewBoolVar(f"rest_order_{team}_{i}_{j}")
                model.Add(
                    minutes_vars[j] - minutes_vars[i] >= min_rest_minutes
                ).OnlyEnforceIf(i_before_j)
                model.Add(
                    minutes_vars[i] - minutes_vars[j] >= min_rest_minutes
                ).OnlyEnforceIf(i_before_j.Not())


def _add_opening_day_constraint(model, slot_vars, matchups, defending_champion):
    """Slot 0 (the single opening-day evening match) must be a home
    game for the defending champion."""
    candidate_indicators = []
    for i, m in enumerate(matchups):
        if m.home == defending_champion:
            b = model.NewBoolVar(f"opening_candidate_{i}")
            model.Add(slot_vars[i] == 0).OnlyEnforceIf(b)
            model.Add(slot_vars[i] != 0).OnlyEnforceIf(b.Not())
            candidate_indicators.append(b)

    if not candidate_indicators:
        raise ValueError(
            f"'{defending_champion}' has no home game in the matchup list -- "
            "can't schedule them as the opening-day home team."
        )

    # Exactly one of the champion's home games occupies slot 0. Combined
    # with global slot uniqueness (each slot used by at most one game),
    # this also guarantees no OTHER team's game can land on slot 0.
    model.Add(sum(candidate_indicators) == 1)


def schedule_ipl_calendar(
    matchups: List[Matchup],
    teams: List[str],
    calendar: List[Slot],
    max_consecutive_away: int = 2,
    max_consecutive_home: int = 3,
    min_rest_hours: int = 48,
    defending_champion: Optional[str] = None,
    time_limit_seconds: float = 60.0,
) -> Optional[List[ScheduledMatch]]:
    """
    Assign every matchup to a real calendar slot, respecting:
      - global slot uniqueness (one match per slot)
      - no double-slot conflicts for any team on double-header days
      - streak limits (max consecutive home/away)
      - minimum rest, enforced in real hours
      - optional opening-day rule (defending champion hosts slot 0)

    Returns None if no feasible assignment is found within the time limit.
    """
    if len(matchups) > len(calendar):
        raise ValueError(
            f"{len(matchups)} games don't fit in a calendar with only "
            f"{len(calendar)} slots -- extend season_days."
        )

    model = cp_model.CpModel()
    num_games = len(matchups)
    max_slot = len(calendar) - 1

    slot_vars = [model.NewIntVar(0, max_slot, f"slot_{i}") for i in range(num_games)]

    games_by_team: Dict[str, List[int]] = {t: [] for t in teams}
    for i, m in enumerate(matchups):
        games_by_team[m.home].append(i)
        games_by_team[m.away].append(i)

    _add_global_slot_uniqueness(model, slot_vars)
    _add_no_double_header_conflict(model, slot_vars, games_by_team, calendar)
    _add_hour_based_rest(model, slot_vars, games_by_team, calendar, min_rest_hours)
    _add_streak_limits(
        model, slot_vars, matchups, games_by_team,
        max_consecutive_away, max_consecutive_home,
        horizon=len(calendar), min_rest_days=0,  # unused by rank-based logic; kept for signature compatibility
    )
    if defending_champion is not None:
        _add_opening_day_constraint(model, slot_vars, matchups, defending_champion)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    slot_by_index = {s.index: s for s in calendar}
    result = []
    for i, m in enumerate(matchups):
        s = slot_by_index[solver.Value(slot_vars[i])]
        result.append(
            ScheduledMatch(
                slot_index=s.index, day_number=s.day_number, weekday=s.weekday,
                time_label=s.time_label, home=m.home, away=m.away,
            )
        )
    result.sort(key=lambda g: g.slot_index)
    return result


def print_schedule(games: List[ScheduledMatch]) -> None:
    for g in games:
        print(f"Day {g.day_number:3d} {g.weekday:9s} {g.time_label:9s}  {g.away} @ {g.home}")
