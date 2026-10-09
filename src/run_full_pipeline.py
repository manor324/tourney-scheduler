"""
Stage 3 demo: run the full pipeline end to end.

  Stage 1 (round_robin.py)         -> who plays who
  Stage 2 (constrained_scheduler)  -> who plays who, and when (feasible)
  Stage 3 (optimizer.py)           -> same games, better days (less travel)

Uses a handful of real NBA teams with real city coordinates so the
"total travel distance" numbers mean something concrete.
"""

from round_robin import generate_round_robin
from constrained_scheduler import assign_days, Constraints, print_scheduled_games
from travel_cost import total_travel_distance, per_team_travel_breakdown
from optimizer import optimize_schedule
from team_locations import NBA_TEAM_CITIES


def main():
    teams = [
        "Golden State Warriors",
        "Los Angeles Lakers",
        "Boston Celtics",
        "Miami Heat",
        "Chicago Bulls",
        "Dallas Mavericks",
    ]

    print(f"Teams: {', '.join(teams)}\n")

    # --- Stage 1: who plays who ---
    matchups = generate_round_robin(teams, double_round=True)
    print(f"Stage 1: generated {len(matchups)} matchups.\n")

    # --- Stage 2: assign feasible days ---
    constraints = Constraints(
        season_days=60,
        max_consecutive_away=2,
        max_consecutive_home=3,
        min_rest_days=1,
    )
    scheduled = assign_days(matchups, teams, constraints)
    if scheduled is None:
        print("Stage 2 failed to find a feasible schedule. Try loosening constraints "
              "or increasing season_days.")
        return

    print("Stage 2: feasible schedule found.\n")

    before_cost = total_travel_distance(scheduled, teams, NBA_TEAM_CITIES)
    print(f"Total travel distance BEFORE optimization: {before_cost:,.0f} km\n")

    # --- Stage 3: optimize for travel distance ---
    optimized, cost_history = optimize_schedule(
        scheduled, teams, constraints, NBA_TEAM_CITIES,
        iterations=8000, start_temp=80.0,
    )

    after_cost = total_travel_distance(optimized, teams, NBA_TEAM_CITIES)
    improvement = (before_cost - after_cost) / before_cost * 100

    print(f"Total travel distance AFTER optimization:  {after_cost:,.0f} km")
    print(f"Improvement: {improvement:.1f}%\n")

    print("Per-team travel breakdown (after optimization):")
    breakdown = per_team_travel_breakdown(optimized, teams, NBA_TEAM_CITIES)
    for team, dist in sorted(breakdown.items(), key=lambda x: -x[1]):
        print(f"  {team:28s} {dist:>8,.0f} km")

    print("\nFinal optimized schedule:")
    print_scheduled_games(optimized)


if __name__ == "__main__":
    main()
