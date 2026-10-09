"""
Builds a realistic IPL-style match calendar: a sequence of SLOTS (not
just days), where a "slot" is one specific broadcast time -- e.g.
"Day 12, 7:30 PM". Some days have one slot, some have two.

Real IPL scheduling rules this encodes:

  - Weekdays (Monday-Friday): exactly 1 evening slot (7:30 PM IST).
    Weekday double-headers are avoided almost entirely.
  - Saturday: 1-2 slots. Early in the tournament, Saturdays are
    double-headers (afternoon 3:30 PM + evening 7:30 PM) just like
    Sundays. Later in the tournament (roughly the back half), Saturday
    double-headers taper off to a single evening game -- workload and
    peak-heat management -- leaving Sunday as the dedicated
    double-header day.
  - Sunday: always 2 slots (3:30 PM + 7:30 PM).
  - Opening day (day 0): always a single evening slot, regardless of
    what weekday it falls on -- the IPL always opens with one
    prime-time match, never a double-header, even if day 0 happens to
    land on a Saturday or Sunday.

This calendar feeds into ipl_calendar_scheduler.py, which assigns each
game to one of these slots (rather than an abstract day number), so
constraints like "no team plays both games of a double-header" and
"48-72 hours rest, in real hours" can be enforced precisely.
"""

from dataclasses import dataclass
from typing import List

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
AFTERNOON_MINUTES = 15 * 60 + 30  # 3:30 PM
EVENING_MINUTES = 19 * 60 + 30    # 7:30 PM


@dataclass
class Slot:
    index: int          # position in the overall slot list -- also the
                         # value the CP-SAT solver assigns to a game
    day_number: int      # 0-indexed day of the season
    weekday: str         # "Monday", ..., "Sunday"
    time_label: str       # "Afternoon" or "Evening"
    minutes_from_start: int  # for computing real rest-hour gaps


def build_ipl_calendar(season_days: int, opening_weekday: str = "Saturday") -> List[Slot]:
    """
    Build the full slot calendar for a season of `season_days` days,
    starting on `opening_weekday` (must be "Friday" or "Saturday" --
    the IPL always opens on one of these two).
    """
    if opening_weekday not in ("Friday", "Saturday"):
        raise ValueError(
            f"IPL opening day must be Friday or Saturday, got '{opening_weekday}'."
        )

    start_idx = WEEKDAY_NAMES.index(opening_weekday)
    halfway_point = season_days // 2

    slots: List[Slot] = []
    slot_index = 0

    for day in range(season_days):
        weekday = WEEKDAY_NAMES[(start_idx + day) % 7]

        if day == 0:
            # Opening day override: always exactly one evening slot,
            # no matter what weekday it lands on.
            day_slots = [("Evening", EVENING_MINUTES)]
        elif weekday == "Sunday":
            day_slots = [("Afternoon", AFTERNOON_MINUTES), ("Evening", EVENING_MINUTES)]
        elif weekday == "Saturday":
            if day < halfway_point:
                # First half of the season: Saturday is a double-header
                # day too.
                day_slots = [("Afternoon", AFTERNOON_MINUTES), ("Evening", EVENING_MINUTES)]
            else:
                # Second half: tapered down to a single evening game.
                day_slots = [("Evening", EVENING_MINUTES)]
        else:
            # Monday-Friday: single evening slot.
            day_slots = [("Evening", EVENING_MINUTES)]

        for time_label, minutes in day_slots:
            slots.append(
                Slot(
                    index=slot_index,
                    day_number=day,
                    weekday=weekday,
                    time_label=time_label,
                    minutes_from_start=day * 24 * 60 + minutes,
                )
            )
            slot_index += 1

    return slots


def summarize_calendar(slots: List[Slot]) -> None:
    total_days = slots[-1].day_number + 1 if slots else 0
    print(f"Season length: {total_days} days")
    print(f"Total slots (max possible matches): {len(slots)}")
    print(f"Opening slot: Day 0, {slots[0].weekday}, {slots[0].time_label}")


if __name__ == "__main__":
    calendar = build_ipl_calendar(season_days=70, opening_weekday="Saturday")
    summarize_calendar(calendar)
    print("\nFirst two weeks:")
    for s in calendar[:20]:
        print(f"  slot {s.index:3d}  day {s.day_number:3d}  {s.weekday:10s} {s.time_label}")
