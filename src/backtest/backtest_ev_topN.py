import pandas as pd
import numpy as np

# =========================
# 設定（ユーザー合意済み）
# =========================
INITIAL_BANKROLL = 100_000
BET_UNIT = 100                  # 100円単位
TOP_N = 3                       # EV上位N点
KELLY_MULTIPLIER = 0.5          # ハーフケリー

# 安全装置（最初は保守的推奨）
RACE_CAP = 0.01                 # 1レースの最大投資 = 資金の1%
TICKET_CAP = 0.005              # 1点あたり最大投資 = 資金の0.5%
MIN_BET = 100                   # 0にすると「丸めで0円なら買わない」

# フィルタ（必要なら後で調整）
EV_MIN = 0.0                    # EVがこれ未満は買わない
P_MIN = 0.0                     # pがこれ未満は買わない（例: 0.002 など）

# 入力
PATH_TICKETS = "data/keirin_ev_tickets.csv"
PATH_RESULTS = "data/keirin_results_sanrentan.csv"

# 出力
OUT_DETAIL = "data/backtest_detail_topN.csv"
OUT_RACE_SUMMARY = "data/backtest_race_summary_topN.csv"


def kelly_fraction(p: float, odds: float) -> float:
    """Decimal odds（例: 5544.8）前提のケリー比率（フルケリー）"""
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
df_t = pd.read_csv(PATH_TICKETS)
df_r = pd.read_csv(PATH_RESULTS)

# 結果突合（結果あるものだけが settled）
df = df_t.merge(df_r, on="race_id", how="left")
df["settled"] = df["sanrentan_result"].notna()

# フィルタ
df = df[df["EV"] >= EV_MIN].copy()
df = df[df["p"] >= P_MIN].copy()

# EV降順で上位N点を各race_idで選ぶ
df = df.sort_values(["race_id", "EV"], ascending=[True, False])
df["rank_in_race"] = df.groupby("race_id").cumcount() + 1
df = df[df["rank_in_race"] <= TOP_N].copy()

# 時系列順（race_idに日付が含まれている前提）
df = df.sort_values(["race_id", "rank_in_race"]).reset_index(drop=True)

# =========================
# バックテスト（settledのみ資金推移）
# =========================
bankroll = INITIAL_BANKROLL
max_bankroll = INITIAL_BANKROLL

detail_records = []
race_records = []

