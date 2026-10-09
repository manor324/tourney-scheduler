"""
Stage 5 milestone test: verify the full pipeline works correctly at
IPL scale using the ACTUAL IPL format -- 10 teams in two groups of
five, 14 games each via the actual group/row-rival rule -- not a flat
round-robin approximation.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ipl_format import generate_ipl_schedule
from constrained_scheduler import assign_days, Constraints
from optimizer import optimize_schedule, _is_valid_schedule
from travel_cost import total_travel_distance
from team_locations import NBA_TEAM_CITIES


GROUP_A = ["Chennai Super Kings", "Kolkata Knight Riders", "Rajasthan Royals",
           "Royal Challengers Bengaluru", "Punjab Kings"]
GROUP_B = ["Mumbai Indians", "Sunrisers Hyderabad", "Gujarat Titans",
           "Delhi Capitals", "Lucknow Super Giants"]
ROW_PAIRS = {a: b for a, b in zip(GROUP_A, GROUP_B)}
ALL_TEAMS = GROUP_A + GROUP_B


def _setup():
    matchups = generate_ipl_schedule(GROUP_A, GROUP_B, ROW_PAIRS)
    city_lookup = {name: coords for name, coords in zip(ALL_TEAMS, NBA_TEAM_CITIES.values())}
    return matchups, city_lookup


def test_matches_real_ipl_totals():
    matchups, _ = _setup()
    assert len(matchups) == 70

    games_played = {t: 0 for t in ALL_TEAMS}
    for m in matchups:
        games_played[m.home] += 1
        games_played[m.away] += 1
    for team, count in games_played.items():
        assert count == 14, f"{team} played {count}, expected 14"


def test_within_group_pairs_play_twice():
    matchups, _ = _setup()
    pair_counts = {}
    for m in matchups:
        key = frozenset([m.home, m.away])
        pair_counts[key] = pair_counts.get(key, 0) + 1

    for group in (GROUP_A, GROUP_B):
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                key = frozenset([group[i], group[j]])
                assert pair_counts[key] == 2


def test_row_rival_plays_twice_others_once():
    matchups, _ = _setup()
    pair_counts = {}
    for m in matchups:
        key = frozenset([m.home, m.away])
        pair_counts[key] = pair_counts.get(key, 0) + 1

    for a_team, rival in ROW_PAIRS.items():
        assert pair_counts[frozenset([a_team, rival])] == 2
        for b_team in GROUP_B:
            if b_team != rival:
                assert pair_counts[frozenset([a_team, b_team])] == 1


def test_ipl_schedule_solves_and_verifies():
    matchups, city_lookup = _setup()
    constraints = Constraints(
        season_days=60, max_consecutive_away=2, max_consecutive_home=3, min_rest_days=1
    )
    scheduled = assign_days(matchups, ALL_TEAMS, constraints, time_limit_seconds=60.0)
    assert scheduled is not None, "real IPL-format schedule should be solvable well within 60s"

    for team in ALL_TEAMS:
        team_games = sorted(
            [g for g in scheduled if g.home == team or g.away == team], key=lambda g: g.day
        )
        away_streak = home_streak = 0
        for i, g in enumerate(team_games):
            if g.away == team:
                away_streak += 1
                home_streak = 0
            else:
                home_streak += 1
                away_streak = 0
            assert away_streak <= constraints.max_consecutive_away
            assert home_streak <= constraints.max_consecutive_home
            if i > 0:
                gap = g.day - team_games[i - 1].day
                assert gap >= constraints.min_rest_days + 1


def test_ipl_schedule_optimizer_improves_travel():
    matchups, city_lookup = _setup()
    constraints = Constraints(
        season_days=60, max_consecutive_away=2, max_consecutive_home=3, min_rest_days=1
    )
    scheduled = assign_days(matchups, ALL_TEAMS, constraints, time_limit_seconds=60.0)
    assert scheduled is not None

    before = total_travel_distance(scheduled, ALL_TEAMS, city_lookup)
    optimized, _ = optimize_schedule(
        scheduled, ALL_TEAMS, constraints, city_lookup, iterations=3000
    )
    after = total_travel_distance(optimized, ALL_TEAMS, city_lookup)

    assert after <= before
    assert _is_valid_schedule(optimized, ALL_TEAMS, constraints)


if __name__ == "__main__":
    test_matches_real_ipl_totals()
    print("test_matches_real_ipl_totals passed")
    test_within_group_pairs_play_twice()
    print("test_within_group_pairs_play_twice passed")
    test_row_rival_plays_twice_others_once()
    print("test_row_rival_plays_twice_others_once passed")
    test_ipl_schedule_solves_and_verifies()
    print("test_ipl_schedule_solves_and_verifies passed")
    test_ipl_schedule_optimizer_improves_travel()
    print("test_ipl_schedule_optimizer_improves_travel passed")
    print("\nAll tests passed.")
