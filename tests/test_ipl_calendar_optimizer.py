"""
Tests for ipl_calendar_optimizer.py. Like test_ipl_calendar.py, the main
test here is slow (includes a real ~60-90s CP-SAT solve for Stage 2
before optimizing) -- that's expected, not a bug.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ipl_format import generate_ipl_schedule
from ipl_calendar import build_ipl_calendar
from ipl_calendar_scheduler import schedule_ipl_calendar
from ipl_calendar_optimizer import (
    optimize_ipl_calendar_schedule, is_valid_calendar_schedule, calendar_travel_distance,
)


GROUP_A = ["Chennai Super Kings", "Kolkata Knight Riders", "Rajasthan Royals",
           "Royal Challengers Bengaluru", "Punjab Kings"]
GROUP_B = ["Mumbai Indians", "Sunrisers Hyderabad", "Gujarat Titans",
           "Delhi Capitals", "Lucknow Super Giants"]
ROW_PAIRS = {a: b for a, b in zip(GROUP_A, GROUP_B)}
ALL_TEAMS = GROUP_A + GROUP_B

CITY_LOOKUP = {
    "Chennai Super Kings": (13.0827, 80.2707),
    "Kolkata Knight Riders": (22.5726, 88.3639),
    "Rajasthan Royals": (26.9124, 75.7873),
    "Royal Challengers Bengaluru": (12.9716, 77.5946),
    "Punjab Kings": (30.7046, 76.7179),
    "Mumbai Indians": (19.0760, 72.8777),
    "Sunrisers Hyderabad": (17.3850, 78.4867),
    "Gujarat Titans": (23.0225, 72.5714),
    "Delhi Capitals": (28.7041, 77.1025),
    "Lucknow Super Giants": (26.8467, 80.9462),
}


def test_optimizer_preserves_opening_day_and_all_constraints():
    matchups = generate_ipl_schedule(GROUP_A, GROUP_B, ROW_PAIRS)
    calendar = build_ipl_calendar(season_days=70, opening_weekday="Saturday")

    scheduled = schedule_ipl_calendar(
        matchups, ALL_TEAMS, calendar,
        max_consecutive_away=2, max_consecutive_home=3, min_rest_hours=48,
        defending_champion="Chennai Super Kings", time_limit_seconds=150.0,
    )
    assert scheduled is not None

    opening_before = [g for g in scheduled if g.slot_index == 0][0]
    assert opening_before.home == "Chennai Super Kings"

    before_cost = calendar_travel_distance(scheduled, ALL_TEAMS, CITY_LOOKUP)

    optimized, _ = optimize_ipl_calendar_schedule(
        scheduled, ALL_TEAMS, calendar, CITY_LOOKUP,
        max_consecutive_away=2, max_consecutive_home=3, min_rest_hours=48,
        defending_champion="Chennai Super Kings", iterations=4000,
    )

    opening_after = [g for g in optimized if g.slot_index == 0][0]
    assert opening_after.home == "Chennai Super Kings"
    assert opening_after.away == opening_before.away

    assert is_valid_calendar_schedule(optimized, ALL_TEAMS, 2, 3, 48)

    after_cost = calendar_travel_distance(optimized, ALL_TEAMS, CITY_LOOKUP)
    assert after_cost <= before_cost

    before_pairs = sorted((g.home, g.away) for g in scheduled)
    after_pairs = sorted((g.home, g.away) for g in optimized)
    assert before_pairs == after_pairs


if __name__ == "__main__":
    print("Running slow calendar-optimizer test (Stage 2 solve + optimization, ~60-90s) ...")
    test_optimizer_preserves_opening_day_and_all_constraints()
    print("test_optimizer_preserves_opening_day_and_all_constraints passed")
    print("\nAll tests passed.")
