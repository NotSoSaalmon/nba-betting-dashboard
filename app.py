import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="NBA Betting Dashboard", layout="wide")
st.title("🏀 NBA Pro Projection & Top 15 Edges")

all_players_df = pd.read_csv("all_player_logs.csv")
teams_df = pd.read_csv("team_ratings.csv")

all_players_df["GAME_DATE"] = pd.to_datetime(all_players_df["GAME_DATE"])
all_players_df["MIN"] = pd.to_numeric(all_players_df["MIN"], errors="coerce").fillna(0)
all_players_df = all_players_df.sort_values(by="GAME_DATE", ascending=False)

league_avg_pace = teams_df["PACE"].mean()
league_avg_opp_pts = teams_df["OPP_PTS"].mean()
league_avg_opp_reb = teams_df["OPP_REB"].mean()
league_avg_opp_ast = teams_df["OPP_AST"].mean()

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
full_to_abbr = {v: k for k, v in team_abbr_map.items()}

def calculate_pro_projection(p_df, stat, opp_name, is_home=True, game_total=226.0, spread=0.0):
    # 1. Filter out injury/blowout games (< 15 mins)
    valid_df = p_df[p_df["MIN"] >= 15]
    if len(valid_df) < 5:
        valid_df = p_df

    # 2. Per-Minute Efficiency Rate (L10 healthy games) x Projected Minutes (L5 healthy games)
    l10 = valid_df.head(10)
    l5_min = valid_df.head(5)["MIN"].mean()
    l10_min = l10["MIN"].mean()
    proj_min = (l5_min * 0.65) + (l10_min * 0.35)

    rate_per_min = l10[stat].sum() / l10["MIN"].sum() if l10["MIN"].sum() > 0 else 0
    rate_proj = rate_per_min * proj_min

    # Blend with raw L5/L10 average (60% rate-based, 40% raw average)
    raw_avg = (valid_df.head(5)[stat].mean() * 0.60) + (l10[stat].mean() * 0.40)
    baseline = (rate_proj * 0.60) + (raw_avg * 0.40)

    # 3. Home vs. Away Split Blending (25% weight)
    split_df = valid_df[valid_df["MATCHUP"].str.contains("vs." if is_home else "@", na=False)]
    if len(split_df) >= 3:
        baseline = (baseline * 0.75) + (split_df[stat].mean() * 0.25)

    # 4. Head-to-Head Matchup History (15% weight if played this opponent this season)
    opp_abbr = full_to_abbr.get(opp_name, "")
    if opp_abbr:
        h2h_df = valid_df[valid_df["MATCHUP"].str.contains(opp_abbr, na=False)]
        if len(h2h_df) >= 1:
            baseline = (baseline * 0.85) + (h2h_df[stat].mean() * 0.15)

    # 5. Stat-Specific Opponent Defense & Pace Adjustment
    opp_row = teams_df[teams_df["TEAM_NAME"] == opp_name]
    if opp_row.empty:
        matchup_factor = 1.0
    else:
        opp_stats = opp_row.squeeze()
        pace_ratio = opp_stats["PACE"] / league_avg_pace
        if stat == "PTS":
            stat_ratio = opp_stats["OPP_PTS"] / league_avg_opp_pts
        elif stat == "REB":
            stat_ratio = opp_stats["OPP_REB"] / league_avg_opp_reb
        else:
            stat_ratio = opp_stats["OPP_AST"] / league_avg_opp_ast
        # Combine pace and stat-specific allowance (dampened to avoid extreme swings)
        matchup_factor = 1 + ((pace_ratio - 1) * 0.4) + ((stat_ratio - 1) * 0.6)

    # 6. Vegas Game Total & Blowout Risk Factor
    total_factor = 1 + ((game_total - 226.0) / 226.0) * 0.5
    blowout_factor = 0.96 if spread >= 13.5 else 1.0

    # 7. Back-to-Back (B2B) Fatigue Check
    latest_game_date = p_df["GAME_DATE"].max().date()
    days_rest = (datetime.now().date() - latest_game_date).days
    is_b2b = (days_rest == 1)
    b2b_factor = 0.97 if is_b2b else 1.0

    final_proj = baseline * matchup_factor * total_factor * blowout_factor * b2b_factor
    return final_proj, is_b2b, round(proj_min, 1)

