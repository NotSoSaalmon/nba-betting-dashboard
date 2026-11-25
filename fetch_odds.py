import sys
import requests
import pandas as pd
import tomllib
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

with open("/Users/rasheedwhiters/nba_project/.streamlit/secrets.toml", "rb") as f:
    secrets = tomllib.load(f)
API_KEY = secrets["ODDS_API_KEY"].strip()

s = chr(47)
domain = ".".join(["api", "the-odds-api", "com"])
host = "https:" + s + s + domain

local_tz = ZoneInfo("America/Chicago")
offset_days = int(sys.argv) if len(sys.argv) > 1 else 0
target_date = (datetime.now(local_tz) + timedelta(days=offset_days)).strftime("%Y-%m-%d")

# 1. Fetch Game Lines (Spreads & Totals)
game_odds_url = s.join([host, "v4", "sports", "basketball_nba", "odds"])
g_resp = requests.get(game_odds_url, params={
    "apiKey": API_KEY, "regions": "us", "markets": "spreads,totals", "bookmakers": "draftkings,fanduel"
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

# 2. Fetch Events for Target Date
events_url = s.join([host, "v4", "sports", "basketball_nba", "events"])
resp = requests.get(events_url, params={"apiKey": API_KEY}, timeout=15)
if resp.status_code != 200:
    print(f"API Error {resp.status_code}: {resp.text}")
    exit()

todays_events = []
for ev in resp.json():
    tip_utc = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
    tip_local_date = tip_utc.astimezone(local_tz).strftime("%Y-%m-%d")
    if tip_local_date == target_date:
        todays_events.append(ev)

print(f"Found {len(todays_events)} NBA games scheduled for {target_date}.")

rows = []
market_map = {
    "player_points": "PTS",
    "player_rebounds": "REB",
    "player_assists": "AST",
    "player_points_rebounds_assists": "PRA"
}

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

    # Fallback without PRA if API rejects combo market for an early game
    if p_resp.status_code != 200:
        p_resp = requests.get(props_url, params={
            "apiKey": API_KEY,
            "regions": "us_dfs,us",
            "markets": "player_points,player_rebounds,player_assists",
            "bookmakers": "prizepicks,draftkings,fanduel",
            "oddsFormat": "american"
        }, timeout=15)
        if p_resp.status_code != 200:
            print(f"Skipped {away_team} @ {home_team} (HTTP {p_resp.status_code}): {p_resp.text[:100]}")
            continue

    data = p_resp.json()
    for book in data.get("bookmakers", []):
        book_key = book["key"]
        book_name = book["title"]
        priority = 0 if book_key == "prizepicks" else 1

        for market in book.get("markets", []):
            stat_code = market_map.get(market["key"])
            if not stat_code:
                continue
            for outcome in market.get("outcomes", []):
                if outcome["name"] == "Over":
                    rows.append({
                        "FETCH_DATE": target_date,
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
    pp_count = (odds_df["BOOK"] == "PrizePicks").sum()
    print(f"Saved {len(odds_df)} props ({pp_count} from PrizePicks) for {target_date}!")
else:
    print(f"0 props returned from API yet for {target_date} — kept existing live_odds.csv.")
