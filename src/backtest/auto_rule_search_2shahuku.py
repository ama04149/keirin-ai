import pandas as pd
import numpy as np

TICKETS="data/merged/odds_distortion_2shahuku_all.csv"
RESULTS="data/merged/results_nirenpuku_all.csv"

BET=100
INITIAL=100000

EV_GRID=[0,1,2,3]
RATIO_GRID=[1.5,2,3,5]
RANK_GRID=[3,5,8]
ODDS_MIN_GRID=[20,50,80]
ODDS_MAX_GRID=[200,300,500]

df_t=pd.read_csv(TICKETS)
df_r=pd.read_csv(RESULTS)

df=df_t.merge(df_r,on="race_id")

results=[]

for ev in EV_GRID:
    for ratio in RATIO_GRID:
        for rank in RANK_GRID:
            for o_min in ODDS_MIN_GRID:
                for o_max in ODDS_MAX_GRID:

                    cond=(
                        (df["EV"]>=ev) &
                        (df["distortion_ratio"]>=ratio) &
                        (df["rank_gap"]>=rank) &
                        (df["odds"]>=o_min) &
                        (df["odds"]<=o_max)
                    )

                    d=df[cond]

                    if len(d)==0:
                        continue

                    stake=len(d)*BET
                    payout=0
                    hit=0

                    for _,r in d.iterrows():
                        if r["買い目"]==r["nirenpuku_result"]:
                            payout+=r["payout_nirenpuku_100"]
                            hit+=1

                    roi=payout/stake if stake>0 else 0

                    results.append({
                        "EV_MIN":ev,
                        "ratio":ratio,
                        "rank_gap":rank,
                        "odds_min":o_min,
                        "odds_max":o_max,
                        "bets":len(d),
                        "hit":hit,
                        "ROI":roi
                    })

res=pd.DataFrame(results)

res=res.sort_values("ROI",ascending=False)

print(res.head(30))

res.to_csv("data/merged/auto_rule_search_2shahuku.csv",index=False)