"""
Accurate IPL-format matchup generator.

The real IPL format (introduced 2022, still in use as of the 2025
season) is NOT a flat "everyone plays everyone the same number of
times" structure -- it has a specific asymmetric rule:

  - 10 teams split into two groups of 5.
  - Each team plays the other 4 teams in its OWN group twice
    (home and away)                                    -> 4 * 2 = 8 games
  - Each team has one designated "row" rival in the OTHER
    group (a fixed pairing, usually by historical seeding)
    and plays them twice too                            -> 1 * 2 = 2 games
  - Each team plays the remaining 4 teams in the other
    group once                                          -> 4 * 1 = 4 games

  Total: 8 + 2 + 4 = 14 games per team, 70 games league-wide.

This is a genuinely different shape from Stage 4's division/conference
model -- it needs a specific PAIRWISE exception (one designated rival),
not just a uniform weight for "everyone in the other group". That's the
same kind of team-specific rotation real NFL scheduling also uses (see
docs/scaling_notes.md and the NFL fact-check earlier in this project) --
worth remembering any time a league's real schedule is being modeled:
check for these exceptions rather than assuming a flat rule.
"""

from dataclasses import dataclass
from typing import List, Dict
from round_robin import Matchup


@dataclass
class IPLTeam:
    name: str
    group: str  # "A" or "B"
    row: int    # position within the group, used to find the row rival


def generate_ipl_schedule(
    group_a: List[str], group_b: List[str], row_pairs: Dict[str, str]
) -> List[Matchup]:
    """
    Generate matchups following the real IPL format.

    Args:
        group_a: 5 team names in Group A.
        group_b: 5 team names in Group B.
        row_pairs: mapping from a Group A team name to its designated
                   Group B "row rival" (the one cross-group team it
                   plays twice instead of once).

    Returns:
        List of Matchup objects: 70 games total for 10 teams (14 each).
    """
    if len(group_a) != 5 or len(group_b) != 5:
        raise ValueError("IPL format expects exactly 5 teams per group.")

    matchups: List[Matchup] = []
    counter = 0

    def add_pair(team_a: str, team_b: str, times: int):
        nonlocal counter
        for game_num in range(times):
            if game_num % 2 == 0:
                home, away = team_a, team_b
            else:
                home, away = team_b, team_a
            counter += 1
            matchups.append(Matchup(round_num=counter, home=home, away=away))

    # Within-group: everyone plays everyone else in their group twice.
    for group in (group_a, group_b):
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                add_pair(group[i], group[j], times=2)

    # Cross-group: row rival plays twice, everyone else once.
    for a_team in group_a:
        row_rival = row_pairs[a_team]
        for b_team in group_b:
            if b_team == row_rival:
                add_pair(a_team, b_team, times=2)
            else:
                add_pair(a_team, b_team, times=1)

    return matchups


def summarize_schedule(teams: List[str], matchups: List[Matchup]) -> None:
    games_played = {t: 0 for t in teams}
    for m in matchups:
        games_played[m.home] += 1
        games_played[m.away] += 1

    print(f"Total games: {len(matchups)}")
    for team, count in games_played.items():
        print(f"  {team:20s} {count} games")


if __name__ == "__main__":
    # Mirrors the real IPL 2025 group structure and row pairings.
    group_a = ["Chennai Super Kings", "Kolkata Knight Riders", "Rajasthan Royals",
               "Royal Challengers Bengaluru", "Punjab Kings"]
    group_b = ["Mumbai Indians", "Sunrisers Hyderabad", "Gujarat Titans",
               "Delhi Capitals", "Lucknow Super Giants"]

    # Row pairing by seed position (1st plays 1st, 2nd plays 2nd, etc.)
    row_pairs = {a: b for a, b in zip(group_a, group_b)}

    matchups = generate_ipl_schedule(group_a, group_b, row_pairs)
    summarize_schedule(group_a + group_b, matchups)
