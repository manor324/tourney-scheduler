import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from round_robin import generate_round_robin
from constrained_scheduler import assign_days, Constraints


def _games_by_team_sorted_by_day(scheduled, team):
    games = [g for g in scheduled if g.home == team or g.away == team]
    games.sort(key=lambda g: g.day)
    return games


def test_no_double_booking():
    teams = ["A", "B", "C", "D"]
    matchups = generate_round_robin(teams, double_round=True)
    scheduled = assign_days(matchups, teams, Constraints(season_days=40))
    assert scheduled is not None

    for team in teams:
        days_used = [g.day for g in scheduled if g.home == team or g.away == team]
        assert len(days_used) == len(set(days_used)), f"{team} double-booked"


def test_min_rest_days_respected():
    teams = ["A", "B", "C", "D"]
    matchups = generate_round_robin(teams, double_round=True)
    min_rest = 2
    scheduled = assign_days(
        matchups, teams, Constraints(season_days=60, min_rest_days=min_rest)
    )
    assert scheduled is not None

    for team in teams:
        games = _games_by_team_sorted_by_day(scheduled, team)
        for i in range(len(games) - 1):
            gap = games[i + 1].day - games[i].day
            assert gap >= min_rest + 1, f"{team} rest violated: gap={gap}"


def test_max_consecutive_away_respected():
    teams = ["A", "B", "C", "D"]
    matchups = generate_round_robin(teams, double_round=True)
    max_away = 2
    scheduled = assign_days(
        matchups, teams, Constraints(season_days=40, max_consecutive_away=max_away)
    )
    assert scheduled is not None

    for team in teams:
        games = _games_by_team_sorted_by_day(scheduled, team)
        streak = 0
        for g in games:
            if g.away == team:
                streak += 1
                assert streak <= max_away, f"{team} exceeded away streak limit"
            else:
                streak = 0


def test_max_consecutive_home_respected():
    teams = ["A", "B", "C", "D"]
    matchups = generate_round_robin(teams, double_round=True)
    max_home = 3
    scheduled = assign_days(
        matchups, teams, Constraints(season_days=40, max_consecutive_home=max_home)
    )
    assert scheduled is not None

    for team in teams:
        games = _games_by_team_sorted_by_day(scheduled, team)
        streak = 0
        for g in games:
            if g.home == team:
                streak += 1
                assert streak <= max_home, f"{team} exceeded home streak limit"
            else:
                streak = 0


def test_infeasible_case_returns_none():
    teams = ["A", "B", "C", "D"]
    matchups = generate_round_robin(teams, double_round=True)
    scheduled = assign_days(
        matchups, teams, Constraints(season_days=3), time_limit_seconds=5.0
    )
    assert scheduled is None


if __name__ == "__main__":
    test_no_double_booking()
    print("test_no_double_booking passed")
    test_min_rest_days_respected()
    print("test_min_rest_days_respected passed")
    test_max_consecutive_away_respected()
    print("test_max_consecutive_away_respected passed")
    test_max_consecutive_home_respected()
    print("test_max_consecutive_home_respected passed")
    test_infeasible_case_returns_none()
    print("test_infeasible_case_returns_none passed")
    print("\nAll tests passed.")
