"""
Real NBA team home cities with approximate latitude/longitude, used to
compute travel distance between games. Coordinates are for each team's
home arena's city (rounded to a reasonable precision -- exact arena
address isn't necessary for schedule-level travel estimates).
"""

NBA_TEAM_CITIES = {
    "Atlanta Hawks": (33.7573, -84.3963),
    "Boston Celtics": (42.3662, -71.0621),
    "Brooklyn Nets": (40.6826, -73.9754),
    "Charlotte Hornets": (35.2251, -80.8392),
    "Chicago Bulls": (41.8807, -87.6742),
    "Cleveland Cavaliers": (41.4965, -81.6882),
    "Dallas Mavericks": (32.7905, -96.8103),
    "Denver Nuggets": (39.7487, -105.0077),
    "Detroit Pistons": (42.3410, -83.0550),
    "Golden State Warriors": (37.7680, -122.3877),
    "Houston Rockets": (29.7508, -95.3621),
    "Indiana Pacers": (39.7640, -86.1555),
    "Los Angeles Clippers": (34.0430, -118.2673),
    "Los Angeles Lakers": (34.0430, -118.2673),
    "Memphis Grizzlies": (35.1382, -90.0505),
    "Miami Heat": (25.7814, -80.1870),
    "Milwaukee Bucks": (43.0451, -87.9174),
    "Minnesota Timberwolves": (44.9795, -93.2760),
    "New Orleans Pelicans": (29.9490, -90.0821),
    "New York Knicks": (40.7505, -73.9934),
    "Oklahoma City Thunder": (35.4634, -97.5151),
    "Orlando Magic": (28.5392, -81.3839),
    "Philadelphia 76ers": (39.9012, -75.1720),
    "Phoenix Suns": (33.4457, -112.0712),
    "Portland Trail Blazers": (45.5316, -122.6668),
    "Sacramento Kings": (38.5802, -121.4997),
    "San Antonio Spurs": (29.4269, -98.4375),
    "Toronto Raptors": (43.6435, -79.3791),
    "Utah Jazz": (40.7683, -111.9011),
    "Washington Wizards": (38.8981, -77.0209),
}
