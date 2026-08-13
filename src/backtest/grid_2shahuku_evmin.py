import pandas as pd
import re

TICKETS = "data/merged/ev_tickets_2shahuku_all.csv"
RESULTS = "data/merged/results_nirenpuku_all.csv"

BET = 100
INITIAL = 100_000

TOP_N = 1
EV_MINS = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]


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

def run(ev_min):
    df_t = pd.read_csv(TICKETS)
    df_r = pd.read_csv(RESULTS)

    df = df_t.merge(df_r, on="race_id", how="inner").copy()

    df["EV"] = pd.to_numeric(df["EV"], errors="coerce")
    df["odds"] = pd.to_numeric(df["odds"], errors="coerce")

    df = df[df["odds"] < 9999]
    df = df[df["EV"] >= ev_min]

    df = df.sort_values(["race_id", "EV"], ascending=[True, False])
    df["rank"] = df.groupby("race_id").cumcount() + 1
    df = df[df["rank"] <= TOP_N]

    bankroll = INITIAL
    stake_total = 0
    payout_total = 0
    hit_races = 0
    bought_races = 0

    for rid, g in df.groupby("race_id"):
        true_pair = normalize_pair(g["nirenpuku_result"].iloc[0])
        g = g.sort_values("EV", ascending=False).head(TOP_N)

        if g.empty:
            continue

        bought_races += 1
        race_hit = False

        for _, r in g.iterrows():
            stake_total += BET
            bankroll -= BET

            bet_pair = normalize_pair(r["買い目"])
            payout100 = int(r["payout_nirenpuku_100"])

            if bet_pair == true_pair:
                race_hit = True
                payout_total += payout100
                bankroll += payout100

        if race_hit:
            hit_races += 1

    roi = payout_total / stake_total if stake_total else 0.0

    return {
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
    for ev in EV_MINS:
        rows.append(run(ev))

    out = pd.DataFrame(rows).sort_values("EV_MIN")
    print("\n===== EV_MIN GRID =====")
    print(out.to_string(index=False))
    out.to_csv("data/merged/grid_2shahuku_evmin.csv", index=False, encoding="utf-8-sig")
    print("\n[OUT] data/merged/grid_2shahuku_evmin.csv")


if __name__ == "__main__":
    main()