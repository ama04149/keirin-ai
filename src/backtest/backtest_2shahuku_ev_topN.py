import pandas as pd
import re

TICKETS = "data/merged/ev_tickets_2shahuku_all.csv"
RESULTS = "data/merged/results_nirenpuku_all.csv"

TOP_N = 3
BET = 100
INITIAL = 100_000
EV_MIN = 0.0  # まずはプラス期待値のみ


def norm(s: str) -> str:
    s = str(s).strip()
    s = re.sub(r"[－―−–—]", "-", s)
    s = re.sub(r"\s+", "", s)
    return s


def normalize_pair(s: str) -> str:
    # "6-3" -> "3-6"
    t = norm(s)
    a, b = t.split("-")
    x, y = sorted([int(a), int(b)])
    return f"{x}-{y}"


def main():
    df_t = pd.read_csv(TICKETS)
    df_r = pd.read_csv(RESULTS)

    df = df_t.merge(df_r, on="race_id", how="inner").copy()

    required = ["race_id", "買い目", "EV", "nirenpuku_result", "payout_nirenpuku_100"]
    miss = [c for c in required if c not in df.columns]
    if miss:
        raise ValueError(f"missing columns: {miss}")

    bankroll = INITIAL
    stake_total = 0
    payout_total = 0
    hit_races = 0
    bought_races = 0

    for rid, g in df.groupby("race_id"):
        true_pair = normalize_pair(g["nirenpuku_result"].iloc[0])
        payout100 = int(g["payout_nirenpuku_100"].iloc[0])

        gg = g.copy()
        gg["EV"] = pd.to_numeric(gg["EV"], errors="coerce")
        gg = gg.dropna(subset=["EV"])
        gg = gg[gg["EV"] >= EV_MIN]

        if gg.empty:
            continue

        # EV上位TOP_N
        gg = gg.sort_values("EV", ascending=False).head(TOP_N)
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

    roi = payout_total / stake_total if stake_total else 0

    print("matched races (after merge):", df["race_id"].nunique())
    print("BOUGHT RACES:", bought_races)
    print("TOP_N:", TOP_N, "EV_MIN:", EV_MIN)
    print("hit races:", hit_races)
    print("stake:", stake_total, "payout:", payout_total)
    print("ROI:", roi)
    print("final bankroll:", bankroll)


if __name__ == "__main__":
    main()