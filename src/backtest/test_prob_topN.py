# src/backtest/test_prob_topN.py

import pandas as pd

TICKETS = "data/merged/ev_tickets_all.csv"
RESULTS = "data/merged/results_sanrentan_all.csv"

TOP_N = 3
BET = 100
INITIAL_BANKROLL = 100_000

df_t = pd.read_csv(TICKETS)
df_r = pd.read_csv(RESULTS)

df = df_t.merge(df_r, on="race_id", how="inner")

df = df.sort_values(["race_id","p"], ascending=[True, False])
df["rank"] = df.groupby("race_id").cumcount() + 1
df = df[df["rank"] <= TOP_N]

bankroll = INITIAL_BANKROLL
stake_total = 0
payout_total = 0
hit_races = 0

for race_id, g in df.groupby("race_id"):
    result = str(g["sanrentan_result"].iloc[0])
    payout100 = int(g["payout_sanrentan_100"].iloc[0])

    race_hit = False
    for _, row in g.iterrows():
        stake_total += BET
        bankroll -= BET
        if str(row["買い目"]) == result:
            payout = payout100
            payout_total += payout
            bankroll += payout
            race_hit = True

    if race_hit:
        hit_races += 1

roi = payout_total / stake_total if stake_total > 0 else 0

print("races:", df["race_id"].nunique())
print("hit races:", hit_races)
print("stake:", stake_total)
print("payout:", payout_total)
print("ROI:", roi)
print("final bankroll:", bankroll)