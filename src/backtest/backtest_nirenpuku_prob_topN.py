import pandas as pd
import re

TICKETS = "data/merged/ev_tickets_all.csv"
RESULTS = "data/merged/results_nirenpuku_all.csv"

BET = 100
INITIAL_BANKROLL = 100000

TOP_N = 3

# 👇 ここを調整する
MAX_TOP_PAIR_PROB = 0.25  # 上位ペア確率がこれ以上のレースは買わない


def normalize(s: str) -> str:
    s = str(s).strip()
    s = re.sub(r"[－―−–—]", "-", s)
    s = re.sub(r"\s+", "", s)
    return s


def parse_trifecta(ticket: str):
    t = normalize(ticket)
    parts = t.split("-")
    if len(parts) != 3:
        return None
    return parts[0], parts[1], parts[2]


def pair_key(a: str, b: str) -> str:
    x, y = sorted([int(a), int(b)])
    return f"{x}-{y}"


def main():
    df_t = pd.read_csv(TICKETS)
    df_r = pd.read_csv(RESULTS)
    df = df_t.merge(df_r, on="race_id", how="inner").copy()

    bankroll = INITIAL_BANKROLL
    stake_total = 0
    payout_total = 0
    hit_races = 0
    bought_races = 0

    for race_id, g in df.groupby("race_id"):
        true_pair = normalize(g["nirenpuku_result"].iloc[0])
        payout100 = int(g["payout_nirenpuku_100"].iloc[0])

        # ペア確率集約
        pair_prob = {}
        for _, r in g.iterrows():
            parsed = parse_trifecta(r["買い目"])
            if parsed is None:
                continue
            a, b, _ = parsed
            p = float(r["p"])
            k = pair_key(a, b)
            pair_prob[k] = pair_prob.get(k, 0.0) + p

        ranked = sorted(pair_prob.items(), key=lambda x: x[1], reverse=True)

        # 👇 上位ペア確率でフィルタ
        if ranked and ranked[0][1] > MAX_TOP_PAIR_PROB:
            continue

        chosen = [k for k, _ in ranked[:TOP_N]]
        bought_races += 1

        race_hit = False
        for k in chosen:
            stake_total += BET
            bankroll -= BET
            if normalize(k) == true_pair:
                race_hit = True
                payout_total += payout100
                bankroll += payout100

        if race_hit:
            hit_races += 1

    roi = payout_total / stake_total if stake_total else 0

    print("TOTAL RACES:", df["race_id"].nunique())
    print("BOUGHT RACES:", bought_races)
    print("hit:", hit_races)
    print("stake:", stake_total)
    print("payout:", payout_total)
    print("ROI:", roi)
    print("final bankroll:", bankroll)


if __name__ == "__main__":
    main()