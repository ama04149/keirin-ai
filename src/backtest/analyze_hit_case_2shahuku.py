import pandas as pd
import re

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
    df["odds"] = pd.to_numeric(df["odds"], errors="coerce")
    df["EV"] = pd.to_numeric(df["EV"], errors="coerce")
    df["p"] = pd.to_numeric(df["p"], errors="coerce")

    df = df[df["odds"] < 9999]

    hit_rows = []

    for rid, g in df.groupby("race_id"):
        true_pair = normalize_pair(g["nirenpuku_result"].iloc[0])

        g = g.sort_values("EV", ascending=False).head(3)  # TOP3戦略

        for _, row in g.iterrows():
            bet = normalize_pair(row["買い目"])
            if bet == true_pair:
                hit_rows.append(row)

    if not hit_rows:
        print("No hit found")
        return

    hit_df = pd.DataFrame(hit_rows)

    print("\n===== HIT DETAIL =====")
    print(hit_df[[
        "race_id",
        "買い目",
        "odds",
        "p",
        "EV"
    ]].to_string(index=False))

    print("\n===== EV RANKING (そのレース全体) =====")
    rid = hit_df["race_id"].iloc[0]
    full = df[df["race_id"] == rid].sort_values("EV", ascending=False)

    print(full[[
        "買い目",
        "odds",
        "p",
        "EV"
    ]].head(15).to_string(index=False))


if __name__ == "__main__":
    main()