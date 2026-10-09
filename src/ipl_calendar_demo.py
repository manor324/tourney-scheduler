"""
Demo: run the real IPL matchup format (Stage 5) through the new
calendar-aware scheduler -- opening day, double-header rules, and
hour-based rest, on top of everything Stage 2 already enforces.

Note on solve time: this is noticeably slower than the plain IPL demo
(ipl_scale_demo.py, ~2-3s) -- typically 60-90 seconds. The added realism
(hour-based rest via AddElement, double-header conflict logic across
every team/day pair, global slot uniqueness) costs real solver
performance. Still fast enough to run once for a demo; not fast enough
to call repeatedly in a tight loop without a longer time budget.
"""

import time

from ipl_format import generate_ipl_schedule
from ipl_calendar import build_ipl_calendar, summarize_calendar
from ipl_calendar_scheduler import schedule_ipl_calendar, print_schedule


GROUP_A = ["Chennai Super Kings", "Kolkata Knight Riders", "Rajasthan Royals",
           "Royal Challengers Bengaluru", "Punjab Kings"]
GROUP_B = ["Mumbai Indians", "Sunrisers Hyderabad", "Gujarat Titans",
           "Delhi Capitals", "Lucknow Super Giants"]
ROW_PAIRS = {a: b for a, b in zip(GROUP_A, GROUP_B)}
ALL_TEAMS = GROUP_A + GROUP_B


def main():
    matchups = generate_ipl_schedule(GROUP_A, GROUP_B, ROW_PAIRS)
    print(f"Generated {len(matchups)} matchups for {len(ALL_TEAMS)} teams.\n")

    calendar = build_ipl_calendar(season_days=70, opening_weekday="Saturday")
    summarize_calendar(calendar)
    print()

    print("Solving (this typically takes 60-90 seconds -- see module docstring) ...")
    start = time.time()
    scheduled = schedule_ipl_calendar(
        matchups, ALL_TEAMS, calendar,
        max_consecutive_away=2, max_consecutive_home=3, min_rest_hours=48,
        defending_champion="Chennai Super Kings",
        time_limit_seconds=120.0,
    )
    elapsed = time.time() - start

    if scheduled is None:
        print(f"FAILED to find a feasible schedule in {elapsed:.1f}s.")
        return

    print(f"Solved in {elapsed:.1f}s.\n")

    print("Opening match:")
    print_schedule(scheduled[:1])

    print("\nFirst two weeks:")
    print_schedule([g for g in scheduled if g.day_number < 14])


if __name__ == "__main__":
    main()
