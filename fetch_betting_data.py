import time
import random
import pandas as pd
from nba_api.stats.endpoints import leaguedashteamstats, leaguegamelog, playerindex, leaguedashplayerstats

# 1. Fetch ALL 30 teams' Pace & Overall Defensive Rating
print("Fetching team advanced ratings...")
adv_stats = leaguedashteamstats.LeagueDashTeamStats(
    season='2026-27',
    measure_type_detailed_defense='Advanced',
    timeout=30
)
adv_df = next(iter(adv_stats.get_data_frames()))[['TEAM_NAME', 'TEAM_ID', 'GP', 'PACE', 'DEF_RATING', 'OFF_RATING']]

time.sleep(random.uniform(2.0, 3.5))

# 2. Fetch Opponent Stats Allowed (Points, Rebounds, Assists, 3PM, FGM allowed per game)
print("Fetching opponent stats & 3PT/2PT defense...")
opp_stats = leaguedashteamstats.LeagueDashTeamStats(
    season='2026-27',
    measure_type_detailed_defense='Opponent',
    per_mode_detailed='PerGame',
    timeout=30
)
opp_raw = next(iter(opp_stats.get_data_frames()))
opp_raw['OPP_FG2M'] = opp_raw['OPP_FGM'] - opp_raw['OPP_FG3M']
opp_df = opp_raw[['TEAM_ID', 'OPP_PTS', 'OPP_REB', 'OPP_AST', 'OPP_FG3M', 'OPP_FG2M', 'OPP_FG3_PCT']]

teams_df = pd.merge(adv_df, opp_df, on='TEAM_ID')
teams_df.to_csv('/Users/rasheedwhiters/nba_project/team_ratings.csv', index=False)
print("Saved upgraded team_ratings.csv with 3PT/2PT defense!")

time.sleep(random.uniform(2.0, 3.5))

# 3. Fetch ALL Players' Shot Profile (% of points from 2PT, 3PT, and FT) in ONE call
print("Fetching player shot profiles (2PT vs 3PT scoring shares)...")
p_scoring = leaguedashplayerstats.LeagueDashPlayerStats(
    season='2026-27',
    measure_type_detailed_defense='Scoring',
    timeout=30
)
scoring_df = next(iter(p_scoring.get_data_frames()))[['PLAYER_NAME', 'PCT_PTS_2PT', 'PCT_PTS_3PT', 'PCT_PTS_FT', 'PCT_PTS_PAINT']]
scoring_df.to_csv('/Users/rasheedwhiters/nba_project/player_shot_profile.csv', index=False)
print("Saved player_shot_profile.csv!")

time.sleep(random.uniform(2.0, 3.5))

# 4. Fetch Player Positions (G, F, C)
print("Fetching player positions...")
p_idx = playerindex.PlayerIndex(season='2026-27', timeout=30)
idx_df = next(iter(p_idx.get_data_frames()))
idx_df['PLAYER_NAME'] = idx_df['PLAYER_FIRST_NAME'] + ' ' + idx_df['PLAYER_LAST_NAME']
idx_df['POS'] = idx_df['POSITION'].fillna('G').apply(lambda x: str(x).split('-') if str(x) else 'G')
idx_df[['PLAYER_ID', 'PLAYER_NAME', 'POS']].to_csv('/Users/rasheedwhiters/nba_project/player_positions.csv', index=False)
print("Saved player_positions.csv!")

time.sleep(random.uniform(2.0, 3.5))

# 5. Fetch ALL NBA players' game logs
print("Fetching game logs for ALL NBA players...")
all_logs = leaguegamelog.LeagueGameLog(
    season='2026-27',
    player_or_team_abbreviation='P',
    timeout=30
)
logs_df = next(iter(all_logs.get_data_frames()))
logs_df.to_csv('/Users/rasheedwhiters/nba_project/all_player_logs.csv', index=False)
print("Saved all_player_logs.csv!")
