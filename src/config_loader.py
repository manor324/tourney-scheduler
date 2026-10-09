"""
Config file loading for the CLI.

The config is a single JSON file describing everything needed to run
the pipeline end to end: which matchup-generation mode to use (Stage 1
flat round-robin, Stage 4 weighted conference/division, Stage 5's real
IPL format, or the realistic IPL calendar mode with opening day /
double-header / hour-based-rest rules), the constraints Stage 2 should
enforce, and whether to run Stage 3's travel optimization.

See configs/example_round_robin.json, configs/example_weighted.json,
configs/example_ipl.json, and configs/example_ipl_calendar.json for
real examples of each mode.
"""

import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

from constrained_scheduler import Constraints


@dataclass
class RunConfig:
    mode: str  # "round_robin" | "weighted" | "ipl" | "ipl_calendar"
    constraints: Constraints
    optimize: bool = True
    optimizer_iterations: int = 5000

    # round_robin mode
    teams: Optional[List[str]] = None
    double_round: bool = True

    # weighted mode
    weighted_teams: Optional[List[Dict]] = None  # [{"name","conference","division"}]
    same_division_games: int = 4
    same_conference_games: int = 3
    cross_conference_games: int = 2

    # ipl mode
    group_a: Optional[List[str]] = None
    group_b: Optional[List[str]] = None
    row_pairs: Optional[Dict[str, str]] = None

    # ipl_calendar mode (real IPL format + realistic broadcast calendar)
    calendar_days: int = 70
    opening_weekday: str = "Saturday"
    min_rest_hours: int = 48
    defending_champion: Optional[str] = None

    # optional: team name -> [lat, lon], used for travel optimization.
    # If omitted, optimization is skipped with a warning (no city data
    # to compute travel distance from).
    cities: Optional[Dict[str, Tuple[float, float]]] = None


def parse_config(raw: dict) -> RunConfig:
    """Build a RunConfig from an already-parsed dict (as opposed to a
    file path). Split out from load_config so other code -- like
    nl_to_config.py, which gets JSON back from an LLM rather than a
    file on disk -- can validate a config without writing a temp file
    first."""
    constraints_raw = raw.get("constraints", {})
    constraints = Constraints(
        season_days=constraints_raw.get("season_days", 60),
        max_consecutive_away=constraints_raw.get("max_consecutive_away", 2),
        max_consecutive_home=constraints_raw.get("max_consecutive_home", 3),
        min_rest_days=constraints_raw.get("min_rest_days", 1),
    )

    mode = raw.get("mode")
    if mode not in ("round_robin", "weighted", "ipl", "ipl_calendar"):
        raise ValueError(
            f"Unknown mode '{mode}' in config -- must be 'round_robin', 'weighted', "
            "'ipl', or 'ipl_calendar'."
        )

    cities = None
    if "cities" in raw:
        cities = {name: tuple(coords) for name, coords in raw["cities"].items()}

    cfg = RunConfig(
        mode=mode,
        constraints=constraints,
        optimize=raw.get("optimize", True),
        optimizer_iterations=raw.get("optimizer_iterations", 5000),
        cities=cities,
    )

    if mode == "round_robin":
        if "teams" not in raw:
            raise ValueError("round_robin mode requires a 'teams' list.")
        cfg.teams = raw["teams"]
        cfg.double_round = raw.get("double_round", True)

    elif mode == "weighted":
        if "teams" not in raw:
            raise ValueError("weighted mode requires a 'teams' list of {name,conference,division}.")
        cfg.weighted_teams = raw["teams"]
        for t in cfg.weighted_teams:
            for field_name in ("name", "conference", "division"):
                if field_name not in t:
                    raise ValueError(f"weighted mode team entry missing '{field_name}': {t}")
        rules = raw.get("rules", {})
        cfg.same_division_games = rules.get("same_division_games", 4)
        cfg.same_conference_games = rules.get("same_conference_games", 3)
        cfg.cross_conference_games = rules.get("cross_conference_games", 2)

    elif mode in ("ipl", "ipl_calendar"):
        if "group_a" not in raw or "group_b" not in raw:
            raise ValueError(f"{mode} mode requires 'group_a' and 'group_b' lists of 5 team names each.")
        cfg.group_a = raw["group_a"]
        cfg.group_b = raw["group_b"]
        if len(cfg.group_a) != 5 or len(cfg.group_b) != 5:
            raise ValueError(
                f"{mode} mode requires exactly 5 teams per group "
                f"(got {len(cfg.group_a)} and {len(cfg.group_b)})."
            )
        row_pairs = raw.get("row_pairs")
        if row_pairs is None:
            row_pairs = {a: b for a, b in zip(cfg.group_a, cfg.group_b)}
        cfg.row_pairs = row_pairs

        if mode == "ipl_calendar":
            calendar_raw = raw.get("calendar", {})
            cfg.calendar_days = calendar_raw.get("season_days", 70)
            cfg.opening_weekday = calendar_raw.get("opening_weekday", "Saturday")
            cfg.min_rest_hours = calendar_raw.get("min_rest_hours", 48)
            cfg.defending_champion = calendar_raw.get("defending_champion")

    return cfg


def load_config(path: str) -> RunConfig:
    with open(path, "r") as f:
        raw = json.load(f)
    return parse_config(raw)
