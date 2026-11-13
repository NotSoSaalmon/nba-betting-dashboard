import math
import pandas as pd
from datetime import datetime

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

def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def load_all_data(base_path=""):
    all_players_df = pd.read_csv(f"{base_path}all_player_logs.csv")
    teams_df = pd.read_csv(f"{base_path}team_ratings.csv")
    pos_df = pd.read_csv(f"{base_path}player_positions.csv")
    shot_df = pd.read_csv(f"{base_path}player_shot_profile.csv")
    try:
        track_df = pd.read_csv(f"{base_path}player_tracking.csv")
    except FileNotFoundError:
        track_df = pd.DataFrame(columns=["PLAYER_NAME", "REB", "REB_CHANCES", "AST", "POTENTIAL_AST"])

    all_players_df["GAME_DATE"] = pd.to_datetime(all_players_df["GAME_DATE"])
    all_players_df["MIN"] = pd.to_numeric(all_players_df["MIN"], errors="coerce").fillna(0)
    all_players_df = all_players_df.sort_values(by="GAME_DATE", ascending=False)

    pos_map = dict(zip(pos_df["PLAYER_NAME"], pos_df["POS"]))
    all_players_df["POS"] = all_players_df["PLAYER_NAME"].map(pos_map).fillna("G")
    all_players_df["OPP_ABBR"] = all_players_df["MATCHUP"].apply(lambda x: str(x).split(" ")[-1])

    dvp_logs = all_players_df[all_players_df["MIN"] >= 15].copy()
    dvp_grouped = dvp_logs.groupby(["OPP_ABBR", "POS"])[["MIN", "PTS", "REB", "AST"]].sum().reset_index()
    for s in ["PTS", "REB", "AST"]:
        dvp_grouped[f"{s}_PER_MIN"] = dvp_grouped[s] / dvp_grouped["MIN"]

    league_pos_avg = dvp_logs.groupby("POS")[["MIN", "PTS", "REB", "AST"]].sum().reset_index()
    for s in ["PTS", "REB", "AST"]:
        league_pos_avg[f"LG_{s}_PER_MIN"] = league_pos_avg[s] / league_pos_avg["MIN"]

    dvp_table = pd.merge(dvp_grouped, league_pos_avg[["POS", "LG_PTS_PER_MIN", "LG_REB_PER_MIN", "LG_AST_PER_MIN"]], on="POS")

    return all_players_df, teams_df, shot_df, track_df, dvp_table

