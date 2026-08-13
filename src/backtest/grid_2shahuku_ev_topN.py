import pandas as pd
import re

TICKETS = "data/merged/ev_tickets_2shahuku_all.csv"
RESULTS = "data/merged/results_nirenpuku_all.csv"

BET = 100
INITIAL = 100_000

TOP_NS = [1, 2, 3, 5]
EV_MINS = [0.0, 0.1, 0.2, 0.5]


def norm(s: str) -> str:
    s = str(s).strip()
    s = re.sub(r"[－―−–—]", "-", s)
    s = re.sub(r"\s+", "", s)
    return s


def normalize_pair(s: str) -> str:
    t = norm(s)
    a, b = t.split("-")
    x, y = sorted([int(a), int(b)])
    return f"{x}-{y}"


def run(top_n: int, ev_min: float):
    df_t = pd.read_csv(TICKETS)
    df_r = pd.read_csv(RESULTS)
    df = df_t.merge(df_r, on="race_id", how="inner").copy()

    # EV & odds cleaning
    df["EV"] = pd.to_numeric(df["EV"], errors="coerce")
    df["odds"] = pd.to_numeric(df["odds"], errors="coerce")
    df = df.dropna(subset=["EV", "odds"])

    # 番兵除外（念のためバックテスト側でも）
    df = df[df["odds"] < 9999]

    bankroll = INITIAL
    stake_total = 0
    payout_total = 0
    hit_races = 0
    bought_races = 0

    for rid, g in df.groupby("race_id"):
        true_pair = normalize_pair(g["nirenpuku_result"].iloc[0])
        payout100 = int(g["payout_nirenpuku_100"].iloc[0])

        gg = g[g["EV"] >= ev_min].sort_values("EV", ascending=False).head(top_n)
        if gg.empty:
            continue

        bought_races += 1
        race_hit = False

        for _, r in gg.iterrows():
            stake_total += BET
            bankroll -= BET

            bet_pair = normalize_pair(r["買い目"])
            if bet_pair == true_pair:
                race_hit = True
                payout_total += payout100
                bankroll += payout100

        if race_hit:
            hit_races += 1

    roi = payout_total / stake_total if stake_total else 0.0
    return {
        "TOP_N": top_n,
        "EV_MIN": ev_min,
        "matched_races": df["race_id"].nunique(),
        "bought_races": bought_races,
        "hit_races": hit_races,
        "stake": stake_total,
        "payout": payout_total,
        "ROI": roi,
        "final_bankroll": bankroll,
    }


def main():
    rows = []
    for top_n in TOP_NS:
        for ev_min in EV_MINS:
            rows.append(run(top_n, ev_min))

    out = pd.DataFrame(rows).sort_values(["ROI", "final_bankroll"], ascending=False)
    print(out.to_string(index=False))
    out.to_csv("data/merged/grid_2shahuku_ev_topN.csv", index=False, encoding="utf-8-sig")
    print("[OUT] data/merged/grid_2shahuku_ev_topN.csv")


if __name__ == "__main__":
    main()