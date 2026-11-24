import os
import pandas as pd
from datetime import datetime
from model_engine import load_all_data, calculate_projection, team_abbr_map

BASE = "/Users/rasheedwhiters/nba_project/"
HISTORY_FILE = f"{BASE}pick_history.csv"

all_players_df, teams_df, shot_df, track_df, dvp_table, inj_df = load_all_data(BASE)

if os.path.exists(HISTORY_FILE):
    hist_df = pd.read_csv(HISTORY_FILE)
else:
    hist_df = pd.DataFrame(columns=[
        "Date", "Player", "Opponent", "Stat", "Pick", "Book Line",
        "Model Proj", "Win Prob %", "Actual", "Result"
    ])

# Find all completed game dates in all_player_logs.csv before today
today_str = datetime.now().strftime("%Y-%m-%d")
all_players_df["DATE_STR"] = all_players_df["GAME_DATE"].dt.strftime("%Y-%m-%d")
logged_dates = set(hist_df["Date"].dropna().unique())

# Find the earliest date in pick_history so we only backfill missed days since you started
start_date = min(logged_dates) if logged_dates else "2026-11-18"
all_game_dates = sorted([
    d for d in all_players_df["DATE_STR"].unique()
    if start_date <= d < today_str and d not in logged_dates
])

if not all_game_dates:
    print("No missed game dates found to backfill!")
    exit()

print(f"Backfilling {len(all_game_dates)} missed game dates: {all_game_dates}")

new_history_rows = []

for g_date in all_game_dates:
    # 1. Strict point-in-time cutoff: only use games played BEFORE g_date
    prior_logs = all_players_df[all_players_df["DATE_STR"] < g_date].copy()
    tonight_games = all_players_df[all_players_df["DATE_STR"] == g_date].copy()

    if prior_logs.empty or tonight_games.empty:
        continue

    day_candidates = []
    # Evaluate rotation players who played that night (MIN >= 20)
    active_tonight = tonight_games[tonight_games["MIN"] >= 20]

    for _, game_row in active_tonight.iterrows():
        p_name = game_row["PLAYER_NAME"]
        p_df = prior_logs[prior_logs["PLAYER_NAME"] == p_name]
        if len(p_df) < 6:
            continue

        matchup = str(game_row["MATCHUP"])
        is_home = "vs." in matchup
        opp_abbr = matchup.split(" ")[-1]
        opponent = team_abbr_map.get(opp_abbr, opp_abbr)

        for stat in ["PTS", "REB", "AST"]:
            # Proxy Sportsbook Line = Player's L10 healthy average prior to that game, rounded to nearest 0.5
            valid_prior = p_df[p_df["MIN"] >= 15].head(10)
            if len(valid_prior) < 5:
                continue
            proxy_line = round(valid_prior[stat].mean() * 2) / 2
            if proxy_line < 2.5:
                continue

            proj, lean, win_prob, *_ = calculate_projection(
                p_df, prior_logs, p_name, stat, opponent, proxy_line,
                teams_df, shot_df, track_df, dvp_table,
                out_players_set=set(), is_home=is_home
            )

            actual_val = float(game_row[stat])
            if actual_val == proxy_line:
                res = "PUSH"
            elif (lean == "OVER" and actual_val > proxy_line) or (lean == "UNDER" and actual_val < proxy_line):
                res = "WIN"
            else:
                res = "LOSS"

            day_candidates.append({
                "Date": g_date,
                "Player": p_name,
                "Opponent": opponent,
                "Stat": stat,
                "Pick": lean,
                "Book Line": proxy_line,
                "Model Proj": round(proj, 1),
                "Win Prob %": round(win_prob, 1),
                "Actual": actual_val,
                "Result": res
            })

    if day_candidates:
        day_df = pd.DataFrame(day_candidates).sort_values(by="Win Prob %", ascending=False)
        balanced_15 = pd.concat([
            day_df[day_df["Stat"] == "PTS"].head(5),
            day_df[day_df["Stat"] == "REB"].head(5),
            day_df[day_df["Stat"] == "AST"].head(5)
        ]).sort_values(by="Win Prob %", ascending=False)
        new_history_rows.append(balanced_15)

if new_history_rows:
    backfilled_df = pd.concat(new_history_rows, ignore_index=True)
    combined = pd.concat([backfilled_df, hist_df], ignore_index=True)
    combined = combined.sort_values(by=["Date", "Win Prob %"], ascending=[False, False])
    combined.to_csv(HISTORY_FILE, index=False)
    print(f"Successfully backfilled {len(backfilled_df)} graded picks across {len(all_game_dates)} missed days!")
