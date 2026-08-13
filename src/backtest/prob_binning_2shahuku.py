import pandas as pd
import re
import numpy as np

TICKETS = "data/merged/ev_tickets_2shahuku_all.csv"
RESULTS = "data/merged/results_nirenpuku_all.csv"

def norm(s):
    s = str(s).strip()
    s = re.sub(r"[－―−–—]", "-", s)
    s = re.sub(r"\s+", "", s)
    return s

def normalize_pair(s):
    t = norm(s)
    a, b = t.split("-")
    x, y = sorted([int(a), int(b)])
    return f"{x}-{y}"

def main():
    df_t = pd.read_csv(TICKETS)
    df_r = pd.read_csv(RESULTS)

    df = df_t.merge(df_r, on="race_id", how="inner").copy()

    df["p"] = pd.to_numeric(df["p"], errors="coerce")
    df["odds"] = pd.to_numeric(df["odds"], errors="coerce")

    df = df[df["odds"] < 9999]
    df = df.sort_values(["race_id", "EV"], ascending=[True, False])

    # EV1位のみ使用（TOP1戦略）
    df["rank"] = df.groupby("race_id").cumcount() + 1
    df = df[df["rank"] == 1].copy()

    hits = []

    for _, row in df.iterrows():
        true_pair = normalize_pair(row["nirenpuku_result"])
        bet_pair = normalize_pair(row["買い目"])

        hit = 1 if bet_pair == true_pair else 0

        hits.append({
            "p": row["p"],
            "hit": hit
        })

    df_eval = pd.DataFrame(hits)

    # ビニング（確率帯）
    bins = [0, 0.02, 0.04, 0.06, 0.08, 0.1, 0.15, 1.0]
    labels = [
        "0-2%",
        "2-4%",
        "4-6%",
        "6-8%",
        "8-10%",
        "10-15%",
        "15%+"
    ]

    df_eval["bin"] = pd.cut(df_eval["p"], bins=bins, labels=labels)

    summary = df_eval.groupby("bin").agg(
        count=("hit", "count"),
        hit_sum=("hit", "sum"),
        mean_p=("p", "mean")
    ).reset_index()

    summary["actual_hit_rate"] = summary["hit_sum"] / summary["count"]

    print("\n===== PROBABILITY BINNING =====")
    print(summary.to_string(index=False))

if __name__ == "__main__":
    main()