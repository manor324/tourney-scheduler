"""
CLI entry point: run the full pipeline from a config file.

Usage:
    python3 cli.py --config ../configs/example_ipl.json --output schedule.json
    python3 cli.py --config ../configs/example_weighted.json --output schedule.csv --format csv
    python3 cli.py --config ../configs/example_ipl_calendar.json --output schedule.json --time-limit 120

This ties together every stage of the project behind one command,
instead of requiring someone to open source files and call functions
directly. See configs/ for example config files covering all four
matchup-generation modes (round_robin, weighted, ipl, ipl_calendar).

Note on ipl_calendar mode: it's noticeably slower (60-90s+, so raise
--time-limit accordingly) since it enforces real broadcast-calendar
rules (opening day, double-headers, hour-based rest) on top of
everything the other modes already do. The CLI auto-defaults to a
larger --time-limit for this mode if you don't pass one explicitly.
"""

import argparse
import sys
import time

from config_loader import load_config
from round_robin import generate_round_robin
from unbalanced_schedule import TeamInfo, MatchupRules, generate_weighted_schedule
from ipl_format import generate_ipl_schedule
from ipl_calendar import build_ipl_calendar
from ipl_calendar_scheduler import schedule_ipl_calendar
from ipl_calendar_optimizer import optimize_ipl_calendar_schedule, calendar_travel_distance
from constrained_scheduler import assign_days
from optimizer import optimize_schedule
from travel_cost import total_travel_distance
from output_writer import write_json, write_csv, write_json_calendar, write_csv_calendar


def _build_matchups_and_teams(cfg):
    if cfg.mode == "round_robin":
        teams = cfg.teams
        matchups = generate_round_robin(teams, double_round=cfg.double_round)
        return matchups, teams

    if cfg.mode == "weighted":
        teams_info = [
            TeamInfo(t["name"], t["conference"], t["division"]) for t in cfg.weighted_teams
        ]
        rules = MatchupRules(
            same_division_games=cfg.same_division_games,
            same_conference_games=cfg.same_conference_games,
            cross_conference_games=cfg.cross_conference_games,
        )
        matchups = generate_weighted_schedule(teams_info, rules)
        teams = [t.name for t in teams_info]
        return matchups, teams

    if cfg.mode in ("ipl", "ipl_calendar"):
        matchups = generate_ipl_schedule(cfg.group_a, cfg.group_b, cfg.row_pairs)
        teams = cfg.group_a + cfg.group_b
        return matchups, teams

    raise ValueError(f"Unknown mode: {cfg.mode}")


def _run_standard_mode(cfg, matchups, teams, args, output_format):
    """round_robin / weighted / ipl modes: Stage 2 solve + optional
    Stage 3 travel optimization, using the plain day-based scheduler."""
    print("Solving for a feasible day assignment (Stage 2) ...")
    start = time.time()
    scheduled = assign_days(matchups, teams, cfg.constraints, time_limit_seconds=args.time_limit)
    elapsed = time.time() - start

    if scheduled is None:
        print(
            f"No feasible schedule found within {args.time_limit:.0f}s. "
            "Try loosening constraints, increasing season_days, or raising --time-limit."
        )
        sys.exit(1)

    print(f"Feasible schedule found in {elapsed:.1f}s.")

    if cfg.optimize:
        if cfg.cities is None:
            print("optimize=true but no 'cities' provided in config -- skipping travel optimization.")
        else:
            missing = [t for t in teams if t not in cfg.cities]
            if missing:
                print(
                    f"Missing city coordinates for {len(missing)} team(s) "
                    f"({', '.join(missing[:3])}{'...' if len(missing) > 3 else ''}) "
                    "-- skipping travel optimization."
                )
            else:
                before = total_travel_distance(scheduled, teams, cfg.cities)
                print(f"Running travel optimization ({cfg.optimizer_iterations} iterations) ...")
                scheduled, _ = optimize_schedule(
                    scheduled, teams, cfg.constraints, cfg.cities,
                    iterations=cfg.optimizer_iterations,
                )
                after = total_travel_distance(scheduled, teams, cfg.cities)
                improvement = (before - after) / before * 100 if before > 0 else 0.0
                print(
                    f"Travel distance: {before:,.0f} km -> {after:,.0f} km "
                    f"({improvement:.1f}% improvement)"
                )

    if output_format == "csv":
        write_csv(scheduled, args.output)
    else:
        write_json(scheduled, args.output)

    print(f"Wrote {len(scheduled)} games to {args.output}")


