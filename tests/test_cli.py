import sys
import os
import json
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from config_loader import load_config
from cli import _build_matchups_and_teams
from constrained_scheduler import assign_days


CONFIGS_DIR = os.path.join(os.path.dirname(__file__), "..", "configs")


def test_load_round_robin_config():
    cfg = load_config(os.path.join(CONFIGS_DIR, "example_round_robin.json"))
    assert cfg.mode == "round_robin"
    assert len(cfg.teams) == 6
    assert cfg.constraints.season_days == 60


def test_load_weighted_config():
    cfg = load_config(os.path.join(CONFIGS_DIR, "example_weighted.json"))
    assert cfg.mode == "weighted"
    assert len(cfg.weighted_teams) == 8
    assert cfg.same_division_games == 4
    assert cfg.cities is not None
    assert "Golden State Warriors" in cfg.cities


def test_load_ipl_config():
    cfg = load_config(os.path.join(CONFIGS_DIR, "example_ipl.json"))
    assert cfg.mode == "ipl"
    assert len(cfg.group_a) == 5
    assert len(cfg.group_b) == 5
    assert cfg.row_pairs["Chennai Super Kings"] == "Mumbai Indians"


def test_round_robin_config_builds_and_solves():
    cfg = load_config(os.path.join(CONFIGS_DIR, "example_round_robin.json"))
    matchups, teams = _build_matchups_and_teams(cfg)
    assert len(teams) == 6
    scheduled = assign_days(matchups, teams, cfg.constraints, time_limit_seconds=30.0)
    assert scheduled is not None


def test_weighted_config_builds_and_solves():
    cfg = load_config(os.path.join(CONFIGS_DIR, "example_weighted.json"))
    matchups, teams = _build_matchups_and_teams(cfg)
    assert len(teams) == 8
    scheduled = assign_days(matchups, teams, cfg.constraints, time_limit_seconds=30.0)
    assert scheduled is not None


def test_ipl_config_builds_and_solves():
    cfg = load_config(os.path.join(CONFIGS_DIR, "example_ipl.json"))
    matchups, teams = _build_matchups_and_teams(cfg)
    assert len(teams) == 10
    assert len(matchups) == 70
    scheduled = assign_days(matchups, teams, cfg.constraints, time_limit_seconds=30.0)
    assert scheduled is not None


def test_unknown_mode_raises():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"mode": "not_a_real_mode", "teams": ["A", "B"]}, f)
        path = f.name
    try:
        raised = False
        try:
            load_config(path)
        except ValueError:
            raised = True
        assert raised, "expected ValueError for unknown mode"
    finally:
        os.remove(path)


def test_load_ipl_calendar_config():
    cfg = load_config(os.path.join(CONFIGS_DIR, "example_ipl_calendar.json"))
    assert cfg.mode == "ipl_calendar"
    assert cfg.calendar_days == 70
    assert cfg.opening_weekday == "Saturday"
    assert cfg.min_rest_hours == 48
    assert cfg.defending_champion == "Chennai Super Kings"


def test_ipl_calendar_config_builds_matchups():
    cfg = load_config(os.path.join(CONFIGS_DIR, "example_ipl_calendar.json"))
    matchups, teams = _build_matchups_and_teams(cfg)
    assert len(teams) == 10
    assert len(matchups) == 70


if __name__ == "__main__":
    test_load_round_robin_config()
    print("test_load_round_robin_config passed")
    test_load_weighted_config()
    print("test_load_weighted_config passed")
    test_load_ipl_config()
    print("test_load_ipl_config passed")
    test_round_robin_config_builds_and_solves()
    print("test_round_robin_config_builds_and_solves passed")
    test_weighted_config_builds_and_solves()
    print("test_weighted_config_builds_and_solves passed")
    test_ipl_config_builds_and_solves()
    print("test_ipl_config_builds_and_solves passed")
    test_unknown_mode_raises()
    print("test_unknown_mode_raises passed")
    test_load_ipl_calendar_config()
    print("test_load_ipl_calendar_config passed")
    test_ipl_calendar_config_builds_matchups()
    print("test_ipl_calendar_config_builds_matchups passed")
    print("\nAll tests passed.")
