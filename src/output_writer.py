"""
Write a final schedule (list of ScheduledGame) out to JSON or CSV.
"""

import json
import csv
from typing import List
from constrained_scheduler import ScheduledGame


def write_json(games: List[ScheduledGame], path: str) -> None:
    games = sorted(games, key=lambda g: g.day)
    data = [{"day": g.day, "home": g.home, "away": g.away} for g in games]
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def write_csv(games: List[ScheduledGame], path: str) -> None:
    games = sorted(games, key=lambda g: g.day)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["day", "home", "away"])
        for g in games:
            writer.writerow([g.day, g.home, g.away])


def write_json_calendar(games, path: str) -> None:
    """Output writer for ScheduledMatch (ipl_calendar mode) -- has extra
    fields (day_number, weekday, time_label) that plain ScheduledGame
    doesn't, so it gets its own writer rather than overloading the one
    above."""
    games = sorted(games, key=lambda g: g.slot_index)
    data = [
        {
            "day": g.day_number,
            "weekday": g.weekday,
            "time": g.time_label,
            "home": g.home,
            "away": g.away,
        }
        for g in games
    ]
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def write_csv_calendar(games, path: str) -> None:
    games = sorted(games, key=lambda g: g.slot_index)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["day", "weekday", "time", "home", "away"])
        for g in games:
            writer.writerow([g.day_number, g.weekday, g.time_label, g.home, g.away])
