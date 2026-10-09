import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from unbalanced_schedule import TeamInfo, MatchupRules, generate_weighted_schedule
from constrained_scheduler import assign_days, Constraints
from optimizer import optimize_schedule, _is_valid_schedule
from travel_cost import total_travel_distance
from team_locations import NBA_TEAM_CITIES


def _sample_teams():
    return [
        TeamInfo("Golden State Warriors", "West", "Pacific"),
        TeamInfo("Los Angeles Lakers", "West", "Pacific"),
        TeamInfo("Denver Nuggets", "West", "Northwest"),
        TeamInfo("Utah Jazz", "West", "Northwest"),
        TeamInfo("Boston Celtics", "East", "Atlantic"),
        TeamInfo("Brooklyn Nets", "East", "Atlantic"),
        TeamInfo("Chicago Bulls", "East", "Central"),
        TeamInfo("Milwaukee Bucks", "East", "Central"),
    ]


def test_division_rivals_play_most():
    teams = _sample_teams()
    rules = MatchupRules(same_division_games=4, same_conference_games=3, cross_conference_games=2)
    matchups = generate_weighted_schedule(teams, rules)

    pair_counts = {}
    for m in matchups:
        key = frozenset([m.home, m.away])
        pair_counts[key] = pair_counts.get(key, 0) + 1

    warriors_lakers = frozenset(["Golden State Warriors", "Los Angeles Lakers"])
    assert pair_counts[warriors_lakers] == 4

    warriors_nuggets = frozenset(["Golden State Warriors", "Denver Nuggets"])
    assert pair_counts[warriors_nuggets] == 3

    warriors_celtics = frozenset(["Golden State Warriors", "Boston Celtics"])
    assert pair_counts[warriors_celtics] == 2


def test_total_games_matches_expected_formula():
    teams = _sample_teams()
    rules = MatchupRules(same_division_games=4, same_conference_games=3, cross_conference_games=2)
    matchups = generate_weighted_schedule(teams, rules)

    expected_total = 16 + 24 + 32
    assert len(matchups) == expected_total


def test_each_team_plays_expected_game_count():
    teams = _sample_teams()
    rules = MatchupRules(same_division_games=4, same_conference_games=3, cross_conference_games=2)
    matchups = generate_weighted_schedule(teams, rules)

    games_played = {t.name: 0 for t in teams}
    for m in matchups:
        games_played[m.home] += 1
        games_played[m.away] += 1

    expected = 4 + (2 * 3) + (4 * 2)
    for team, count in games_played.items():
        assert count == expected, f"{team} played {count}, expected {expected}"


def test_no_team_plays_itself():
    teams = _sample_teams()
    rules = MatchupRules()
    matchups = generate_weighted_schedule(teams, rules)
    for m in matchups:
        assert m.home != m.away


def test_plugs_into_stage2_and_stage3():
    teams_info = _sample_teams()
    team_names = [t.name for t in teams_info]
    rules = MatchupRules(same_division_games=2, same_conference_games=2, cross_conference_games=1)
    matchups = generate_weighted_schedule(teams_info, rules)

    constraints = Constraints(
        season_days=60, max_consecutive_away=2, max_consecutive_home=3, min_rest_days=1
    )
    scheduled = assign_days(matchups, team_names, constraints, time_limit_seconds=15.0)
    assert scheduled is not None, "Stage 2 should find a feasible schedule for Stage 4 output"

    optimized, _ = optimize_schedule(
        scheduled, team_names, constraints, NBA_TEAM_CITIES, iterations=1000
    )
    assert _is_valid_schedule(optimized, team_names, constraints)

    before = total_travel_distance(scheduled, team_names, NBA_TEAM_CITIES)
    after = total_travel_distance(optimized, team_names, NBA_TEAM_CITIES)
    assert after <= before


if __name__ == "__main__":
    test_division_rivals_play_most()
    print("test_division_rivals_play_most passed")
    test_total_games_matches_expected_formula()
    print("test_total_games_matches_expected_formula passed")
    test_each_team_plays_expected_game_count()
    print("test_each_team_plays_expected_game_count passed")
    test_no_team_plays_itself()
    print("test_no_team_plays_itself passed")
    test_plugs_into_stage2_and_stage3()
    print("test_plugs_into_stage2_and_stage3 passed")
    print("\nAll tests passed.")
