import time
import random
import pandas as pd
from nba_api.stats.endpoints import leaguedashteamstats, leaguegamelog

# 1. Fetch ALL 30 teams' Pace & Overall Defensive Rating
print("Fetching team advanced ratings...")
adv_stats = leaguedashteamstats.LeagueDashTeamStats(
    season='2026-27',
    measure_type_detailed_defense='Advanced',
    timeout=30
)
adv_df = next(iter(adv_stats.get_data_frames()))[['TEAM_NAME', 'TEAM_ID', 'GP', 'PACE', 'DEF_RATING', 'OFF_RATING']]

time.sleep(random.uniform(2.0, 3.5))

# 2. Fetch Opponent Stats Allowed (Points, Rebounds, Assists allowed per game)
print("Fetching opponent stats allowed...")
opp_stats = leaguedashteamstats.LeagueDashTeamStats(
    season='2026-27',
    measure_type_detailed_defense='Opponent',
    per_mode_detailed='PerGame',
    timeout=30
)
opp_df = next(iter(opp_stats.get_data_frames()))[['TEAM_ID', 'OPP_PTS', 'OPP_REB', 'OPP_AST']]

# Merge into one rich team_ratings.csv
teams_df = pd.merge(adv_df, opp_df, on='TEAM_ID')
teams_df.to_csv('/Users/rasheedwhiters/nba_project/team_ratings.csv', index=False)
print("Saved upgraded team_ratings.csv!")

time.sleep(random.uniform(2.0, 3.5))

# 3. Fetch ALL NBA players' game logs
print("Fetching game logs for ALL NBA players...")
all_logs = leaguegamelog.LeagueGameLog(
    season='2026-27',
    player_or_team_abbreviation='P',
    timeout=30
)
logs_df = next(iter(all_logs.get_data_frames()))
logs_df.to_csv('/Users/rasheedwhiters/nba_project/all_player_logs.csv', index=False)
print("Saved all_player_logs.csv!")
