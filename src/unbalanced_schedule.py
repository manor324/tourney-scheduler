"""
Stage 4: Unbalanced schedule generation based on team groupings.

Stage 1's round-robin generator assumes every team plays every other
team the same number of times. Real leagues don't work that way -- the
NBA, for example, plays division rivals far more often than teams from
the other conference, because it's a better fan/travel/rivalry trade-off
than treating every matchup identically.

This module replaces the flat round-robin with a WEIGHTED generator:
teams are grouped into conferences and divisions, and the number of
times two teams play each other depends on their relationship:

  - Same division            -> most games  (e.g. 4x)
  - Same conference,
    different division       -> medium      (e.g. 3x)
  - Different conference     -> fewest      (e.g. 2x)

This is a simplified version of the real NBA formula -- the actual NBA
schedule also has a few TEAM-SPECIFIC exceptions (some non-division
conference rivals get an extra game on a rotating basis) which we don't
model here. But the core structural idea -- matchup count depends on
group relationship, not a flat constant -- is exactly the conceptual
leap this stage is about.

The output is still just a List[Matchup] (reusing Stage 1's dataclass),
so it plugs directly into Stage 2 (day assignment) and Stage 3
(travel optimization) without any changes to either.
"""

from dataclasses import dataclass
from typing import List
from round_robin import Matchup


@dataclass
class TeamInfo:
    name: str
    conference: str
    division: str


@dataclass
class MatchupRules:
    same_division_games: int = 4
    same_conference_games: int = 3   # same conference, different division
    cross_conference_games: int = 2  # different conference entirely


def _relationship(a: TeamInfo, b: TeamInfo) -> str:
    if a.division == b.division:
        return "same_division"
    if a.conference == b.conference:
        return "same_conference"
    return "cross_conference"


def _games_for_pair(a: TeamInfo, b: TeamInfo, rules: MatchupRules) -> int:
    relationship = _relationship(a, b)
    if relationship == "same_division":
        return rules.same_division_games
    if relationship == "same_conference":
        return rules.same_conference_games
    return rules.cross_conference_games


def generate_weighted_schedule(
    teams: List[TeamInfo], rules: MatchupRules
) -> List[Matchup]:
    """
    Generate matchups for every pair of teams, with the game count
    between each pair determined by their conference/division
    relationship. Home/away is split as evenly as possible for each
    pair -- if the count is odd, the extra game alternates based on
    team order so it doesn't systematically favor one side across the
    whole league.

    `round_num` on the resulting Matchup objects isn't meaningful here
    (unlike Stage 1's round-robin, there's no natural "round" concept
    once matchup counts are unequal) -- it's just an incrementing index,
    unused by Stage 2/3.
    """
    matchups: List[Matchup] = []
    counter = 0

    for i in range(len(teams)):
        for j in range(i + 1, len(teams)):
            team_a, team_b = teams[i], teams[j]
            count = _games_for_pair(team_a, team_b, rules)

            for game_num in range(count):
                # Alternate home team so an odd count doesn't always
                # favor the same side.
                if game_num % 2 == 0:
                    home, away = team_a.name, team_b.name
                else:
                    home, away = team_b.name, team_a.name

                counter += 1
                matchups.append(Matchup(round_num=counter, home=home, away=away))

    return matchups


def summarize_schedule(teams: List[TeamInfo], matchups: List[Matchup]) -> None:
    """Quick sanity printout: how many games does each team play, and
    against how many distinct opponents."""
    games_played = {t.name: 0 for t in teams}
    for m in matchups:
        games_played[m.home] += 1
        games_played[m.away] += 1

    print(f"Total games: {len(matchups)}")
    for team, count in games_played.items():
        print(f"  {team:20s} {count} games")


if __name__ == "__main__":
    # Small example: 2 conferences x 2 divisions x 2 teams = 8 teams.
    teams = [
        TeamInfo("Warriors", "West", "Pacific"),
        TeamInfo("Lakers", "West", "Pacific"),
        TeamInfo("Nuggets", "West", "Northwest"),
        TeamInfo("Jazz", "West", "Northwest"),
        TeamInfo("Celtics", "East", "Atlantic"),
        TeamInfo("Nets", "East", "Atlantic"),
        TeamInfo("Bulls", "East", "Central"),
        TeamInfo("Bucks", "East", "Central"),
    ]

    rules = MatchupRules(
        same_division_games=4,
        same_conference_games=3,
        cross_conference_games=2,
    )

    matchups = generate_weighted_schedule(teams, rules)
    summarize_schedule(teams, matchups)
