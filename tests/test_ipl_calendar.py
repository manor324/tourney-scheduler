"""
Tests for ipl_calendar.py and ipl_calendar_scheduler.py.

The scheduler tests are slow (60-90s each) since they run the real
CP-SAT solve -- that's expected given the added realism, not a bug.
"""

import sys
import os
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ipl_calendar import build_ipl_calendar
from ipl_format import generate_ipl_schedule
from ipl_calendar_scheduler import schedule_ipl_calendar


GROUP_A = ["Chennai Super Kings", "Kolkata Knight Riders", "Rajasthan Royals",
           "Royal Challengers Bengaluru", "Punjab Kings"]
GROUP_B = ["Mumbai Indians", "Sunrisers Hyderabad", "Gujarat Titans",
           "Delhi Capitals", "Lucknow Super Giants"]
ROW_PAIRS = {a: b for a, b in zip(GROUP_A, GROUP_B)}
ALL_TEAMS = GROUP_A + GROUP_B


def test_opening_day_is_single_evening_slot():
    calendar = build_ipl_calendar(season_days=70, opening_weekday="Saturday")
    day0_slots = [s for s in calendar if s.day_number == 0]
    assert len(day0_slots) == 1
    assert day0_slots[0].time_label == "Evening"


def test_weekdays_never_have_two_slots():
    calendar = build_ipl_calendar(season_days=70, opening_weekday="Saturday")
    slots_by_day = defaultdict(list)
    for s in calendar:
        slots_by_day[s.day_number].append(s)
    for day, slots in slots_by_day.items():
        if slots[0].weekday not in ("Saturday", "Sunday"):
            assert len(slots) == 1, f"weekday day {day} has {len(slots)} slots"


def test_sundays_always_have_two_slots():
    calendar = build_ipl_calendar(season_days=70, opening_weekday="Saturday")
    slots_by_day = defaultdict(list)
    for s in calendar:
        slots_by_day[s.day_number].append(s)
    for day, slots in slots_by_day.items():
        if slots[0].weekday == "Sunday":
            assert len(slots) == 2, f"Sunday day {day} has {len(slots)} slots"


def test_saturday_double_headers_taper_off_in_second_half():
    calendar = build_ipl_calendar(season_days=70, opening_weekday="Saturday")
    halfway = 70 // 2
    slots_by_day = defaultdict(list)
    for s in calendar:
        slots_by_day[s.day_number].append(s)
    for day, slots in slots_by_day.items():
        if slots[0].weekday == "Saturday" and day != 0:
            if day < halfway:
                assert len(slots) == 2, f"early Saturday day {day} should be a double-header"
            else:
                assert len(slots) == 1, f"late Saturday day {day} should be single-slot"


def test_invalid_opening_weekday_rejected():
    raised = False
    try:
        build_ipl_calendar(season_days=70, opening_weekday="Monday")
    except ValueError:
        raised = True
    assert raised, "expected ValueError for non-Friday/Saturday opening day"


def test_calendar_scheduler_produces_valid_schedule():
    matchups = generate_ipl_schedule(GROUP_A, GROUP_B, ROW_PAIRS)
    calendar = build_ipl_calendar(season_days=70, opening_weekday="Saturday")

    scheduled = schedule_ipl_calendar(
        matchups, ALL_TEAMS, calendar,
        max_consecutive_away=2, max_consecutive_home=3, min_rest_hours=48,
        defending_champion="Chennai Super Kings",
        time_limit_seconds=120.0,
    )
    assert scheduled is not None, "calendar-aware schedule should be solvable within 120s"

    slot_indices = [g.slot_index for g in scheduled]
    assert len(slot_indices) == len(set(slot_indices))

    opening = [g for g in scheduled if g.slot_index == 0]
    assert len(opening) == 1
    assert opening[0].home == "Chennai Super Kings"
    assert opening[0].day_number == 0
    assert opening[0].time_label == "Evening"

    games_by_team = defaultdict(list)
    for g in scheduled:
        games_by_team[g.home].append(g)
        games_by_team[g.away].append(g)
    for team, games in games_by_team.items():
        days_played = [g.day_number for g in games]
        assert len(days_played) == len(set(days_played)), f"{team} double-booked on a day"

    def minutes(g):
        base = g.day_number * 24 * 60
        return base + (15 * 60 + 30 if g.time_label == "Afternoon" else 19 * 60 + 30)

    for team, games in games_by_team.items():
        games_sorted = sorted(games, key=lambda g: g.slot_index)
        for i in range(len(games_sorted) - 1):
            gap_hours = (minutes(games_sorted[i + 1]) - minutes(games_sorted[i])) / 60
            assert gap_hours >= 48, f"{team} only had {gap_hours:.1f}h rest"

    for team, games in games_by_team.items():
        games_sorted = sorted(games, key=lambda g: g.slot_index)
        away_streak = home_streak = 0
        for g in games_sorted:
            if g.away == team:
                away_streak += 1
                home_streak = 0
            else:
                home_streak += 1
                away_streak = 0
            assert away_streak <= 2
            assert home_streak <= 3

    weekday_slots = defaultdict(set)
    for g in scheduled:
        if g.weekday not in ("Saturday", "Sunday"):
            weekday_slots[g.day_number].add(g.slot_index)
    assert all(len(slots) <= 1 for slots in weekday_slots.values())


if __name__ == "__main__":
    test_opening_day_is_single_evening_slot()
    print("test_opening_day_is_single_evening_slot passed")
    test_weekdays_never_have_two_slots()
    print("test_weekdays_never_have_two_slots passed")
    test_sundays_always_have_two_slots()
    print("test_sundays_always_have_two_slots passed")
    test_saturday_double_headers_taper_off_in_second_half()
    print("test_saturday_double_headers_taper_off_in_second_half passed")
    test_invalid_opening_weekday_rejected()
    print("test_invalid_opening_weekday_rejected passed")

    print("\nRunning slow scheduler test (60-90s expected) ...")
    test_calendar_scheduler_produces_valid_schedule()
    print("test_calendar_scheduler_produces_valid_schedule passed")

    print("\nAll tests passed.")
