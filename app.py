import os
import streamlit as st
import pandas as pd
from model_engine import load_all_data, calculate_projection, team_abbr_map

st.set_page_config(page_title="NBA Pro Betting Dashboard", layout="wide")
st.title("🏀 NBA Pro Projection & Win-Probability Edges")

all_players_df, teams_df, shot_df, track_df, dvp_table = load_all_data()

# --- SECTION 1: TOP 15 PICKS (BALANCED ACROSS PTS, REB, AST) ---
st.header("🔥 Top 15 Picks (Top 5 PTS • Top 5 REB • Top 5 AST)")
st.caption("Balanced across Points, Rebounds & Assists • Ranked by True Win Probability %")

stat_filter = st.radio("Filter Leaderboard by Stat:", ["Balanced Top 15 (5 Each)", "All Combined", "PTS Only", "REB Only", "AST Only"], horizontal=True)

try:
    odds_df = pd.read_csv("live_odds.csv")
    edge_rows = []

    for _, row in odds_df.iterrows():
        p_name = row["PLAYER_NAME"]
        stat = row["STAT"]
        line = row["LINE"]
        p_df = all_players_df[all_players_df["PLAYER_NAME"] == p_name]
        if len(p_df) < 5:
            continue

        player_team_abbr = next(iter(p_df["TEAM_ABBREVIATION"]))
        player_team_full = team_abbr_map.get(player_team_abbr, "")
        is_home = (player_team_full == row["HOME_TEAM"])
        opponent = row["AWAY_TEAM"] if is_home else row["HOME_TEAM"]

        proj, lean, win_prob, pct_edge, is_b2b, proj_min, p_pos, dvp_label, fit_label = calculate_projection(
            p_df, p_name, stat, opponent, line, teams_df, shot_df, track_df, dvp_table,
            is_home=is_home, game_total=row.get("GAME_TOTAL", 226.0), spread=row.get("SPREAD", 0.0)
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
            "Edge %": f"{abs(pct_edge):.1f}%",
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

# --- SECTION 2: AUTOMATED WIN-LOSS BACKTEST TRACKER ---
st.header("📈 Model Track Record (Automated Daily Grading)")
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

    st.dataframe(hist_df.head(30), use_container_width=True, hide_index=True)
else:
    st.info("Pick history will appear here automatically after your first morning update (`grade_picks.py`).")

st.divider()

# --- SECTION 3: INDIVIDUAL PLAYER RESEARCH & TRACKING ---
st.header("🔍 Individual Player Prop, Shot Profile & Tracking Lookup")

st.sidebar.header("Individual Player Lookup")
player_list = sorted(all_players_df["PLAYER_NAME"].unique())
selected_player = st.sidebar.selectbox("Search or Select Player", player_list)
stat_choice = st.sidebar.selectbox("Select Stat", ["PTS", "REB", "AST"])
line = st.sidebar.number_input("Custom Line", value=20.5, step=0.5)
location_choice = st.sidebar.radio("Game Location", ["Home", "Away"])
vegas_total = st.sidebar.number_input("Game Over/Under Total", value=226.0, step=0.5)
game_spread = st.sidebar.number_input("Point Spread (Abs)", value=4.5, step=0.5)
last_n = st.sidebar.slider("Last N Games", min_value=3, max_value=30, value=10)
opponent = st.sidebar.selectbox("Opponent", sorted(teams_df["TEAM_NAME"].unique()))

player_df = all_players_df[all_players_df["PLAYER_NAME"] == selected_player].copy()
player_df["GAME_DATE_STR"] = player_df["GAME_DATE"].dt.strftime("%Y-%m-%d")
recent = player_df.head(last_n)

projected_val, lean, win_prob, pct_edge, is_b2b, proj_min, p_pos, dvp_label, fit_label = calculate_projection(
    player_df, selected_player, stat_choice, opponent, line, teams_df, shot_df, track_df, dvp_table,
    is_home=(location_choice == "Home"), game_total=vegas_total, spread=game_spread
)

col1, col2, col3, col4 = st.columns(4)
col1.metric(f"Projected {stat_choice} ({lean})", f"{projected_val:.1f}", f"{win_prob:.1f}% Win Prob")
col2.metric(f"Last {last_n} Avg", f"{recent[stat_choice].mean():.1f}", f"{pct_edge:+.1f}% Edge vs Line")
col3.metric(f"DvP ({p_pos})", dvp_label)
col4.metric("Projected Minutes", f"{proj_min} mpg", "B2B ⚠️" if is_b2b else "Normal Rest")

t_player = track_df[track_df["PLAYER_NAME"] == selected_player]
if not t_player.empty:
    tp = t_player.squeeze()
    tc1, tc2 = st.columns(2)
    tc1.info(f"**Rebounding Volume:** {tp['REB_CHANCES']:.1f} Rebound Chances/game (Actual: {tp['REB']:.1f} REB/g)")
    tc2.info(f"**Passing Volume:** {tp['POTENTIAL_AST']:.1f} Potential Assists/game (Actual: {tp['AST']:.1f} AST/g)")

p_shot_row = shot_df[shot_df["PLAYER_NAME"] == selected_player]
opp_team_row = teams_df[teams_df["TEAM_NAME"] == opponent]
if not p_shot_row.empty and not opp_team_row.empty:
    ps = p_shot_row.squeeze()
    os_row = opp_team_row.squeeze()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader(f"🎯 {selected_player} Scoring Breakdown")
        chart_data = pd.DataFrame({
            "Scoring Source": ["3-Pointers", "2-Pointers (Total)", "Points in Paint", "Free Throws"],
            "Share (%)": [
                round(ps["PCT_PTS_3PT"] * 100, 1),
                round(ps["PCT_PTS_2PT"] * 100, 1),
                round(ps["PCT_PTS_PAINT"] * 100, 1),
                round(ps["PCT_PTS_FT"] * 100, 1)
            ]
        }).set_index("Scoring Source")
        st.bar_chart(chart_data)
    with c2:
        st.subheader(f"🛡️ {opponent} Zone Defense Allowed")
        rank_3 = int(teams_df["OPP_FG3M"].rank(ascending=False)[teams_df["TEAM_NAME"] == opponent].values)
        rank_2 = int(teams_df["OPP_FG2M"].rank(ascending=False)[teams_df["TEAM_NAME"] == opponent].values)
        st.metric("Opponent 3PM Allowed / Game", f"{os_row['OPP_FG3M']:.1f}", f"#{rank_3} Most 3s Allowed (1=Softest)")
        st.metric("Opponent 2PM Allowed / Game", f"{os_row['OPP_FG2M']:.1f}", f"#{rank_2} Most 2s Allowed (1=Softest)")

st.dataframe(recent[['GAME_DATE_STR', 'MATCHUP', 'MIN', 'PTS', 'REB', 'AST']].rename(columns={"GAME_DATE_STR": "DATE"}), use_container_width=True, hide_index=True)
