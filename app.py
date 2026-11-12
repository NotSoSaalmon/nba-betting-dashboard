import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="NBA Betting Dashboard", layout="wide")
st.title("🏀 NBA Betting Analytics & Top 15 Edges")

# Load cached CSV files
all_players_df = pd.read_csv("all_player_logs.csv")
teams_df = pd.read_csv("team_ratings.csv")

# Clean and sort dates & minutes
all_players_df["GAME_DATE"] = pd.to_datetime(all_players_df["GAME_DATE"])
all_players_df["MIN"] = pd.to_numeric(all_players_df["MIN"], errors="coerce").fillna(0)
all_players_df = all_players_df.sort_values(by="GAME_DATE", ascending=False)

league_avg_pace = teams_df["PACE"].mean()
league_avg_def = teams_df["DEF_RATING"].mean()

team_abbr_map = {
    "ATL": "Atlanta Hawks", "BOS": "Boston Celtics", "BKN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets", "CHI": "Chicago Bulls", "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks", "DEN": "Denver Nuggets", "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors", "HOU": "Houston Rockets", "IND": "Indiana Pacers",
    "LAC": "LA Clippers", "LAL": "Los Angeles Lakers", "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat", "MIL": "Milwaukee Bucks", "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans", "NYK": "New York Knicks", "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic", "PHI": "Philadelphia 76ers", "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers", "SAC": "Sacramento Kings", "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors", "UTA": "Utah Jazz", "WAS": "Washington Wizards"
}

def calculate_projection(p_df, stat, opp_name, is_home=True, min_minutes=15):
    # 1. Filter out early-injury / blowout games (< 15 mins)
    valid_df = p_df[p_df["MIN"] >= min_minutes]
    if len(valid_df) < 5:
        valid_df = p_df  # Fallback for bench players who normally play < 15 mins

    # 2. Recent Form Baseline (60% L5, 40% L10)
    avg_5 = valid_df.head(5)[stat].mean()
    avg_10 = valid_df.head(10)[stat].mean()
    recent_baseline = (avg_5 * 0.60) + (avg_10 * 0.40)

    # 3. Home vs. Away Split Blending (30% weight on location split)
    if is_home:
        split_df = valid_df[valid_df["MATCHUP"].str.contains("vs.", na=False)]
    else:
        split_df = valid_df[valid_df["MATCHUP"].str.contains("@", na=False)]

    if len(split_df) >= 3:
        split_avg = split_df[stat].mean()
        baseline = (recent_baseline * 0.70) + (split_avg * 0.30)
    else:
        baseline = recent_baseline

    # 4. Minutes Trend Factor (Captures recent role/injury usage boosts)
    min_5 = valid_df.head(5)["MIN"].mean()
    min_15 = valid_df.head(15)["MIN"].mean()
    if min_15 > 0:
        min_ratio = min_5 / min_15
        # Cap minutes swing between -15% and +15% to prevent extreme outliers
        min_factor = max(0.85, min(1.15, 1 + (min_ratio - 1) * 0.75))
    else:
        min_factor = 1.0

    # 5. Back-to-Back (B2B) Fatigue Check
    latest_game_date = p_df["GAME_DATE"].max().date()
    today_date = datetime.now().date()
    days_rest = (today_date - latest_game_date).days
    b2b_factor = 0.97 if days_rest == 1 else 1.0
    is_b2b = (days_rest == 1)

    # 6. Opponent Pace & Defense Factors
    opp_row = teams_df[teams_df["TEAM_NAME"] == opp_name]
    if opp_row.empty:
        pace_factor, def_factor = 1.0, 1.0
    else:
        opp_stats = opp_row.squeeze()
        pace_factor = opp_stats["PACE"] / league_avg_pace
        def_factor = 1 + ((opp_stats["DEF_RATING"] / league_avg_def) - 1) * 0.5

    final_proj = baseline * min_factor * b2b_factor * pace_factor * def_factor
    return final_proj, is_b2b, round(min_5, 1)

