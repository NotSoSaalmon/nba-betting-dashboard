import pandas as pd
from nba_api.stats.endpoints import playergamelog
from nba_api.stats.static import players

# 1. Find the player ID (Example: Giannis Antetokounmpo)
player_dict = players.find_players_by_full_name("Giannis Antetokounmpo")
player_id = player_dict[0]['id']

# 2. Fetch current season game logs (e.g., 2026-27 season)
gamelog = playergamelog.PlayerGameLog(player_id=player_id, season='2026-27')
df = gamelog.get_data_frames()[0]

# 3. View recent games and calculate averages
recent_games = df[['GAME_DATE', 'MATCHUP', 'MIN', 'PTS', 'REB', 'AST']].head(10)
print(recent_games)
print("\nLast 10 Games Average Points:", recent_games['PTS'].mean())
