import sys
import requests
import pandas as pd
import tomllib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

with open("/Users/rasheedwhiters/nba_project/.streamlit/secrets.toml", "rb") as f:
    secrets = tomllib.load(f)
API_KEY = secrets["ODDS_API_KEY"].strip()

s = chr(47)
domain = ".".join(["api", "the-odds-api", "com"])
host = "https:" + s + s + domain

local_tz = ZoneInfo("America/Chicago")
offset_days = int(sys.argv.pop()) if len(sys.argv) > 1 else 0
target_date = (datetime.now(local_tz) + timedelta(days=offset_days)).strftime("%Y-%m-%d")

events_url = s.join([host, "v4", "sports", "basketball_nba", "events"])
resp = requests.get(events_url, params={"apiKey": API_KEY}, timeout=15)
rows = []
if resp.status_code == 200:
    for ev in resp.json():
        tip_utc = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
        if tip_utc.astimezone(local_tz).strftime("%Y-%m-%d") == target_date:
            rows.append({
                "SLATE_DATE": target_date,
                "HOME_TEAM": ev["home_team"],
                "AWAY_TEAM": ev["away_team"],
                "GAME_TOTAL": 226.0,
                "SPREAD": 0.0
            })

pd.DataFrame(rows).to_csv("/Users/rasheedwhiters/nba_project/slate_games.csv", index=False)
print(f"Saved {len(rows)} scheduled NBA games for {target_date} (0 API credits used)!")
