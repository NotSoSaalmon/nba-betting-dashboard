import pandas as pd
from nba_api.stats.endpoints import playergamelog
from nba_api.stats.static import players

player_dict = players.find_players_by_full_name("Giannis Antetokounmpo")
player_id = player_dict[0]['id']

gamelog = playergamelog.PlayerGameLog(player_id=player_id, season='2026-27')
df = gamelog.get_data_frames()[0]

recent_games = df[['GAME_DATE', 'MATCHUP', 'MIN', 'PTS', 'REB', 'AST']].head(10)
print(recent_games)
print("\nLast 10 Games Average Points:", recent_games['PTS'].mean())
