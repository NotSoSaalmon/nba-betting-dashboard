import math
import pandas as pd

nfl_abbr_map = {
    "ARI": "Arizona Cardinals", "ATL": "Atlanta Falcons", "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills", "CAR": "Carolina Panthers", "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns", "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos", "DET": "Detroit Lions", "GB": "Green Bay Packers",
    "HOU": "Houston Texans", "IND": "Indianapolis Colts", "JAX": "Jacksonville Jaguars",
    "KC": "Kansas City Chiefs", "LV": "Las Vegas Raiders", "LAC": "Los Angeles Chargers",
    "LA": "Los Angeles Rams", "MIA": "Miami Dolphins", "MIN": "Minnesota Vikings",
    "NE": "New England Patriots", "NO": "New Orleans Saints", "NYG": "New York Giants",
    "NYJ": "New York Jets", "PHI": "Philadelphia Eagles", "PIT": "Pittsburgh Steelers",
    "SF": "San Francisco 49ers", "SEA": "Seattle Seahawks", "TB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans", "WAS": "Washington Commanders"
}
nfl_full_to_abbr = {v: k for k, v in nfl_abbr_map.items()}

stat_col_map = {
    "PASS_YDS": "passing_yards",
    "RUSH_YDS": "rushing_yards",
    "REC_YDS": "receiving_yards"
}

def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def load_nfl_data(base_path=""):
    df = pd.read_csv(f"{base_path}nfl_player_logs.csv")
    df = df.sort_values(by="week", ascending=False)
    # Build Defense vs Position table (avg yards allowed per game by opponent & position)
    dvp = df.groupby(["opponent_team", "position"])[["passing_yards", "rushing_yards", "receiving_yards"]].mean().reset_index()
    lg_avg = df.groupby("position")[["passing_yards", "rushing_yards", "receiving_yards"]].mean().reset_index()
    lg_avg = lg_avg.rename(columns={
        "passing_yards": "lg_pass", "rushing_yards": "lg_rush", "receiving_yards": "lg_rec"
    })
    dvp_table = pd.merge(dvp, lg_avg, on="position")
    return df, dvp_table

def calculate_nfl_projection(p_df, stat_code, opp_full, line, dvp_table, game_total=44.5):
    col = stat_col_map[stat_code]
    pos = next(iter(p_df["position"])) if not p_df.empty else "WR"

    # Weighted Recent Form (60% Last 3 weeks, 40% Last 6 weeks)
    avg_3 = p_df.head(3)[col].mean()
    avg_6 = p_df.head(6)[col].mean()
    baseline = (avg_3 * 0.60) + (avg_6 * 0.40)

    # Opportunity Volume Note (Carries or Targets)
    if stat_code == "RUSH_YDS":
        vol = p_df.head(4)["carries"].mean()
        vol_note = f"{vol:.1f} Carries/g"
    elif stat_code == "REC_YDS":
        vol = p_df.head(4)["targets"].mean()
        vol_note = f"{vol:.1f} Targets/g"
    else:
        vol = p_df.head(4)["attempts"].mean()
        vol_note = f"{vol:.1f} Pass Att/g"

    # Opponent Defense vs Position Adjustment
    opp_abbr = nfl_full_to_abbr.get(opp_full, "")
    dvp_row = dvp_table[(dvp_table["opponent_team"] == opp_abbr) & (dvp_table["position"] == pos)]
    adj_pct = 0.0
    dvp_label = f"🟡 Neutral vs {pos}"

    if not dvp_row.empty:
        r = dvp_row.squeeze()
        lg_col = {"passing_yards": "lg_pass", "rushing_yards": "lg_rush", "receiving_yards": "lg_rec"}[col]
        if r[lg_col] > 0:
            ratio = r[col] / r[lg_col]
            adj_pct += (ratio - 1.0) * 0.40
            pct_diff = (ratio - 1.0) * 100
            if pct_diff >= 5.0:
                dvp_label = f"🟢 Soft vs {pos} ({pct_diff:+.0f}%)"
            elif pct_diff <= -5.0:
                dvp_label = f"🔴 Tough vs {pos} ({pct_diff:+.0f}%)"

    # Vegas Game Total Adjustment (44.5 league avg)
    adj_pct += ((game_total - 44.5) / 44.5) * 0.35
    adj_pct = max(-0.15, min(0.15, adj_pct))

    raw_proj = baseline * (1.0 + adj_pct)
    # 55% Model / 45% Line market shrinkage
    final_proj = (raw_proj * 0.55) + (line * 0.45)

    # Realistic NFL volatility floors
    min_stds = {"PASS_YDS": 48.0, "RUSH_YDS": 22.0, "REC_YDS": 24.0}
    s_std = p_df.head(8)[col].std()
    floor = max(min_stds[stat_code], line * 0.30)
    std_dev = floor if pd.isna(s_std) else max(s_std, floor)

    z = (final_proj - line) / std_dev
    p_over = norm_cdf(z)
    if final_proj >= line:
        lean, win_prob = "OVER", p_over * 100
    else:
        lean, win_prob = "UNDER", (1.0 - p_over) * 100

    # L6 Hit-Rate & Median Quality Gate
    l6 = p_df.head(6)[col]
    hits = (l6 > line).sum() if lean == "OVER" else (l6 < line).sum()
    med_agrees = (l6.median() > line) if lean == "OVER" else (l6.median() < line)
    if hits < 3 or not med_agrees:
        win_prob = 50.0 + ((win_prob - 50.0) * 0.80)

    win_prob = max(50.5, min(66.0, win_prob))
    return final_proj, lean, win_prob, vol_note, dvp_label, f"{hits}/{len(l6)}"
