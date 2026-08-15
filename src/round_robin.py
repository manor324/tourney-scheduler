"""
Round-robin schedule generator using the "circle method".

Given a list of teams, produces a schedule where every team plays every
other team exactly once per "leg". Two legs (double round-robin) gives
a home-and-away schedule, like most real leagues use.

This is Stage 1 of the tournament scheduler: it only produces the raw
matchup skeleton (who plays who, on which "round"). Constraints like
max consecutive away games, road trip lengths, and rest days are NOT
handled here -- that's Stage 2 (constraint programming with OR-Tools).
"""

from dataclasses import dataclass
from typing import List


@dataclass
class Matchup:
    round_num: int
    home: str
    away: str


def generate_round_robin(teams: List[str], double_round: bool = True) -> List[Matchup]:
    """
    Generate a round-robin schedule for the given teams using the circle method.

    Args:
        teams: list of team names/ids. If odd, a "BYE" placeholder is added.
        double_round: if True, mirror the schedule with home/away swapped
                      (so every pair plays twice -- once at each venue).

    Returns:
        List of Matchup objects, each tagged with the round number they
        belong to. Rounds are 1-indexed.
    """
    if len(teams) < 2:
        raise ValueError("Need at least 2 teams to schedule a round robin.")

    working_teams = list(teams)
    has_bye = len(working_teams) % 2 == 1
    if has_bye:
        working_teams.append("BYE")

    n = len(working_teams)
    num_rounds = n - 1
    half = n // 2

    schedule: List[Matchup] = []

    # Circle method: fix the first team, rotate the rest.
    rotation = working_teams[1:]

    for round_num in range(1, num_rounds + 1):
        round_teams = [working_teams[0]] + rotation

        for i in range(half):
            t1 = round_teams[i]
            t2 = round_teams[n - 1 - i]

            if t1 == "BYE" or t2 == "BYE":
                continue

            # Alternate home/away by round parity so nobody is always
            # stuck at home or always on the road for a given slot.
            if round_num % 2 == 1:
                home, away = t1, t2
            else:
                home, away = t2, t1

            schedule.append(Matchup(round_num=round_num, home=home, away=away))

        # Rotate: last element moves to front of the rotating block.
        rotation = [rotation[-1]] + rotation[:-1]

    if double_round:
        mirrored = []
        for m in schedule:
            mirrored.append(
                Matchup(round_num=m.round_num + num_rounds, home=m.away, away=m.home)
            )
        schedule.extend(mirrored)

    return schedule


def print_schedule(schedule: List[Matchup]) -> None:
    """Quick human-readable dump, grouped by round."""
    rounds = {}
    for m in schedule:
        rounds.setdefault(m.round_num, []).append(m)

    for round_num in sorted(rounds):
        print(f"Round {round_num}:")
        for m in rounds[round_num]:
            print(f"  {m.away} @ {m.home}")


if __name__ == "__main__":
    teams = ["Warriors", "Lakers", "Celtics", "Bulls", "Nets", "Heat"]
    schedule = generate_round_robin(teams, double_round=True)
    print_schedule(schedule)
    print(f"\nTotal games: {len(schedule)}")
