import pandas as pd
import numpy as np

# =========================
# 設定
# =========================
INITIAL_BANKROLL = 100000
BET_UNIT = 100  # 100円単位

# =========================
# データ読み込み
# =========================
df = pd.read_csv("data/keirin_eval_hit.csv")

# settledのみ
df = df[df["settled"] == True].copy()

# race_idで時系列ソート
df = df.sort_values("race_id")

# =========================
# バックテスト
# =========================
bankroll = INITIAL_BANKROLL
bankroll_history = []
max_bankroll = INITIAL_BANKROLL
drawdowns = []

for _, row in df.iterrows():
    
    stake = row["stake"]
    
    # 100円単位に丸め
    stake = (stake // BET_UNIT) * BET_UNIT
    
    if stake <= 0:
        bankroll_history.append(bankroll)
        drawdowns.append(0)
        continue
    
    if stake > bankroll:
        stake = bankroll  # 全額以上は不可
    
    bankroll -= stake
    
    payout = row["payout"]
    
    bankroll += payout
    
    bankroll_history.append(bankroll)
    
    # 最大DD計算
    max_bankroll = max(max_bankroll, bankroll)
    dd = (max_bankroll - bankroll) / max_bankroll
    drawdowns.append(dd)

# =========================
# 結果集計
# =========================
total_stake = df["stake"].sum()
total_payout = df["payout"].sum()

roi = total_payout / total_stake if total_stake > 0 else 0
max_dd = max(drawdowns)

print("===== バックテスト結果 =====")
print(f"初期資金: {INITIAL_BANKROLL:,.0f} 円")
print(f"最終資金: {bankroll:,.0f} 円")
print(f"総投資額: {total_stake:,.0f} 円")
print(f"総回収額: {total_payout:,.0f} 円")
print(f"ROI: {roi*100:.2f}%")
print(f"最大ドローダウン: {max_dd*100:.2f}%")