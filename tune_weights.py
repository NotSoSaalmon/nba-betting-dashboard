import os
import json
import pandas as pd

BASE = "/Users/rasheedwhiters/nba_project/"
HISTORY_FILE = f"{BASE}pick_history.csv"
WEIGHTS_FILE = f"{BASE}model_weights.json"

weights = {
    "PTS_OVER": 1.0, "PTS_UNDER": 1.0,
    "REB_OVER": 1.0, "REB_UNDER": 1.0,
    "AST_OVER": 1.0, "AST_UNDER": 1.0,
    "win_rates": {},
    "global_bias_adj": 0.0,
    "sample_size": 0
}

if os.path.exists(HISTORY_FILE):
    df = pd.read_csv(HISTORY_FILE)
    graded = df[df["Result"].isin(["WIN", "LOSS"])].copy()
    weights["sample_size"] = int(len(graded))

    if len(graded) >= 15:
        for stat in ["PTS", "REB", "AST", "PRA"]:
            for side in ["OVER", "UNDER"]:
                sub = graded[(graded["Stat"] == stat) & (graded["Pick"] == side)]
                if len(sub) >= 10:
                    win_rate = (sub["Result"] == "WIN").mean()
                    weights["win_rates"][f"{stat}_{side}"] = round(win_rate * 100, 1)
                    # Center target at 58% instead of 52.4% so sub-60% categories get noticeably dampened
                    diff_from_target = win_rate - 0.58
                    mult = 1.0 + (diff_from_target * 0.85)
                    weights[f"{stat}_{side}"] = round(max(0.85, min(1.15, mult)), 4)

        graded["Actual"] = pd.to_numeric(graded["Actual"], errors="coerce")
        graded["Model Proj"] = pd.to_numeric(graded["Model Proj"], errors="coerce")
        valid_num = graded.dropna(subset=["Actual", "Model Proj"])
        if len(valid_num) >= 15:
            pct_errors = (valid_num["Actual"] - valid_num["Model Proj"]) / valid_num["Model Proj"].replace(0, 1)
            mean_bias = pct_errors.mean()
            weights["global_bias_adj"] = round(max(-0.03, min(0.03, mean_bias * 0.30)), 4)

with open(WEIGHTS_FILE, "w") as f:
    json.dump(weights, f, indent=2)

print("Updated model_weights.json:", weights)
