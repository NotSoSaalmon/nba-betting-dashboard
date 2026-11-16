import os
import json
import streamlit as st
import pandas as pd
from model_engine import load_all_data, calculate_projection, team_abbr_map

st.set_page_config(page_title="NBA Pro Betting Dashboard", layout="wide")
st.title("🏀 NBA Pro Projection & Win-Probability Edges")

all_players_df, teams_df, shot_df, track_df, dvp_table, inj_df = load_all_data()

all_names = sorted(all_players_df["PLAYER_NAME"].unique())
default_out = [p for p in inj_df["PLAYER_NAME"].tolist() if p in all_names]

with st.expander("🚨 Breaking Injury News (Tap to Add Late Scratches & Recalculate Usage)", expanded=False):
    selected_out = st.multiselect(
        "Players Ruled OUT Tonight (Boosts Teammate Usage & Removes Out Players):",
        options=all_names,
        default=default_out
    )
out_players_set = set(selected_out)

# --- SECTION 1: TOP 15 PICKS ---
st.header("🔥 Top 15 Picks (Top 5 PTS • Top 5 REB • Top 5 AST)")
st.caption("Self-Calibrating Model • Teammate Injury Usage • Potential Ast & Reb Chances • 3PT/2PT Shot Profile • DvP • Vegas Total & Spread • B2B Rest")

stat_filter = st.radio("Filter Leaderboard by Stat:", ["Balanced Top 15 (5 Each)", "All Combined", "PTS Only", "REB Only", "AST Only"], horizontal=True)

try:
    odds_df = pd.read_csv("live_odds.csv")
    edge_rows = []

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

        proj, lean, win_prob, pct_edge, is_b2b, proj_min, p_pos, dvp_label, fit_label, usage_note = calculate_projection(
            p_df, all_players_df, p_name, stat, opponent, line, teams_df, shot_df, track_df, dvp_table,
            out_players_set=out_players_set, is_home=is_home,
            game_total=row.get("GAME_TOTAL", 226.0), spread=row.get("SPREAD", 0.0)
        )

        valid_10 = p_df[p_df["MIN"] >= 15].head(10)
        if len(valid_10) < 5:
            valid_10 = p_df.head(10)
        hits = (valid_10[stat] > line).sum() if lean == "OVER" else (valid_10[stat] < line).sum()

        edge_rows.append({
            "Player": p_name,
            "Stat": stat,
            "Pick": lean,
            "Book Line": line,
            "Model Proj": round(proj, 1),
            "Win Prob": f"{win_prob:.1f}%",
            "_sort_prob": win_prob,
            "Usage Boost": usage_note if usage_note else "Normal",
            "Matchup / Tracking": fit_label,
            "DvP": dvp_label,
            "Opponent": opponent,
            "Rest": "B2B ⚠️" if is_b2b else "Rested",
            "Hit Rate": f"{hits}/{len(valid_10)}",
            "Book": row["BOOK"]
        })

    if edge_rows:
        full_edges_df = pd.DataFrame(edge_rows).sort_values(by="_sort_prob", ascending=False)

        if stat_filter == "Balanced Top 15 (5 Each)":
            pts_top = full_edges_df[full_edges_df["Stat"] == "PTS"].head(5)
            reb_top = full_edges_df[full_edges_df["Stat"] == "REB"].head(5)
            ast_top = full_edges_df[full_edges_df["Stat"] == "AST"].head(5)
            display_df = pd.concat([pts_top, reb_top, ast_top]).sort_values(by="_sort_prob", ascending=False)
        elif stat_filter == "PTS Only":
            display_df = full_edges_df[full_edges_df["Stat"] == "PTS"].head(15)
        elif stat_filter == "REB Only":
            display_df = full_edges_df[full_edges_df["Stat"] == "REB"].head(15)
        elif stat_filter == "AST Only":
            display_df = full_edges_df[full_edges_df["Stat"] == "AST"].head(15)
        else:
            display_df = full_edges_df.head(15)

        st.dataframe(display_df.drop(columns=["_sort_prob"]), use_container_width=True, hide_index=True)
    else:
        st.info("No matching player props found for tonight's slate yet.")

except FileNotFoundError:
    st.warning("Run `python fetch_odds.py` to load tonight's live sportsbook lines.")

st.divider()

# --- SECTION 2: AUTOMATED WIN-LOSS BACKTEST & SELF-CALIBRATION ---
st.header("📈 Model Track Record & Self-Calibration")
if os.path.exists("pick_history.csv"):
    hist_df = pd.read_csv("pick_history.csv")
    graded = hist_df[hist_df["Result"].isin(["WIN", "LOSS"])]
    wins = (graded["Result"] == "WIN").sum()
    losses = (graded["Result"] == "LOSS").sum()
    win_pct = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0.0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Overall Record", f"{wins}W - {losses}L")
    m2.metric("Win Rate (52.4% Break-Even)", f"{win_pct:.1f}%")
    m3.metric("Pending Today", f"{(hist_df['Result'] == 'PENDING').sum()} Picks")
    m4.metric("Total Tracked", f"{len(hist_df)} Picks")

    # Show Category Win Rates & Active Learned Multipliers
    if os.path.exists("model_weights.json") and len(graded) > 0:
        with open("model_weights.json", "r") as wf:
            w_data = json.load(wf)

        st.subheader("🧠 Learned Category Performance & Multipliers")
        cat_rows = []
        for s in ["PTS", "REB", "AST"]:
            for side in ["OVER", "UNDER"]:
                sub = graded[(graded["Stat"] == s) & (graded["Pick"] == side)]
                c_wins = (sub["Result"] == "WIN").sum()
                c_losses = (sub["Result"] == "LOSS").sum()
                c_pct = (c_wins / (c_wins + c_losses) * 100) if (c_wins + c_losses) > 0 else 0.0
                mult = w_data.get(f"{s}_{side}", 1.0)
                status = "🔥 Boosted" if mult > 1.0 else ("❄️ Dampened" if mult < 1.0 else "⚖️ Neutral")
                cat_rows.append({
                    "Category": f"{s} {side}",
                    "Record": f"{c_wins}W - {c_losses}L",
                    "Win %": f"{c_pct:.1f}%" if (c_wins + c_losses) > 0 else "N/A",
                    "Model Weight": f"{mult:.2f}x ({status})"
                })
        st.dataframe(pd.DataFrame(cat_rows), use_container_width=True, hide_index=True)

    st.subheader("Recent Graded & Pending Picks")
    st.dataframe(hist_df.head(45), use_container_width=True, hide_index=True)
else:
    st.info("Pick history will appear here automatically after your first morning update (`grade_picks.py`).")
