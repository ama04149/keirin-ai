import pandas as pd

TICKETS = "data/merged/ev_tickets_all.csv"
RESULTS = "data/merged/results_sanrentan_all.csv"

df_t = pd.read_csv(TICKETS)
df_r = pd.read_csv(RESULTS)

df = df_t.merge(df_r[["race_id","sanrentan_result"]], on="race_id", how="inner").copy()
df["is_true"] = df["買い目"].astype(str) == df["sanrentan_result"].astype(str)

# EV順位
df = df.sort_values(["race_id","EV"], ascending=[True, False])
df["ev_rank"] = df.groupby("race_id").cumcount() + 1

true = df[df["is_true"]].copy()
print("true rows:", len(true), " / races:", true["race_id"].nunique())
print("\nEV-rank quantiles:")
print(true["ev_rank"].quantile([0.5,0.75,0.9,0.95,0.99]).to_string())
print("\nEV-rank top counts:")
print(true["ev_rank"].value_counts().head(20).to_string())