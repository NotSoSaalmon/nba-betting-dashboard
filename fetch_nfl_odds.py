import requests
import pandas as pd
import tomllib
from datetime import datetime

# Only fetch NFL odds on Thursday (3), Sunday (6), or Monday (0) to save API credits
if datetime.now().weekday() not in:
    print("Not an NFL game day (Thu/Sun/Mon) — skipping NFL odds to save API credits.")
    exit()

with open("/Users/rasheedwhiters/nba_project/.streamlit/secrets.toml", "rb") as f:
    secrets = tomllib.load(f)
API_KEY = secrets["ODDS_API_KEY"].strip()

s = chr(47)
domain = ".".join(["api", "the-odds-api", "com"])
host = "https:" + s + s + domain

# 1. Fetch NFL Game Totals & Spreads
g_url = s.join([host, "v4", "sports", "americanfootball_nfl", "odds"])
g_resp = requests.get(g_url, params={
    "apiKey": API_KEY, "regions": "us", "markets": "totals", "bookmakers": "draftkings,fanduel"
}, timeout=15)

game_totals = {}
if g_resp.status_code == 200:
    for g in g_resp.json():
        for b in g.get("bookmakers", []):
            for m in b.get("markets", []):
                if m["key"] == "totals" and m["outcomes"]:
                    game_totals[g["id"]] = next(iter(m["outcomes"]))["point"]
            break

# 2. Fetch NFL PrizePicks Player Props
events_url = s.join([host, "v4", "sports", "americanfootball_nfl", "events"])
resp = requests.get(events_url, params={"apiKey": API_KEY}, timeout=15)
if resp.status_code != 200:
    print(f"NFL API Error {resp.status_code}: {resp.text}")
    exit()

rows = []
market_map = {
    "player_pass_yds": "PASS_YDS",
    "player_rush_yds": "RUSH_YDS",
    "player_reception_yds": "REC_YDS"
}

for event in resp.json():
    eid = event["id"]
    total_pts = game_totals.get(eid, 44.5)
    props_url = s.join([host, "v4", "sports", "americanfootball_nfl", "events", eid, "odds"])
    p_resp = requests.get(props_url, params={
        "apiKey": API_KEY,
        "regions": "us_dfs,us",
        "markets": "player_pass_yds,player_rush_yds,player_reception_yds",
        "bookmakers": "prizepicks,draftkings,fanduel",
        "oddsFormat": "american"
    }, timeout=15)
    if p_resp.status_code != 200:
        continue

    for book in p_resp.json().get("bookmakers", []):
        prio = 0 if book["key"] == "prizepicks" else 1
        for m in book.get("markets", []):
            stat_code = market_map.get(m["key"])
            for o in m.get("outcomes", []):
                if o["name"] == "Over":
                    rows.append({
                        "PLAYER_NAME": o["description"],
                        "STAT": stat_code,
                        "LINE": o["point"],
                        "BOOK": book["title"],
                        "_prio": prio,
                        "HOME_TEAM": event["home_team"],
                        "AWAY_TEAM": event["away_team"],
                        "GAME_TOTAL": total_pts
                    })

df = pd.DataFrame(rows)
if not df.empty:
    df = df.sort_values(by="_prio").drop_duplicates(subset=["PLAYER_NAME", "STAT"]).drop(columns=["_prio"])
    df.to_csv("/Users/rasheedwhiters/nba_project/nfl_live_odds.csv", index=False)
    print(f"Saved {len(df)} NFL player props to nfl_live_odds.csv!")
