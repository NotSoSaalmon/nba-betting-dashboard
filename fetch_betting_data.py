import time
import random
import pandas as pd
from nba_api.stats.endpoints import leaguedashteamstats, leaguegamelog

# 1. Fetch ALL 30 teams' Pace & Defensive Rating
print("Fetching team pace and defensive ratings...")
team_stats = leaguedashteamstats.LeagueDashTeamStats(
    season='2026-27',
    measure_type_detailed_defense='Advanced',
    timeout=30
)
teams_df = next(iter(team_stats.get_data_frames()))
teams_df[['TEAM_NAME', 'GP', 'PACE', 'DEF_RATING', 'OFF_RATING']].to_csv('/Users/rasheedwhiters/nba_project/team_ratings.csv', index=False)
print("Saved team_ratings.csv!")

# 2. Pause safely before the second request
time.sleep(random.uniform(2.0, 4.0))

# 3. Fetch ALL NBA players' game logs in ONE bulk call
print("Fetching game logs for ALL NBA players...")
all_logs = leaguegamelog.LeagueGameLog(
    season='2026-27',
    player_or_team_abbreviation='P',
    timeout=30
)
logs_df = next(iter(all_logs.get_data_frames()))
logs_df.to_csv('/Users/rasheedwhiters/nba_project/all_player_logs.csv', index=False)
print("Saved all_player_logs.csv!")
