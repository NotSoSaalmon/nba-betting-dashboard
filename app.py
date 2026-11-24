import os
import json
import streamlit as st
import pandas as pd
from model_engine import load_all_data, calculate_projection, team_abbr_map
from nfl_engine import load_nfl_data, calculate_nfl_projection, nfl_abbr_map

st.set_page_config(page_title="Pro Betting Dashboard", layout="wide")
st.title("🏆 NBA & NFL Pro Betting Dashboard")

tab_nba, tab_nfl = st.tabs(["🏀 NBA PrizePicks & Track Record", "🏈 NFL Props (Thu/Sun/Mon)"])

with tab_nba:
    all_players_df, teams_df, shot_df, track_df, dvp_table, inj_df = load_all_data()
    all_names = sorted(all_players_df["PLAYER_NAME"].unique())
    default_out = [p for p in inj_df["PLAYER_NAME"].tolist() if p in all_names]

    with st.expander("🚨 Breaking Injury News (Tap to Add Late Scratches & Recalculate Usage)", expanded=False):
        selected_out = st.multiselect("Players Ruled OUT Tonight:", options=all_names, default=default_out)
    out_players_set = set(selected_out)

    st.header("🔥 NBA Top 16 Picks (4 PTS • 4 REB • 4 AST • 4 PRA)")
    stat_filter = st.radio("Filter NBA Leaderboard:", ["Balanced Top 16 (4 Each)", "All Combined", "PTS Only", "REB Only", "AST Only", "PRA Only"], horizontal=True)

    try:
        odds_df = pd.read_csv("live_odds.csv")
        if "FETCH_DATE" in odds_df.columns and not odds_df.empty:
            slate_dt = next(iter(odds_df["FETCH_DATE"]))
            st.caption(f"📅 **Active Slate Date:** {slate_dt} (Only showing games tipping off on this date)")
        edge_rows = []
        for _, row in odds_df.iterrows():
            p_name = row["PLAYER_NAME"]
            if p_name in out_players_set:
                continue
            stat, line = row["STAT"], row["LINE"]
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
                "Player": p_name, "Stat": stat, "Pick": lean, "Line": line, "Proj": round(proj, 1),
                "Win Prob": f"{win_prob:.1f}%", "_sort": win_prob,
                "Usage": usage_note if usage_note else "Normal",
                "Matchup / Tracking": fit_label, "DvP": dvp_label,
                "Opponent": opponent, "Rest": "B2B ⚠️" if is_b2b else "Rested",
                "Hit Rate": f"{hits}/{len(valid_10)}", "Book": row["BOOK"]
            })

        if edge_rows:
            full_df = pd.DataFrame(edge_rows).sort_values(by="_sort", ascending=False)
            if stat_filter == "Balanced Top 16 (4 Each)":
                disp = pd.concat([full_df[full_df["Stat"] == s].head(4) for s in ["PTS", "REB", "AST"]]).sort_values(by="_sort", ascending=False)
            elif stat_filter in ["PTS Only", "REB Only", "AST Only", "PRA Only"]:
                disp = full_df[full_df["Stat"] == next(iter(stat_filter.split(" ")))].head(15)
            else:
                disp = full_df.head(15)
            st.dataframe(disp.drop(columns=["_sort"]), use_container_width=True, hide_index=True)
        else:
            st.info("No matching NBA player props found yet.")
    except FileNotFoundError:
        st.warning("Run `fetch_odds.py` to load today's NBA lines.")

    st.divider()
    st.header("📈 NBA Track Record & Self-Calibration")
    if os.path.exists("pick_history.csv"):
        hist_df = pd.read_csv("pick_history.csv")
        graded = hist_df[hist_df["Result"].isin(["WIN", "LOSS"])]
        wins, losses = (graded["Result"] == "WIN").sum(), (graded["Result"] == "LOSS").sum()
        win_pct = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0.0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Overall Record", f"{wins}W - {losses}L")
        m2.metric("Win Rate (52.4% BE)", f"{win_pct:.1f}%")
        m3.metric("Pending Today", f"{(hist_df['Result'] == 'PENDING').sum()}")
        m4.metric("Total Tracked", f"{len(hist_df)}")

        if os.path.exists("model_weights.json") and len(graded) > 0:
            with open("model_weights.json", "r") as wf:
                w_data = json.load(wf)
            cat_rows = []
            for s in ["PTS", "REB", "AST", "PRA"]:
                for side in ["OVER", "UNDER"]:
                    sub = graded[(graded["Stat"] == s) & (graded["Pick"] == side)]
                    cw, cl = (sub["Result"] == "WIN").sum(), (sub["Result"] == "LOSS").sum()
                    cp = (cw / (cw + cl) * 100) if (cw + cl) > 0 else 0.0
                    mult = w_data.get(f"{s}_{side}", 1.0)
                    cat_rows.append({
                        "Category": f"{s} {side}", "Record": f"{cw}W - {cl}L",
                        "Win %": f"{cp:.1f}%" if (cw + cl) > 0 else "N/A",
                        "Model Weight": f"{mult:.2f}x"
                    })
            st.dataframe(pd.DataFrame(cat_rows), use_container_width=True, hide_index=True)
        st.dataframe(hist_df.head(45), use_container_width=True, hide_index=True)

with tab_nfl:
    st.header("🏈 NFL Top PrizePicks Edges (Thu / Sun / Mon)")
    st.caption("Automatically updates on NFL game days (Thu, Sun, Mon) to save free API credits • Weighs L3/L6 Form, Carries/Targets, DvP & Vegas Totals")

    if os.path.exists("nfl_player_logs.csv") and os.path.exists("nfl_live_odds.csv"):
        nfl_df, nfl_dvp = load_nfl_data()
        nfl_odds = pd.read_csv("nfl_live_odds.csv")
        nfl_rows = []

        for _, row in nfl_odds.iterrows():
            p_name, stat, line = row["PLAYER_NAME"], row["STAT"], row["LINE"]
            p_df = nfl_df[nfl_df["player_display_name"] == p_name]
            if len(p_df) < 3:
                continue

            team_abbr = next(iter(p_df["recent_team"]))
            team_full = nfl_abbr_map.get(team_abbr, "")
            opp_full = row["AWAY_TEAM"] if team_full == row["HOME_TEAM"] else row["HOME_TEAM"]

            proj, lean, win_prob, vol_note, dvp_label, hit_str = calculate_nfl_projection(
                p_df, stat, opp_full, line, nfl_dvp, game_total=row.get("GAME_TOTAL", 44.5)
            )
            nfl_rows.append({
                "Player": p_name, "Stat": stat, "Pick": lean, "Line": line, "Proj": round(proj, 1),
                "Win Prob": f"{win_prob:.1f}%", "_sort": win_prob,
                "Volume": vol_note, "DvP": dvp_label, "Opponent": opp_full,
                "L6 Hit Rate": hit_str, "Book": row["BOOK"]
            })

        if nfl_rows:
            nfl_top = pd.DataFrame(nfl_rows).sort_values(by="_sort", ascending=False).head(15).drop(columns=["_sort"])
            st.dataframe(nfl_top, use_container_width=True, hide_index=True)
        else:
            st.info("No matching NFL props found for the current slate.")
    else:
        st.info("NFL PrizePicks lines automatically load on **Thursdays, Sundays, and Mondays** at 5:00 AM (saving API credits on Tue/Wed/Fri/Sat).")


