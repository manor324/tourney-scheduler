import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from round_robin import generate_round_robin


def test_every_pair_plays_twice_in_double_round():
    teams = ["A", "B", "C", "D"]
    schedule = generate_round_robin(teams, double_round=True)

    pair_counts = {}
    for m in schedule:
        key = frozenset([m.home, m.away])
        pair_counts[key] = pair_counts.get(key, 0) + 1

    assert len(pair_counts) == 6
    assert all(count == 2 for count in pair_counts.values())


def test_no_team_plays_itself():
    teams = ["A", "B", "C", "D", "E"]
    schedule = generate_round_robin(teams, double_round=True)
    for m in schedule:
        assert m.home != m.away


def test_odd_number_of_teams_handles_bye():
    teams = ["A", "B", "C"]
    schedule = generate_round_robin(teams, double_round=False)
    assert len(schedule) == 3


def test_total_game_count_single_round():
    teams = ["A", "B", "C", "D", "E", "F"]
    schedule = generate_round_robin(teams, double_round=False)
    assert len(schedule) == 15


def test_total_game_count_double_round():
    teams = ["A", "B", "C", "D", "E", "F"]
    schedule = generate_round_robin(teams, double_round=True)
    assert len(schedule) == 30


if __name__ == "__main__":
    test_every_pair_plays_twice_in_double_round()
    test_no_team_plays_itself()
    test_odd_number_of_teams_handles_bye()
    test_total_game_count_single_round()
    test_total_game_count_double_round()
    print("All tests passed.")