def _run_ipl_calendar_mode(cfg, matchups, teams, args, output_format):
    """ipl_calendar mode: real broadcast calendar (opening day,
    double-headers, hour-based rest), with a dedicated calendar-aware
    travel optimizer that never breaks those rules."""
    calendar = build_ipl_calendar(
        season_days=cfg.calendar_days, opening_weekday=cfg.opening_weekday
    )
    print(
        f"Calendar: {cfg.calendar_days} days starting {cfg.opening_weekday}, "
        f"{len(calendar)} total slots."
    )
    if cfg.defending_champion:
        print(f"Opening day will feature: {cfg.defending_champion} (home)")

    print(
        "Solving with realistic calendar constraints (this typically takes "
        "60-90+ seconds -- see module docstring) ..."
    )
    start = time.time()
    scheduled = schedule_ipl_calendar(
        matchups, teams, calendar,
        max_consecutive_away=cfg.constraints.max_consecutive_away,
        max_consecutive_home=cfg.constraints.max_consecutive_home,
        min_rest_hours=cfg.min_rest_hours,
        defending_champion=cfg.defending_champion,
        time_limit_seconds=args.time_limit,
    )
    elapsed = time.time() - start

    if scheduled is None:
        print(
            f"No feasible schedule found within {args.time_limit:.0f}s. "
            "Try increasing calendar.season_days, raising --time-limit, or "
            "loosening min_rest_hours / streak constraints."
        )
        sys.exit(1)

    print(f"Feasible schedule found in {elapsed:.1f}s.")

    if cfg.optimize:
        if cfg.cities is None:
            print("optimize=true but no 'cities' provided in config -- skipping travel optimization.")
        else:
            missing = [t for t in teams if t not in cfg.cities]
            if missing:
                print(
                    f"Missing city coordinates for {len(missing)} team(s) "
                    f"({', '.join(missing[:3])}{'...' if len(missing) > 3 else ''}) "
                    "-- skipping travel optimization."
                )
            else:
                before = calendar_travel_distance(scheduled, teams, cfg.cities)
                print(f"Running calendar-aware travel optimization ({cfg.optimizer_iterations} iterations) ...")
                scheduled, _ = optimize_ipl_calendar_schedule(
                    scheduled, teams, calendar, cfg.cities,
                    max_consecutive_away=cfg.constraints.max_consecutive_away,
                    max_consecutive_home=cfg.constraints.max_consecutive_home,
                    min_rest_hours=cfg.min_rest_hours,
                    defending_champion=cfg.defending_champion,
                    iterations=cfg.optimizer_iterations,
                )
                after = calendar_travel_distance(scheduled, teams, cfg.cities)
                improvement = (before - after) / before * 100 if before > 0 else 0.0
                print(
                    f"Travel distance: {before:,.0f} km -> {after:,.0f} km "
                    f"({improvement:.1f}% improvement)"
                )
                if cfg.defending_champion:
                    print("(opening-day game was left untouched during optimization)")

    if output_format == "csv":
        write_csv_calendar(scheduled, args.output)
    else:
        write_json_calendar(scheduled, args.output)

    print(f"Wrote {len(scheduled)} games to {args.output}")


def main():
    parser = argparse.ArgumentParser(description="Tournament scheduler CLI")
    parser.add_argument("--config", required=True, help="Path to a JSON config file")
    parser.add_argument("--output", required=True, help="Path to write the resulting schedule")
    parser.add_argument(
        "--format", choices=["json", "csv"], default=None,
        help="Output format (default: inferred from --output file extension)"
    )
    parser.add_argument(
        "--time-limit", type=float, default=None,
        help="Max seconds for the Stage 2 solver. Default: 60, except "
             "ipl_calendar mode which defaults to 150 since it's noticeably "
             "slower (see docs). Pass explicitly to override either default."
    )
    args = parser.parse_args()

    output_format = args.format
    if output_format is None:
        output_format = "csv" if args.output.lower().endswith(".csv") else "json"

    print(f"Loading config from {args.config} ...")
    cfg = load_config(args.config)

    print(f"Mode: {cfg.mode}")
    matchups, teams = _build_matchups_and_teams(cfg)
    print(f"Generated {len(matchups)} matchups for {len(teams)} teams.")

    if args.time_limit is None:
        # ipl_calendar needs meaningfully more time than the other modes --
        # see the solver-tuning writeup in the README for why (it's not a
        # search-strategy issue, just more interacting constraints).
        args.time_limit = 150.0 if cfg.mode == "ipl_calendar" else 60.0
        print(f"(no --time-limit given, defaulting to {args.time_limit:.0f}s for {cfg.mode} mode)")

    if cfg.mode == "ipl_calendar":
        _run_ipl_calendar_mode(cfg, matchups, teams, args, output_format)
    else:
        _run_standard_mode(cfg, matchups, teams, args, output_format)


if __name__ == "__main__":
    main()