for race_id, g in df.groupby("race_id", sort=True):
    g = g.copy()

    settled = bool(g["settled"].iloc[0])
    result = g["sanrentan_result"].iloc[0] if settled else None
    payout100 = g["payout_sanrentan_100"].iloc[0] if settled else None

    # 未確定レースは買わない（資金推移も変えない）
    if not settled:
        for _, row in g.iterrows():
            detail_records.append({
                "race_id": race_id,
                "買い目": row["買い目"],
                "odds": row["odds"],
                "p": row["p"],
                "EV": row["EV"],
                "rank_in_race": row["rank_in_race"],
                "settled": False,
                "sanrentan_result": result,
                "stake": 0,
                "hit": False,
                "payout": 0,
                "profit": 0,
                "bankroll_after": bankroll
            })
        race_records.append({
            "race_id": race_id,
            "settled": False,
            "sanrentan_result": result,
            "stake_total": 0,
            "payout_total": 0,
            "profit_total": 0,
            "hit_any": False,
            "bankroll_after": bankroll
        })
        continue

    # --- レース内：各点のstakeを計算 ---
    stakes = []
    for _, row in g.iterrows():
        p = float(row["p"])
        odds = float(row["odds"])

        f_full = kelly_fraction(p, odds)
        f = min(f_full * KELLY_MULTIPLIER, TICKET_CAP)

        stake_raw = bankroll * f
        stake = round_down_to_unit(stake_raw, BET_UNIT)

        if stake > 0 and stake < MIN_BET:
            stake = MIN_BET

        stakes.append(stake)

    g["stake"] = stakes

    # --- 1レース投資上限（RACE_CAP）を超えたら縮小 ---
    race_cap_yen = round_down_to_unit(bankroll * RACE_CAP, BET_UNIT)
    stake_sum = int(g["stake"].sum())

    if race_cap_yen > 0 and stake_sum > race_cap_yen:
        # 比例配分で縮小 → 100円単位に丸め直す
        scale = race_cap_yen / stake_sum
        g["stake"] = (g["stake"] * scale).apply(lambda x: round_down_to_unit(x, BET_UNIT))
        stake_sum = int(g["stake"].sum())

        # 縮小後に全部0になったら買わない
        if stake_sum == 0:
            for _, row in g.iterrows():
                detail_records.append({
                    "race_id": race_id,
                    "買い目": row["買い目"],
                    "odds": row["odds"],
                    "p": row["p"],
                    "EV": row["EV"],
                    "rank_in_race": row["rank_in_race"],
                    "settled": True,
                    "sanrentan_result": result,
                    "stake": 0,
                    "hit": False,
                    "payout": 0,
                    "profit": 0,
                    "bankroll_after": bankroll
                })
            race_records.append({
                "race_id": race_id,
                "settled": True,
                "sanrentan_result": result,
                "stake_total": 0,
                "payout_total": 0,
                "profit_total": 0,
                "hit_any": False,
                "bankroll_after": bankroll
            })
            continue

    # --- レース結果で精算 ---
    payout_total = 0
    profit_total = 0
    hit_any = False

    for _, row in g.iterrows():
        stake = int(row["stake"])
        bet = str(row["買い目"])

        hit = (bet == str(result)) and stake > 0
        if hit:
            hit_any = True
            payout = int(payout100) * (stake // 100)
        else:
            payout = 0

        profit = payout - stake

        payout_total += payout
        profit_total += profit

        detail_records.append({
            "race_id": race_id,
            "買い目": bet,
            "odds": row["odds"],
            "p": row["p"],
            "EV": row["EV"],
            "rank_in_race": row["rank_in_race"],
            "settled": True,
            "sanrentan_result": result,
            "stake": stake,
            "hit": bool(hit),
            "payout": payout,
            "profit": profit,
            "bankroll_after": None  # 後でレース精算後の値を入れる
        })

    bankroll += profit_total
    max_bankroll = max(max_bankroll, bankroll)
    dd = (max_bankroll - bankroll) / max_bankroll if max_bankroll > 0 else 0

    # 詳細の bankroll_after を埋める（このレース分）
    for rec in reversed(detail_records):
        if rec["race_id"] != race_id:
            break
        rec["bankroll_after"] = bankroll
        rec["drawdown"] = dd

    race_records.append({
        "race_id": race_id,
        "settled": True,
        "sanrentan_result": result,
        "stake_total": stake_sum,
        "payout_total": payout_total,
        "profit_total": profit_total,
        "hit_any": hit_any,
        "bankroll_after": bankroll,
        "drawdown": dd
    })

# =========================
# 集計
# =========================
detail = pd.DataFrame(detail_records)
race_summary = pd.DataFrame(race_records)

settled_races = race_summary[race_summary["settled"] == True].copy()

total_stake = int(settled_races["stake_total"].sum())
total_payout = int(settled_races["payout_total"].sum())
roi = (total_payout / total_stake) if total_stake > 0 else 0.0

hits = int(settled_races["hit_any"].sum())
n = len(settled_races)
max_dd = float(settled_races["drawdown"].max()) if n > 0 else 0.0

# 最大連敗（レース単位）
max_losing_streak = 0
cur = 0
for h in settled_races["hit_any"].fillna(False).tolist():
    if h:
        cur = 0
    else:
        cur += 1
        max_losing_streak = max(max_losing_streak, cur)

# 期待的中数（上位N点のp合計、レース単位で上限1にクリップ）
# ※「同一レースで複数的中しない」前提なので min(1, sum p)
p_race = detail[detail["settled"] == True].groupby("race_id")["p"].sum().clip(upper=1.0)
expected_hits = float(p_race.sum())

# 出力
detail.to_csv(OUT_DETAIL, index=False)
race_summary.to_csv(OUT_RACE_SUMMARY, index=False)

print("===== EV上位N点 戦略（ハーフケリー）=====")
print(f"TOP_N: {TOP_N}")
print(f"EV_MIN: {EV_MIN}, P_MIN: {P_MIN}")
print(f"RACE_CAP: {RACE_CAP*100:.2f}% / TICKET_CAP: {TICKET_CAP*100:.2f}%")
print(f"対象（settled）: {n} レース")
print(f"初期資金: {INITIAL_BANKROLL:,.0f} 円")
print(f"最終資金: {bankroll:,.0f} 円")
print(f"総投資額: {total_stake:,.0f} 円")
print(f"総回収額: {total_payout:,.0f} 円")
print(f"ROI: {roi*100:.2f}%")
print(f"的中（レース単位）: {hits} / {n}（{(hits/n*100 if n else 0):.2f}%）")
print(f"期待的中数（概算）: {expected_hits:.3f}")
print(f"最大ドローダウン: {max_dd*100:.2f}%")
print(f"最大連敗（レース単位）: {max_losing_streak}")
print(f"詳細CSV: {OUT_DETAIL}")
print(f"レース集計CSV: {OUT_RACE_SUMMARY}")