# --- SECTION 1: TOP 15 PICKS BY DIFFERENTIAL ---
st.header("🔥 Top 15 Picks (Pro Projection Model vs. Sportsbooks)")
st.caption("Model weighs: Per-Min Efficiency • Proj Minutes • Stat-Specific Defense • Pace • Vegas Total & Blowout Spread • Home/Away & H2H Splits • B2B Rest")

try:
    odds_df = pd.read_csv("live_odds.csv")
    edge_rows = []

    for _, row in odds_df.iterrows():
        p_name = row["PLAYER_NAME"]
        stat = row["STAT"]
        line = row["LINE"]
        g_total = row.get("GAME_TOTAL", 226.0)
        spread = row.get("SPREAD", 0.0)

        p_df = all_players_df[all_players_df["PLAYER_NAME"] == p_name]
        if len(p_df) < 5:
            continue

        player_team_abbr = next(iter(p_df["TEAM_ABBREVIATION"]))
        player_team_full = team_abbr_map.get(player_team_abbr, "")
        is_home = (player_team_full == row["HOME_TEAM"])
        opponent = row["AWAY_TEAM"] if is_home else row["HOME_TEAM"]

        proj, is_b2b, proj_min = calculate_pro_projection(
            p_df, stat, opponent, is_home=is_home, game_total=g_total, spread=spread
        )
        diff = proj - line
        lean = "OVER" if diff > 0 else "UNDER"

        valid_10 = p_df[p_df["MIN"] >= 15].head(10)
        if len(valid_10) < 5:
            valid_10 = p_df.head(10)
        hits = (valid_10[stat] > line).sum() if lean == "OVER" else (valid_10[stat] < line).sum()

        edge_rows.append({
            "Player": p_name,
            "Loc": "Home" if is_home else "Away",
            "Opponent": opponent,
            "Vegas O/U": g_total,
            "Rest": "B2B ⚠️" if is_b2b else "Rested",
            "Proj Min": proj_min,
            "Stat": stat,
            "Pick": lean,
            "Book Line": line,
            "Model Proj": round(proj, 1),
            "Differential": round(abs(diff), 1),
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
vegas_total = st.sidebar.number_input("Game Over/Under Total", value=226.0, step=0.5)
game_spread = st.sidebar.number_input("Point Spread (Abs)", value=4.5, step=0.5)
last_n = st.sidebar.slider("Last N Games", min_value=3, max_value=30, value=10)
opponent = st.sidebar.selectbox("Opponent", sorted(teams_df["TEAM_NAME"].unique()))

player_df = all_players_df[all_players_df["PLAYER_NAME"] == selected_player].copy()
player_df["GAME_DATE_STR"] = player_df["GAME_DATE"].dt.strftime("%Y-%m-%d")

recent = player_df.head(last_n)
hits = (recent[stat_choice] > line).sum()
hit_rate = (hits / len(recent)) * 100 if len(recent) > 0 else 0

projected_val, is_b2b, proj_min = calculate_pro_projection(
    player_df, stat_choice, opponent, is_home=(location_choice == "Home"),
    game_total=vegas_total, spread=game_spread
)
edge = projected_val - line
lean = "OVER" if edge > 0 else "UNDER"

col1, col2, col3, col4 = st.columns(4)
col1.metric(f"Projected {stat_choice} ({lean})", f"{projected_val:.1f}", f"{edge:+.1f} vs Line")
col2.metric(f"Last {last_n} Avg", f"{recent[stat_choice].mean():.1f}")
col3.metric("Hit Rate Over Line", f"{hit_rate:.0f}% ({hits}/{len(recent)})")
col4.metric("Projected Minutes", f"{proj_min} mpg", "B2B ⚠️" if is_b2b else "Normal Rest")

st.dataframe(recent[['GAME_DATE_STR', 'MATCHUP', 'MIN', 'PTS', 'REB', 'AST']].rename(columns={"GAME_DATE_STR": "DATE"}), use_container_width=True, hide_index=True)
