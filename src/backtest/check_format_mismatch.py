import pandas as pd

TICKETS = "data/merged/ev_tickets_all.csv"
RESULTS = "data/merged/results_sanrentan_all.csv"

df_t = pd.read_csv(TICKETS)
df_r = pd.read_csv(RESULTS)

df = df_t.merge(df_r[["race_id","sanrentan_result"]], on="race_id", how="inner")

print("rows:", len(df))
print("unique races:", df["race_id"].nunique())

# 先頭の例を表示
print("\n--- sample (ticket vs result) ---")
sample = df[["買い目","sanrentan_result"]].head(20)
print(sample.to_string(index=False))

# 文字列の“見た目”統計
df["bet_str"] = df["買い目"].astype(str)
df["res_str"] = df["sanrentan_result"].astype(str)

print("\n--- length stats ---")
print("bet len min/mean/max:", df["bet_str"].str.len().min(), df["bet_str"].str.len().mean(), df["bet_str"].str.len().max())
print("res len min/mean/max:", df["res_str"].str.len().min(), df["res_str"].str.len().mean(), df["res_str"].str.len().max())

# “完全一致”が1件でもあるか
eq_any = (df["bet_str"] == df["res_str"]).any()
print("\nexact match exists?:", eq_any)