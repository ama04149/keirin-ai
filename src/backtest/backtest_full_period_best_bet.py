import pandas as pd
import numpy as np

# =========================
# 設定（ユーザー合意済み）
# =========================
INITIAL_BANKROLL = 100_000
BET_UNIT = 100                  # 100円単位
KELLY_MULTIPLIER = 0.5          # ハーフケリー
KELLY_CAP = 0.005               # 1レースあたり最大0.5%（安全キャップ、必要なら調整）
MIN_BET = 100                   # 最低購入単位（0にしたければ 0 に）

# 入力
PATH_EV_RANK = "data/keirin_ev_race_rank.csv"
PATH_RESULTS = "data/keirin_results_sanrentan.csv"

# 出力
OUT_DETAIL = "data/backtest_detail_best_bet.csv"

# =========================
# Kelly計算（オッズは「倍率」＝decimal odds 前提）
# odds: 5544.8 のような値（倍率）
# p: 0-1
# =========================
def kelly_fraction(p: float, odds: float) -> float:
    if pd.isna(p) or pd.isna(odds) or odds <= 1 or p <= 0:
        return 0.0
    b = odds - 1.0
    f = (b * p - (1.0 - p)) / b  # = (odds*p - 1) / (odds - 1)
    return max(0.0, float(f))

def round_down_to_unit(x: float, unit: int) -> int:
    if x <= 0:
        return 0
    return int(x // unit) * unit

# =========================
# 読み込み
# =========================
df_ev = pd.read_csv(PATH_EV_RANK)
df_res = pd.read_csv(PATH_RESULTS)

# 結果と突合（結果があるものだけが settled 扱い）
df = df_ev.merge(df_res, on="race_id", how="left")

# 時系列順（race_idに日付が入っている前提）
df = df.sort_values("race_id").reset_index(drop=True)

# settledフラグ
df["settled"] = df["sanrentan_result"].notna()

# =========================
# バックテスト（settled のみ資金推移）
# =========================
bankroll = INITIAL_BANKROLL
max_bankroll = INITIAL_BANKROLL

records = []

for _, row in df.iterrows():
    race_id = row["race_id"]
    best_bet = row["best_bet"]
    p = row["best_p"]
    odds = row["best_odds"]
    result = row["sanrentan_result"]
    payout100 = row["payout_sanrentan_100"]
    settled = bool(row["settled"])

    # 未確定はスキップ（資金推移に入れない）
    if not settled:
        records.append({
            "race_id": race_id,
            "best_bet": best_bet,
            "best_p": p,
            "best_odds": odds,
            "sanrentan_result": result,
            "payout_sanrentan_100": payout100,
            "settled": False,
            "stake": 0,
            "payout": 0,
            "profit": 0,
            "bankroll_after": bankroll,
            "drawdown": (max_bankroll - bankroll) / max_bankroll if max_bankroll > 0 else 0
        })
        continue

    # Kelly（フル→ハーフ→キャップ）
    f_full = kelly_fraction(p, odds)
    f = f_full * KELLY_MULTIPLIER
    f = min(f, KELLY_CAP)

    stake_raw = bankroll * f
    stake = round_down_to_unit(stake_raw, BET_UNIT)

    # 最低購入単位（MIN_BET）
    if stake > 0 and stake < MIN_BET:
        stake = MIN_BET

    # 資金を超えない（100円単位で切り下げ）
    if stake > bankroll:
        stake = round_down_to_unit(bankroll, BET_UNIT)

    # 的中判定（完全一致）
    hit = (str(best_bet) == str(result))

    if hit and stake > 0:
        payout = int(payout100) * (stake // 100)
    else:
        payout = 0

    profit = payout - stake
    bankroll += profit

    max_bankroll = max(max_bankroll, bankroll)
    dd = (max_bankroll - bankroll) / max_bankroll if max_bankroll > 0 else 0

    records.append({
        "race_id": race_id,
        "best_bet": best_bet,
        "best_p": p,
        "best_odds": odds,
        "kelly_full": f_full,
        "kelly_used": f,
        "sanrentan_result": result,
        "payout_sanrentan_100": payout100,
        "settled": True,
        "hit": hit,
        "stake_raw": stake_raw,
        "stake": stake,
        "payout": payout,
        "profit": profit,
        "bankroll_after": bankroll,
        "drawdown": dd
    })

detail = pd.DataFrame(records)

# =========================
# 集計
# =========================
settled_detail = detail[detail["settled"] == True].copy()

total_stake = settled_detail["stake"].sum()
total_payout = settled_detail["payout"].sum()
roi = (total_payout / total_stake) if total_stake > 0 else 0.0

hits = int(settled_detail["hit"].sum()) if "hit" in settled_detail.columns else 0
n = len(settled_detail)

max_dd = float(settled_detail["drawdown"].max()) if n > 0 else 0.0

# 連敗数（hit=Falseが連続した最大長）
max_losing_streak = 0
cur = 0
for h in settled_detail["hit"].fillna(False).tolist():
    if h:
        cur = 0
    else:
        cur += 1
        max_losing_streak = max(max_losing_streak, cur)

# 出力
detail.to_csv(OUT_DETAIL, index=False)

print("===== 全期間 再計算（best_bet / ハーフケリー） =====")
print(f"対象（settled）: {n} レース")
print(f"初期資金: {INITIAL_BANKROLL:,.0f} 円")
print(f"最終資金: {bankroll:,.0f} 円")
print(f"総投資額: {total_stake:,.0f} 円")
print(f"総回収額: {total_payout:,.0f} 円")
print(f"ROI: {roi*100:.2f}%")
print(f"的中: {hits} / {n}（{(hits/n*100 if n else 0):.2f}%）")
print(f"最大ドローダウン: {max_dd*100:.2f}%")
print(f"最大連敗: {max_losing_streak}")
print(f"詳細CSV出力: {OUT_DETAIL}")