import streamlit as st
import pandas as pd

st.set_page_config(page_title="NBA Betting Dashboard", layout="wide")
st.title("🏀 NBA Betting Analytics & Top 15 Edges")

# Load cached CSV files
all_players_df = pd.read_csv("all_player_logs.csv")
teams_df = pd.read_csv("team_ratings.csv")

all_players_df["GAME_DATE"] = pd.to_datetime(all_players_df["GAME_DATE"])
all_players_df = all_players_df.sort_values(by="GAME_DATE", ascending=False)

league_avg_pace = teams_df["PACE"].mean()
league_avg_def = teams_df["DEF_RATING"].mean()

# Map team abbreviations from logs to full team names for opponent matching
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

def calculate_projection(p_df, stat, opp_name):
    avg_5 = p_df.head(5)[stat].mean()
    avg_10 = p_df.head(10)[stat].mean()
    baseline = (avg_5 * 0.6) + (avg_10 * 0.4)
    
    opp_row = teams_df[teams_df["TEAM_NAME"] == opp_name]
    if opp_row.empty:
        return baseline
    
    opp_stats = opp_row.squeeze()
    pace_factor = opp_stats["PACE"] / league_avg_pace
    def_factor = opp_stats["DEF_RATING"] / league_avg_def
    return baseline * pace_factor * (1 + (def_factor - 1) * 0.5)

# --- SECTION 1: TOP 15 PICKS BY DIFFERENTIAL ---
st.header("🔥 Top 15 Picks (Highest Differential vs. Sportsbooks)")

try:
    odds_df = pd.read_csv("live_odds.csv")
    edge_rows = []

    for _, row in odds_df.iterrows():
        p_name = row["PLAYER_NAME"]
        stat = row["STAT"]
        line = row["LINE"]
        
        p_df = all_players_df[all_players_df["PLAYER_NAME"] == p_name]
        if len(p_df) < 5:
            continue  # Skip players without at least 5 recent games
        
        # Determine player's current team & tonight's opponent
        player_team_abbr = next(iter(p_df["TEAM_ABBREVIATION"]))
        player_team_full = team_abbr_map.get(player_team_abbr, "")
        opponent = row["AWAY_TEAM"] if player_team_full == row["HOME_TEAM"] else row["HOME_TEAM"]
        
        proj = calculate_projection(p_df, stat, opponent)
        diff = proj - line
        abs_diff = abs(diff)
        lean = "OVER" if diff > 0 else "UNDER"
        
        # Calculate L10 hit rate for that specific side
        recent_10 = p_df.head(10)
        hits = (recent_10[stat] > line).sum() if lean == "OVER" else (recent_10[stat] < line).sum()
        
        edge_rows.append({
            "Player": p_name,
            "Opponent": opponent,
            "Stat": stat,
            "Pick": lean,
            "Book Line": line,
            "Model Proj": round(proj, 1),
            "Differential": round(abs_diff, 1),
            "Edge (+/-)": round(diff, 1),
            "L10 Hit Rate": f"{hits}/10 ({hits*10}%)",
            "Book": row["BOOK"]
        })

    if edge_rows:
        top_15_df = pd.DataFrame(edge_rows).sort_values(by="Differential", ascending=False).head(15)
        st.dataframe(top_15_df, use_container_width=True, hide_index=True)
    else:
        st.info("No matching player props found for tonight's slate yet.")

except FileNotFoundError:
    st.warning("Run `python fetch_odds.py` in Terminal to load tonight's live sportsbook lines.")

st.divider()

# --- SECTION 2: INDIVIDUAL PLAYER RESEARCH ---
st.header("🔍 Individual Player Prop Lookup")

st.sidebar.header("Individual Player Lookup")
player_list = sorted(all_players_df["PLAYER_NAME"].unique())
selected_player = st.sidebar.selectbox("Search or Select Player", player_list)
stat_choice = st.sidebar.selectbox("Select Stat", ["PTS", "REB", "AST"])
line = st.sidebar.number_input("Custom Line", value=20.5, step=0.5)
last_n = st.sidebar.slider("Last N Games", min_value=3, max_value=30, value=10)
opponent = st.sidebar.selectbox("Opponent", sorted(teams_df["TEAM_NAME"].unique()))

player_df = all_players_df[all_players_df["PLAYER_NAME"] == selected_player].copy()
player_df["GAME_DATE"] = player_df["GAME_DATE"].dt.strftime("%Y-%m-%d")

recent = player_df.head(last_n)
hits = (recent[stat_choice] > line).sum()
hit_rate = (hits / len(recent)) * 100 if len(recent) > 0 else 0

projected_val = calculate_projection(player_df, stat_choice, opponent)
edge = projected_val - line
lean = "OVER" if edge > 0 else "UNDER"

col1, col2, col3, col4 = st.columns(4)
col1.metric(f"Projected {stat_choice} ({lean})", f"{projected_val:.1f}", f"{edge:+.1f} vs Line")
col2.metric(f"Last {last_n} Avg", f"{recent[stat_choice].mean():.1f}")
col3.metric("Hit Rate Over Line", f"{hit_rate:.0f}% ({hits}/{len(recent)})")
col4.metric("Median", f"{recent[stat_choice].median():.1f}")

st.dataframe(recent[['GAME_DATE', 'MATCHUP', 'MIN', 'PTS', 'REB', 'AST']], use_container_width=True, hide_index=True)
