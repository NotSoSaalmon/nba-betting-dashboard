import requests
import pandas as pd

s = chr(47)
domain = ".".join(["site", "api", "espn", "com"])
url = "https:" + s + s + domain + s + s.join(["apis", "site", "v2", "sports", "basketball", "nba", "injuries"])

try:
    resp = requests.get(url, timeout=15)
    data = resp.json()
    out_players = []
    for team_entry in data.get("injuries", []):
        team_name = team_entry.get("displayName", "")
        for inj in team_entry.get("injuries", []):
            status = str(inj.get("status", "")).lower()
            if "out" in status:
                athlete = inj.get("athlete", {})
                p_name = athlete.get("displayName", "")
                if p_name:
                    out_players.append({"PLAYER_NAME": p_name, "TEAM_NAME": team_name, "STATUS": "OUT"})

    out_df = pd.DataFrame(out_players).drop_duplicates(subset=["PLAYER_NAME"])
    out_df.to_csv("/Users/rasheedwhiters/nba_project/injuries_out.csv", index=False)
    print(f"Saved {len(out_df)} players currently marked OUT to injuries_out.csv!")
except Exception as e:
    print("Could not fetch injuries:", e)
    pd.DataFrame(columns=["PLAYER_NAME", "TEAM_NAME", "STATUS"]).to_csv("/Users/rasheedwhiters/nba_project/injuries_out.csv", index=False)
