import requests
import pandas as pd
import tomllib

with open("/Users/rasheedwhiters/nba_project/.streamlit/secrets.toml", "rb") as f:
    secrets = tomllib.load(f)
API_KEY = secrets["ODDS_API_KEY"].strip()

s = chr(47)
host = "https:" + s + s + "://the-odds-api.com"

# 1. Fetch Game Lines (Spreads & Totals) in 1 single call
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
                    total_val = m["outcomes"]["point"]
                elif m["key"] == "spreads" and m["outcomes"]:
                    for o in m["outcomes"]:
                        if o["name"] == game["home_team"]:
                            spread_val = abs(o["point"])
            break
        game_env[eid] = {"GAME_TOTAL": total_val, "SPREAD": spread_val}

# 2. Fetch Player Props
events_url = s.join([host, "v4", "sports", "basketball_nba", "events"])
resp = requests.get(events_url, params={"apiKey": API_KEY}, timeout=15)
if resp.status_code != 200:
    print(f"API Error {resp.status_code}: {resp.text}")
    exit()

events = resp.json()
print(f"Found {len(events)} NBA games. Fetching player props + game environments...")

rows = []
market_map = {"player_points": "PTS", "player_rebounds": "REB", "player_assists": "AST"}

for event in events:
    event_id = event["id"]
    home_team = event["home_team"]
    away_team = event["away_team"]
    env = game_env.get(event_id, {"GAME_TOTAL": 226.0, "SPREAD": 0.0})

    props_url = s.join([host, "v4", "sports", "basketball_nba", "events", event_id, "odds"])
    p_resp = requests.get(props_url, params={
        "apiKey": API_KEY,
        "regions": "us",
        "markets": "player_points,player_rebounds,player_assists",
        "bookmakers": "draftkings,fanduel",
        "oddsFormat": "american"
    }, timeout=15)
    if p_resp.status_code != 200:
        continue

    data = p_resp.json()
    for book in data.get("bookmakers", []):
        book_name = book["title"]
        for market in book.get("markets", []):
            stat_code = market_map.get(market["key"])
            for outcome in market.get("outcomes", []):
                if outcome["name"] == "Over":
                    rows.append({
                        "PLAYER_NAME": outcome["description"],
                        "STAT": stat_code,
                        "LINE": outcome["point"],
                        "BOOK": book_name,
                        "HOME_TEAM": home_team,
                        "AWAY_TEAM": away_team,
                        "GAME_TOTAL": env["GAME_TOTAL"],
                        "SPREAD": env["SPREAD"]
                    })

odds_df = pd.DataFrame(rows)
if not odds_df.empty:
    odds_df = odds_df.drop_duplicates(subset=["PLAYER_NAME", "STAT"])
    odds_df.to_csv("/Users/rasheedwhiters/nba_project/live_odds.csv", index=False)
    print(f"Saved {len(odds_df)} live props with Vegas totals & spreads!")
