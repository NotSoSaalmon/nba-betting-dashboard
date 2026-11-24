import requests
import pandas as pd
import tomllib
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

with open("/Users/rasheedwhiters/nba_project/.streamlit/secrets.toml", "rb") as f:
    secrets = tomllib.load(f)
API_KEY = secrets["ODDS_API_KEY"].strip()

s = chr(47)
domain = ".".join(["api", "the-odds-api", "com"])
host = "https:" + s + s + domain

# Anchor to US Central Time (America/Chicago) so evening NBA games match today's calendar date
local_tz = ZoneInfo("America/Chicago")
today_str = datetime.now(local_tz).strftime("%Y-%m-%d")

# 1. Fetch Game Lines (Spreads & Totals)
game_odds_url = s.join([host, "v4", "sports", "basketball_nba", "odds"])
g_resp = requests.get(game_odds_url, params={
    "apiKey": API_KEY,
    "regions": "us",
    "markets": "spreads,totals",
    "bookmakers": "draftkings,fanduel"
}, timeout=15)

game_env = {}
if g_resp.status_code == 200:
    for game in g_resp.json():
        eid = game["id"]
        spread_val, total_val = 0.0, 226.0
        for book in game.get("bookmakers", []):
            for m in book.get("markets", []):
                if m["key"] == "totals" and m["outcomes"]:
                    total_val = next(iter(m["outcomes"]))["point"]
                elif m["key"] == "spreads" and m["outcomes"]:
                    for o in m["outcomes"]:
                        if o["name"] == game["home_team"]:
                            spread_val = abs(o["point"])
            break
        game_env[eid] = {"GAME_TOTAL": total_val, "SPREAD": spread_val}

# 2. Fetch Events & Keep ONLY Games Tipping Off Today
events_url = s.join([host, "v4", "sports", "basketball_nba", "events"])
resp = requests.get(events_url, params={"apiKey": API_KEY}, timeout=15)
if resp.status_code != 200:
    print(f"API Error {resp.status_code}: {resp.text}")
    exit()

todays_events = []
for ev in resp.json():
    tip_utc = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
    tip_local_date = tip_utc.astimezone(local_tz).strftime("%Y-%m-%d")
    if tip_local_date == today_str:
        todays_events.append(ev)

print(f"Found {len(todays_events)} NBA games scheduled specifically for {today_str}.")

rows = []
market_map = {"player_points": "PTS", "player_rebounds": "REB", "player_assists": "AST", "player_points_rebounds_assists": "PRA"}

for event in todays_events:
    event_id = event["id"]
    home_team = event["home_team"]
    away_team = event["away_team"]
    env = game_env.get(event_id, {"GAME_TOTAL": 226.0, "SPREAD": 0.0})

    props_url = s.join([host, "v4", "sports", "basketball_nba", "events", event_id, "odds"])
    p_resp = requests.get(props_url, params={
        "apiKey": API_KEY,
        "regions": "us_dfs,us",
        "markets": "player_points,player_rebounds,player_assists,player_points_rebounds_assists",
        "bookmakers": "prizepicks,draftkings,fanduel",
        "oddsFormat": "american"
    }, timeout=15)
    if p_resp.status_code != 200:
        continue

    data = p_resp.json()
    for book in data.get("bookmakers", []):
        book_key = book["key"]
        book_name = book["title"]
        priority = 0 if book_key == "prizepicks" else 1

        for market in book.get("markets", []):
            stat_code = market_map.get(market["key"])
            for outcome in market.get("outcomes", []):
                if outcome["name"] == "Over":
                    rows.append({
                        "FETCH_DATE": today_str,
                        "PLAYER_NAME": outcome["description"],
                        "STAT": stat_code,
                        "LINE": outcome["point"],
                        "BOOK": book_name,
                        "_priority": priority,
                        "HOME_TEAM": home_team,
                        "AWAY_TEAM": away_team,
                        "GAME_TOTAL": env["GAME_TOTAL"],
                        "SPREAD": env["SPREAD"]
                    })

odds_df = pd.DataFrame(rows)
if not odds_df.empty:
    odds_df = odds_df.sort_values(by="_priority").drop_duplicates(subset=["PLAYER_NAME", "STAT"]).drop(columns=["_priority"])
    odds_df.to_csv("/Users/rasheedwhiters/nba_project/live_odds.csv", index=False)
    print(f"Saved {len(odds_df)} PrizePicks/book props strictly for {today_str}!")
else:
    # Overwrite with empty table if there are 0 NBA games today (e.g., All-Star break / Thanksgiving)
    pd.DataFrame(columns=["FETCH_DATE", "PLAYER_NAME", "STAT", "LINE", "BOOK", "HOME_TEAM", "AWAY_TEAM", "GAME_TOTAL", "SPREAD"]).to_csv("/Users/rasheedwhiters/nba_project/live_odds.csv", index=False)
    print(f"No NBA games scheduled for {today_str} — cleared old slate.")
