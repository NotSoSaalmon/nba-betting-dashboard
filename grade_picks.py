import os
import pandas as pd
from datetime import datetime
from model_engine import load_all_data, calculate_projection, team_abbr_map

BASE = "/Users/rasheedwhiters/nba_project/"
HISTORY_FILE = f"{BASE}pick_history.csv"

all_players_df, teams_df, shot_df, track_df, dvp_table, inj_df = load_all_data(BASE)
out_players_set = set(inj_df["PLAYER_NAME"].tolist())
today_str = datetime.now().strftime("%Y-%m-%d")

if os.path.exists(HISTORY_FILE):
    hist_df = pd.read_csv(HISTORY_FILE)
else:
    hist_df = pd.DataFrame(columns=[
        "Date", "Player", "Opponent", "Stat", "Pick", "Book Line",
        "Model Proj", "Win Prob %", "Actual", "Result"
    ])

if not hist_df.empty:
    for idx, row in hist_df[hist_df["Result"] == "PENDING"].iterrows():
        p_logs = all_players_df[
            (all_players_df["PLAYER_NAME"] == row["Player"]) &
            (all_players_df["GAME_DATE"].dt.strftime("%Y-%m-%d") >= row["Date"])
        ]
        if not p_logs.empty:
            game_row = p_logs.sort_values(by="GAME_DATE", ascending=True).squeeze()
            if isinstance(game_row, pd.DataFrame):
                game_row = game_row.head(1).squeeze()
            actual_val = float(game_row[row["Stat"]])
            line = float(row["Book Line"])
            hist_df.at[idx, "Actual"] = actual_val
            if actual_val == line:
                hist_df.at[idx, "Result"] = "PUSH"
            elif (row["Pick"] == "OVER" and actual_val > line) or (row["Pick"] == "UNDER" and actual_val < line):
                hist_df.at[idx, "Result"] = "WIN"
            else:
                hist_df.at[idx, "Result"] = "LOSS"

if os.path.exists(f"{BASE}live_odds.csv") and today_str not in hist_df["Date"].values:
    odds_df = pd.read_csv(f"{BASE}live_odds.csv")
    today_rows = []
    for _, row in odds_df.iterrows():
        p_name = row["PLAYER_NAME"]
        if p_name in out_players_set:
            continue
        stat = row["STAT"]
        line = row["LINE"]
        p_df = all_players_df[all_players_df["PLAYER_NAME"] == p_name]
        if len(p_df) < 5:
            continue

        player_team_abbr = next(iter(p_df["TEAM_ABBREVIATION"]))
        player_team_full = team_abbr_map.get(player_team_abbr, "")
        is_home = (player_team_full == row["HOME_TEAM"])
        opponent = row["AWAY_TEAM"] if is_home else row["HOME_TEAM"]

        proj, lean, win_prob, pct_edge, *_ = calculate_projection(
            p_df, all_players_df, p_name, stat, opponent, line, teams_df, shot_df, track_df, dvp_table,
            out_players_set=out_players_set, is_home=is_home,
            game_total=row.get("GAME_TOTAL", 226.0), spread=row.get("SPREAD", 0.0)
        )
        today_rows.append({
            "Date": today_str,
            "Player": p_name,
            "Opponent": opponent,
            "Stat": stat,
            "Pick": lean,
            "Book Line": line,
            "Model Proj": round(proj, 1),
            "Win Prob %": round(win_prob, 1),
            "Actual": None,
            "Result": "PENDING"
        })

    if today_rows:
        full_today = pd.DataFrame(today_rows).sort_values(by="Win Prob %", ascending=False)
        balanced_15 = pd.concat([
            full_today[full_today["Stat"] == "PTS"].head(5),
            full_today[full_today["Stat"] == "REB"].head(5),
            full_today[full_today["Stat"] == "AST"].head(5)
        ]).sort_values(by="Win Prob %", ascending=False)
        hist_df = pd.concat([balanced_15, hist_df], ignore_index=True)

hist_df.to_csv(HISTORY_FILE, index=False)
print(f"Graded pick history saved ({len(hist_df)} total tracked picks)!")
