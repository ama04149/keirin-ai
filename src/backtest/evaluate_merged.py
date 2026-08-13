import pandas as pd

TICKETS = "data/merged/ev_tickets_all.csv"
RESULTS = "data/merged/results_sanrentan_all.csv"
RACE_SUMMARY = "data/merged/backtest_race_summary_topN.csv"  # run_pipeline が出力するやつ

df_t = pd.read_csv(TICKETS)
df_r = pd.read_csv(RESULTS)

# settled（結果がある）レース数
settled_races = df_r["race_id"].nunique()
print("settled races:", settled_races)

# tickets側で、結果と突合できるレース数
df = df_t.merge(df_r[["race_id", "sanrentan_result"]], on="race_id", how="inner")
print("tickets matched races:", df["race_id"].nunique())
print("tickets rows (matched):", len(df))

# 直近のバックテスト結果（ファイルがある場合）
try:
    rs = pd.read_csv(RACE_SUMMARY)
    rs = rs[rs["settled"] == True].copy()
    total_stake = rs["stake_total"].sum()
    total_payout = rs["payout_total"].sum()
    roi = (total_payout / total_stake) if total_stake > 0 else 0
    hits = rs["hit_any"].sum()
    n = len(rs)
    max_dd = rs["drawdown"].max() if n else 0
    print("\n=== latest backtest (from race_summary) ===")
    print("races:", n)
    print("hits:", int(hits), "/", n, f"({(hits/n*100 if n else 0):.2f}%)")
    print("stake:", int(total_stake), "payout:", int(total_payout), f"ROI:{roi*100:.2f}%")
    print(f"max DD:{max_dd*100:.2f}%")
except FileNotFoundError:
    print("\n[INFO] race_summary file not found. Run: py src/run_pipeline.py")