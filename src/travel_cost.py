"""
Stage 3 helper: measuring how "good" a schedule is, in terms of travel.

A team's travel cost is the sum of the distances between the CITIES of
its consecutive AWAY games, in day order -- that's a reasonable proxy for
how much a team has to fly around during a road trip. (Home games "reset"
the team back to its home city, which is how real teams operate: they fly
home between road trips rather than commuting from a road city.)
"""

import math
from typing import List, Dict, Tuple
from constrained_scheduler import ScheduledGame


def haversine_distance(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
    """
    Great-circle distance between two (lat, lon) points, in kilometers.
    This accounts for the Earth's curvature -- straight-line lat/lon
    differences would be misleading over long distances.
    """
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    R = 6371.0  # Earth's radius in km

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def total_travel_distance(
    games: List[ScheduledGame], teams: List[str], city_lookup: Dict[str, Tuple[float, float]]
) -> float:
    """
    Sum of travel distance across every team's season, in km.

    For each team: walk its games in day order. Track the team's current
    location, starting at its home city. Every AWAY game adds the distance
    from current location to that game's location, then updates current
    location to the away city. Every HOME game adds the distance from
    current location back to the home city (if not already there), then
    resets current location to home.
    """
    total = 0.0

    for team in teams:
        home_city = city_lookup[team]
        current_location = home_city

        team_games = [g for g in games if g.home == team or g.away == team]
        team_games.sort(key=lambda g: g.day)

        for g in team_games:
            if g.away == team:
                away_city = city_lookup[g.home]  # they travel to the home team's city
                total += haversine_distance(current_location, away_city)
                current_location = away_city
            else:
                # Home game -- team must be back home. If they were on the
                # road, this is the flight home.
                if current_location != home_city:
                    total += haversine_distance(current_location, home_city)
                    current_location = home_city

        # End of season: no need to fly home again for cost purposes,
        # we only count travel actually required to play the games.

    return total


def per_team_travel_breakdown(
    games: List[ScheduledGame], teams: List[str], city_lookup: Dict[str, Tuple[float, float]]
) -> Dict[str, float]:
    """Same as total_travel_distance, but broken out per team (km each)."""
    breakdown = {}
    for team in teams:
        breakdown[team] = total_travel_distance(games, [team], city_lookup)
    return breakdown
