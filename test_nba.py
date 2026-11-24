import pandas as pd
from nba_api.stats.endpoints import playercareerstats
from nba_api.stats.static import players

# 1. Look up Giannis Antetokounmpo's official NBA ID number
# nba_api stores a local list of players so we can find his ID without internet
player_list = players.find_players_by_full_name("Giannis Antetokounmpo")
giannis = player_list[0]  # Grab the first match from the search results
player_id = giannis["id"]
print(f"Found {giannis['full_name']} with ID: {player_id}")

# 2. Ask NBA.com for his career stats using that ID
career = playercareerstats.PlayerCareerStats(player_id=player_id)

# 3. Convert the response into a readable table (DataFrame)
# [0] grabs the first table returned (Regular Season stats)
df = career.get_data_frames()[0]

# 4. Print just the key columns for his most recent 5 seasons
print(df[["SEASON_ID", "TEAM_ABBREVIATION", "GP", "PTS", "REB", "AST"]].tail(5))
