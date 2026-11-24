import pandas as pd

s = chr(47)
domain = ".".join(["github", "com"])
url = "https:" + s + s + domain + s + s.join(["nflverse", "nflverse-data", "releases", "download", "player_stats", "player_stats_2026.csv"])

print("Downloading 2026 NFL weekly player stats...")
df = pd.read_csv(url, low_memory=False)
df = df[df["season_type"] == "REG"].copy()

cols = [
    "player_display_name", "position", "recent_team", "opponent_team",
    "week", "passing_yards", "rushing_yards", "receiving_yards",
    "carries", "targets", "completions", "attempts"
]
df = df[[c for c in cols if c in df.columns]].fillna(0)
df.to_csv("/Users/rasheedwhiters/nba_project/nfl_player_logs.csv", index=False)
print(f"Saved {len(df)} NFL player game rows to nfl_player_logs.csv!")
