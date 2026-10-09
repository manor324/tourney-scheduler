"""
Stage 5 demo: run the full pipeline (Stages 1-4 combined) at IPL scale
using the ACTUAL IPL format -- 10 teams split into two groups of five,
14 games each (not a flat double round-robin).

This is the "decent real-world scale" milestone for this project. Going
further (NBA/NFL/MLB scale, 30+ teams at higher game density) hits a
real performance wall in the current constraint model -- see
docs/scaling_notes.md for what we found and why.
"""

import time
from collections import Counter

from ipl_format import generate_ipl_schedule
from constrained_scheduler import assign_days, Constraints, print_scheduled_games
from optimizer import optimize_schedule
from travel_cost import total_travel_distance
from team_locations import NBA_TEAM_CITIES


# Mirrors the real IPL 2025 group structure and seed-based row pairings.
GROUP_A = ["Chennai Super Kings", "Kolkata Knight Riders", "Rajasthan Royals",
           "Royal Challengers Bengaluru", "Punjab Kings"]
GROUP_B = ["Mumbai Indians", "Sunrisers Hyderabad", "Gujarat Titans",
           "Delhi Capitals", "Lucknow Super Giants"]
ROW_PAIRS = {a: b for a, b in zip(GROUP_A, GROUP_B)}

# Reuse NBA city coordinates as stand-ins so travel-cost code works
# unchanged -- swap in real Indian city coordinates for accurate numbers.
ALL_TEAMS = GROUP_A + GROUP_B
CITY_LOOKUP = {name: coords for name, coords in zip(ALL_TEAMS, NBA_TEAM_CITIES.values())}


def main():
    matchups = generate_ipl_schedule(GROUP_A, GROUP_B, ROW_PAIRS)

    counts = Counter()
    for m in matchups:
        counts[m.home] += 1
        counts[m.away] += 1
    games_per_team = max(counts.values())

    print(f"Teams: {len(ALL_TEAMS)}")
    print(f"Games per team: {games_per_team}  (real IPL: 14)")
    print(f"Total games: {len(matchups)}  (real IPL: 70 in league stage)\n")

    constraints = Constraints(
        season_days=60, max_consecutive_away=2, max_consecutive_home=3, min_rest_days=1
    )

    start = time.time()
    scheduled = assign_days(matchups, ALL_TEAMS, constraints, time_limit_seconds=60.0)
    elapsed = time.time() - start

    if scheduled is None:
        print(f"FAILED to find a feasible schedule in {elapsed:.1f}s.")
        return

    print(f"Stage 2: feasible schedule found in {elapsed:.1f}s.\n")

    # Don't just trust "success" -- verify every constraint actually holds.
    max_away_streak = 0
    max_home_streak = 0
    min_gap_seen = float("inf")
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
            max_away_streak = max(max_away_streak, away_streak)
            max_home_streak = max(max_home_streak, home_streak)
            if i > 0:
                min_gap_seen = min(min_gap_seen, g.day - team_games[i - 1].day)

    print("Verification against Stage 2 constraints:")
    print(f"  Max away streak observed: {max_away_streak} (limit {constraints.max_consecutive_away})")
    print(f"  Max home streak observed: {max_home_streak} (limit {constraints.max_consecutive_home})")
    print(f"  Min rest gap observed:    {min_gap_seen} days (required >= {constraints.min_rest_days + 1})")
    assert max_away_streak <= constraints.max_consecutive_away
    assert max_home_streak <= constraints.max_consecutive_home
    assert min_gap_seen >= constraints.min_rest_days + 1
    print("  All constraints verified OK.\n")

    # Stage 3: optimize for travel.
    before_cost = total_travel_distance(scheduled, ALL_TEAMS, CITY_LOOKUP)
    optimized, _ = optimize_schedule(
        scheduled, ALL_TEAMS, constraints, CITY_LOOKUP, iterations=6000, start_temp=80.0
    )
    after_cost = total_travel_distance(optimized, ALL_TEAMS, CITY_LOOKUP)
    improvement = (before_cost - after_cost) / before_cost * 100

    print(f"Travel distance before optimization: {before_cost:,.0f} km")
    print(f"Travel distance after optimization:  {after_cost:,.0f} km")
    print(f"Improvement: {improvement:.1f}%\n")

    print("Final optimized schedule (first 15 games):")
    print_scheduled_games(optimized[:15])


if __name__ == "__main__":
    main()
