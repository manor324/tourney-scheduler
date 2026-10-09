import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from round_robin import generate_round_robin
from constrained_scheduler import assign_days, Constraints
from travel_cost import haversine_distance, total_travel_distance
from optimizer import optimize_schedule, _is_valid_schedule
from team_locations import NBA_TEAM_CITIES


def test_haversine_zero_distance_for_same_point():
    p = (37.7749, -122.4194)
    assert haversine_distance(p, p) < 1e-9


def test_haversine_known_distance_sf_to_nyc():
    sf = (37.7749, -122.4194)
    nyc = (40.7128, -74.0060)
    dist = haversine_distance(sf, nyc)
    assert 4000 < dist < 4300, f"unexpected SF-NYC distance: {dist}"


def _build_sample_schedule():
    teams = [
        "Golden State Warriors",
        "Los Angeles Lakers",
        "Boston Celtics",
        "Chicago Bulls",
    ]
    matchups = generate_round_robin(teams, double_round=True)
    constraints = Constraints(
        season_days=40, max_consecutive_away=2, max_consecutive_home=3, min_rest_days=1
    )
    scheduled = assign_days(matchups, teams, constraints)
    assert scheduled is not None
    return teams, scheduled, constraints


def test_optimizer_preserves_validity():
    teams, scheduled, constraints = _build_sample_schedule()
    optimized, _ = optimize_schedule(
        scheduled, teams, constraints, NBA_TEAM_CITIES, iterations=1000
    )
    assert _is_valid_schedule(optimized, teams, constraints)


def test_optimizer_does_not_increase_travel():
    teams, scheduled, constraints = _build_sample_schedule()
    before = total_travel_distance(scheduled, teams, NBA_TEAM_CITIES)

    optimized, _ = optimize_schedule(
        scheduled, teams, constraints, NBA_TEAM_CITIES, iterations=3000
    )
    after = total_travel_distance(optimized, teams, NBA_TEAM_CITIES)

    assert after <= before


def test_optimizer_preserves_same_set_of_games():
    teams, scheduled, constraints = _build_sample_schedule()
    optimized, _ = optimize_schedule(
        scheduled, teams, constraints, NBA_TEAM_CITIES, iterations=500
    )

    original_pairs = sorted((g.home, g.away) for g in scheduled)
    optimized_pairs = sorted((g.home, g.away) for g in optimized)
    assert original_pairs == optimized_pairs, "optimizer must not add/remove/change matchups"


def test_optimizer_returns_day_sorted_output():
    teams, scheduled, constraints = _build_sample_schedule()
    optimized, _ = optimize_schedule(
        scheduled, teams, constraints, NBA_TEAM_CITIES, iterations=2000
    )
    days = [g.day for g in optimized]
    assert days == sorted(days), "optimizer output should be sorted by day"


if __name__ == "__main__":
    test_haversine_zero_distance_for_same_point()
    print("test_haversine_zero_distance_for_same_point passed")
    test_haversine_known_distance_sf_to_nyc()
    print("test_haversine_known_distance_sf_to_nyc passed")
    test_optimizer_preserves_validity()
    print("test_optimizer_preserves_validity passed")
    test_optimizer_does_not_increase_travel()
    print("test_optimizer_does_not_increase_travel passed")
    test_optimizer_preserves_same_set_of_games()
    print("test_optimizer_preserves_same_set_of_games passed")
    test_optimizer_returns_day_sorted_output()
    print("test_optimizer_returns_day_sorted_output passed")
    print("\nAll tests passed.")
