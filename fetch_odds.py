import requests
import pandas as pd
import tomllib

with open("/Users/rasheedwhiters/nba_project/.streamlit/secrets.toml", "rb") as f:
    secrets = tomllib.load(f)
API_KEY = secrets["ODDS_API_KEY"].strip()

s = chr(47)
host = "https:" + s + s + "api.the-odds-api.com"
events_url = s.join([host, "v4", "sports", "basketball_nba", "events"])

resp = requests.get(events_url, params={"apiKey": API_KEY}, timeout=15)
if resp.status_code != 200:
    print(f"API Error {resp.status_code}: {resp.text}")
    exit()

events = resp.json()
print(f"Found {len(events)} NBA games. Fetching player props...")

rows = []
market_map = {
    "player_points": "PTS",
    "player_rebounds": "REB",
    "player_assists": "AST"
}

for event in events:
    event_id = event["id"]
    home_team = event["home_team"]
    away_team = event["away_team"]
    
    props_url = s.join([host, "v4", "sports", "basketball_nba", "events", event_id, "odds"])
    params = {
        "apiKey": API_KEY,
        "regions": "us",
        "markets": "player_points,player_rebounds,player_assists",
        "bookmakers": "draftkings,fanduel",
        "oddsFormat": "american"
    }
    p_resp = requests.get(props_url, params=params, timeout=15)
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
                        "AWAY_TEAM": away_team
                    })

odds_df = pd.DataFrame(rows)
if not odds_df.empty:
    odds_df = odds_df.drop_duplicates(subset=["PLAYER_NAME", "STAT"])
    odds_df.to_csv("/Users/rasheedwhiters/nba_project/live_odds.csv", index=False)
    print(f"Saved {len(odds_df)} live player prop lines to live_odds.csv!")
else:
    print("Connected successfully! Sportsbooks haven't posted player props yet for today's slate—try again later today closer to tip-off.")