# --- SECTION 1: TOP 15 PICKS BY DIFFERENTIAL ---
st.header("🔥 Top 15 Picks (Upgraded Model vs. Sportsbooks)")
st.caption("Factors in: L5/L10 Form • Home/Away Splits • Minutes Trend • Back-to-Back Rest • Opponent Pace & Defense (Excludes <15 min injury games)")

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

        # Determine if player is Home or Away tonight
        is_home = (player_team_full == row["HOME_TEAM"])
        opponent = row["AWAY_TEAM"] if is_home else row["HOME_TEAM"]
        loc_tag = "Home" if is_home else "Away"

        proj, is_b2b, l5_min = calculate_projection(p_df, stat, opponent, is_home=is_home)
        diff = proj - line
        abs_diff = abs(diff)
        lean = "OVER" if diff > 0 else "UNDER"

        # Calculate L10 hit rate (excluding <15 min injury games)
        valid_10 = p_df[p_df["MIN"] >= 15].head(10)
        if len(valid_10) < 5:
            valid_10 = p_df.head(10)
        hits = (valid_10[stat] > line).sum() if lean == "OVER" else (valid_10[stat] < line).sum()

        edge_rows.append({
            "Player": p_name,
            "Loc": loc_tag,
            "Opponent": opponent,
            "Rest": "B2B ⚠️" if is_b2b else "Rested",
            "L5 Min": l5_min,
            "Stat": stat,
            "Pick": lean,
            "Book Line": line,
            "Model Proj": round(proj, 1),
            "Differential": round(abs_diff, 1),
            "Edge (+/-)": round(diff, 1),
            "Hit Rate": f"{hits}/{len(valid_10)}",
            "Book": row["BOOK"]
        })

    if edge_rows:
        top_15_df = pd.DataFrame(edge_rows).sort_values(by="Differential", ascending=False).head(15)
        st.dataframe(top_15_df, use_container_width=True, hide_index=True)
    else:
        st.info("No matching player props found for tonight's slate yet.")

except FileNotFoundError:
    st.warning("Run `python fetch_odds.py` to load tonight's live sportsbook lines.")

st.divider()

# --- SECTION 2: INDIVIDUAL PLAYER RESEARCH ---
st.header("🔍 Individual Player Prop Lookup")

st.sidebar.header("Individual Player Lookup")
player_list = sorted(all_players_df["PLAYER_NAME"].unique())
selected_player = st.sidebar.selectbox("Search or Select Player", player_list)
stat_choice = st.sidebar.selectbox("Select Stat", ["PTS", "REB", "AST"])
line = st.sidebar.number_input("Custom Line", value=20.5, step=0.5)
location_choice = st.sidebar.radio("Game Location", ["Home", "Away"])
last_n = st.sidebar.slider("Last N Games", min_value=3, max_value=30, value=10)
opponent = st.sidebar.selectbox("Opponent", sorted(teams_df["TEAM_NAME"].unique()))

player_df = all_players_df[all_players_df["PLAYER_NAME"] == selected_player].copy()
player_df["GAME_DATE_STR"] = player_df["GAME_DATE"].dt.strftime("%Y-%m-%d")

recent = player_df.head(last_n)
hits = (recent[stat_choice] > line).sum()
hit_rate = (hits / len(recent)) * 100 if len(recent) > 0 else 0

projected_val, is_b2b, l5_min = calculate_projection(
    player_df, stat_choice, opponent, is_home=(location_choice == "Home")
)
edge = projected_val - line
lean = "OVER" if edge > 0 else "UNDER"

col1, col2, col3, col4 = st.columns(4)
col1.metric(f"Projected {stat_choice} ({lean})", f"{projected_val:.1f}", f"{edge:+.1f} vs Line")
col2.metric(f"Last {last_n} Avg", f"{recent[stat_choice].mean():.1f}")
col3.metric("Hit Rate Over Line", f"{hit_rate:.0f}% ({hits}/{len(recent)})")
col4.metric("L5 Minutes Avg", f"{l5_min} mpg", "B2B ⚠️" if is_b2b else "Normal Rest")

st.dataframe(recent[['GAME_DATE_STR', 'MATCHUP', 'MIN', 'PTS', 'REB', 'AST']].rename(columns={"GAME_DATE_STR": "DATE"}), use_container_width=True, hide_index=True)