def calculate_projection(p_df, player_name, stat, opp_name, line, teams_df, shot_df, track_df, dvp_table, is_home=True, game_total=226.0, spread=0.0):
    player_pos = next(iter(p_df["POS"])) if not p_df.empty else "G"
    valid_df = p_df[p_df["MIN"] >= 15]
    if len(valid_df) < 5:
        valid_df = p_df

    l10 = valid_df.head(10)
    l5_min = valid_df.head(5)["MIN"].mean()
    l10_min = l10["MIN"].mean()
    proj_min = (l5_min * 0.65) + (l10_min * 0.35)

    rate_per_min = l10[stat].sum() / l10["MIN"].sum() if l10["MIN"].sum() > 0 else 0
    rate_proj = rate_per_min * proj_min
    raw_avg = (valid_df.head(5)[stat].mean() * 0.60) + (l10[stat].mean() * 0.40)
    baseline = (rate_proj * 0.60) + (raw_avg * 0.40)

    # Tracking Opportunity Blend
    t_row = track_df[track_df["PLAYER_NAME"] == player_name]
    opp_volume_note = ""
    if not t_row.empty:
        tr = t_row.squeeze()
        if stat == "REB" and tr["REB_CHANCES"] > 0:
            expected_reb = tr["REB_CHANCES"] * 0.56
            baseline = (baseline * 0.70) + (expected_reb * 0.30)
            opp_volume_note = f"{tr['REB_CHANCES']:.1f} Reb Chances/g"
        elif stat == "AST" and tr["POTENTIAL_AST"] > 0:
            expected_ast = tr["POTENTIAL_AST"] * 0.52
            baseline = (baseline * 0.70) + (expected_ast * 0.30)
            opp_volume_note = f"{tr['POTENTIAL_AST']:.1f} Pot Ast/g"

    # Home vs. Away Split
    split_df = valid_df[valid_df["MATCHUP"].str.contains("vs." if is_home else "@", na=False)]
    if len(split_df) >= 3:
        baseline = (baseline * 0.80) + (split_df[stat].mean() * 0.20)

    # Head-to-Head History
    opp_abbr = full_to_abbr.get(opp_name, "")
    if opp_abbr:
        h2h_df = valid_df[valid_df["MATCHUP"].str.contains(opp_abbr, na=False)]
        if len(h2h_df) >= 1:
            baseline = (baseline * 0.85) + (h2h_df[stat].mean() * 0.15)

    # Additive & Capped Matchup Adjustments (Prevents compounding inflation)
    adj_pct = 0.0

    opp_row = teams_df[teams_df["TEAM_NAME"] == opp_name]
    if not opp_row.empty:
        opp_stats = opp_row.squeeze()
        pace_diff = (opp_stats["PACE"] / teams_df["PACE"].mean()) - 1.0
        if stat == "PTS":
            stat_diff = (opp_stats["OPP_PTS"] / teams_df["OPP_PTS"].mean()) - 1.0
        elif stat == "REB":
            stat_diff = (opp_stats["OPP_REB"] / teams_df["OPP_REB"].mean()) - 1.0
        else:
            stat_diff = (opp_stats["OPP_AST"] / teams_df["OPP_AST"].mean()) - 1.0
        adj_pct += (pace_diff * 0.30) + (stat_diff * 0.25)

    # DvP Adjustment
    dvp_row = dvp_table[(dvp_table["OPP_ABBR"] == opp_abbr) & (dvp_table["POS"] == player_pos)]
    if dvp_row.empty:
        dvp_label = "Neutral"
    else:
        r = dvp_row.squeeze()
        lg_rate = r[f"LG_{stat}_PER_MIN"]
        ratio = r[f"{stat}_PER_MIN"] / lg_rate if lg_rate > 0 else 1.0
        adj_pct += (ratio - 1.0) * 0.35
        dvp_label = f"{(ratio - 1)*100:+.1f}% vs {player_pos}"

    # Shot Zone Adjustment (for PTS)
    p_shot = shot_df[shot_df["PLAYER_NAME"] == player_name]
    shot_label = "Standard"
    if not p_shot.empty and not opp_row.empty:
        ps = p_shot.squeeze()
        os = opp_row.squeeze()
        pct_3, pct_2 = ps["PCT_PTS_3PT"], ps["PCT_PTS_2PT"]
        if pct_3 >= 0.42:
            style = f"3PT ({pct_3*100:.0f}%)"
        elif ps["PCT_PTS_PAINT"] >= 0.55:
            style = f"Paint ({ps['PCT_PTS_PAINT']*100:.0f}%)"
        else:
            style = f"Balanced ({pct_2*100:.0f}% 2P)"

        if stat == "PTS":
            ratio_3 = os["OPP_FG3M"] / teams_df["OPP_FG3M"].mean()
            ratio_2 = os["OPP_FG2M"] / teams_df["OPP_FG2M"].mean()
            total_fg = pct_3 + pct_2
            w_ratio = ((pct_3 * ratio_3) + (pct_2 * ratio_2)) / total_fg if total_fg > 0 else 1.0
            adj_pct += (w_ratio - 1.0) * 0.40
            shot_label = f"{style} [{(w_ratio - 1)*100:+.1f}%]"
        else:
            shot_label = opp_volume_note if opp_volume_note else style

    # Vegas Total, Blowout, & B2B Rest
    adj_pct += ((game_total - 226.0) / 226.0) * 0.35
    if spread >= 13.5:
        adj_pct -= 0.035
    latest_game_date = p_df["GAME_DATE"].max().date()
    is_b2b = ((datetime.now().date() - latest_game_date).days == 1)
    if is_b2b:
        adj_pct -= 0.025

    # Cap total matchup swing at +/- 15%
    adj_pct = max(-0.15, min(0.15, adj_pct))
    raw_model_proj = baseline * (1.0 + adj_pct)

    # Market-Aware Shrinkage: Anchor 25% to sportsbook line to prevent outlier inflation
    final_proj = (raw_model_proj * 0.75) + (line * 0.25)

    # Full-Season Volatility with Realistic NBA Floors
    min_std_floors = {"PTS": 5.5, "REB": 2.6, "AST": 2.1}
    season_std = valid_df[stat].std()
    floor_std = max(min_std_floors.get(stat, 2.5), line * 0.24)
    std_dev = floor_std if pd.isna(season_std) else max(season_std, floor_std)

    z_score = (final_proj - line) / std_dev
    prob_over = norm_cdf(z_score)
    if final_proj >= line:
        lean = "OVER"
        win_prob = prob_over * 100
    else:
        lean = "UNDER"
        win_prob = (1.0 - prob_over) * 100

    # Cap displayed probability at 72% (realistic ceiling for NBA player props)
    win_prob = min(72.0, win_prob)
    pct_edge = ((final_proj - line) / line) * 100 if line > 0 else 0
    return final_proj, lean, win_prob, pct_edge, is_b2b, round(proj_min, 1), player_pos, dvp_label, shot_label
