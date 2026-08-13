import pandas as pd

T = "data/merged/ev_race_rank_2shahuku_all.csv"
R = "data/merged/results_nirenpuku_all.csv"

df_t = pd.read_csv(T)
df_r = pd.read_csv(R)

s_t = set(df_t["race_id"].astype(str))
s_r = set(df_r["race_id"].astype(str))

print("ev_race_rank_2shahuku_all races:", len(s_t))
print("results_nirenpuku_all races:", len(s_r))
print("intersection:", len(s_t & s_r))

# サンプル表示
print("\n--- sample ev ids ---")
print(list(sorted(s_t))[:5])
print("\n--- sample result ids ---")
print(list(sorted(s_r))[:5])