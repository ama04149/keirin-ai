from __future__ import annotations

from pathlib import Path
from datetime import datetime
import shutil
import glob
import pandas as pd


# =========================================================
# 0) 設定：ここだけ触ればOK
# =========================================================
# 実行日で保存（ユーザー合意）
USE_TIME_SUBFOLDER = False  # Trueにすると同日でも時刻別に保存

# 保存したい「当日CSV」(コピー元) を固定
SOURCE_FILES = [
    "keirin_ev_tickets.csv",
    "keirin_ev_race_rank.csv",
    "keirin_kelly_bets.csv",
    "keirin_results_sanrentan.csv",
    "race_summary.csv",
    "daily_summary.csv",
    "keirin_results_nirenpuku.csv",
    "keirin_ev_tickets_2shahuku.csv",
    "keirin_ev_race_rank_2shahuku.csv",
]

# 統合先
DAILY_ROOT = Path("data") / "daily"
MERGED_ROOT = Path("data") / "merged"

# バックテスト（EV上位N点戦略）
INITIAL_BANKROLL = 100000
BET_UNIT = 100
TOP_N = 3
KELLY_MULTIPLIER = 0.5

# 安全装置
RACE_CAP = 0.01     # 1レース最大投資 = 資金の1%
TICKET_CAP = 0.005  # 1点最大投資 = 資金の0.5%
MIN_BET = 100

# フィルタ（必要に応じて後で調整）
EV_MIN = 0.0
P_MIN = 0.0


# =========================================================
# 1) 日付別保存
# =========================================================
def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def save_daily() -> Path:
    ymd = datetime.now().strftime("%Y%m%d")
    if USE_TIME_SUBFOLDER:
        time_str = datetime.now().strftime("%H%M%S")
        out_dir = DAILY_ROOT / ymd / time_str
    else:
        out_dir = DAILY_ROOT / ymd

    ensure_dir(out_dir)

    copied = 0
    for src_str in SOURCE_FILES:
        src = Path(src_str)
        if src.exists():
            dst = out_dir / src.name
            shutil.copy2(src, dst)
            print(f"[SAVE] {src.name} -> {dst}")
            copied += 1
        else:
            print(f"[SAVE][WARN] not found: {src}")

    if copied == 0:
        raise RuntimeError("保存対象ファイルが1つも見つかりません。SOURCE_FILES を確認してください。")

    print(f"[SAVE] saved to: {out_dir}")
    return out_dir


# =========================================================
# 2) 日付別→統合（重複除去）
# =========================================================
def _find_daily_files(filename: str) -> list[str]:
    """
    data/daily/YYYYMMDD/filename
    data/daily/YYYYMMDD/HHMMSS/filename
    の両方に対応
    """
    pattern1 = str(DAILY_ROOT / "*" / filename)
    pattern2 = str(DAILY_ROOT / "*" / "*" / filename)
    files = sorted(set(glob.glob(pattern1) + glob.glob(pattern2)))
    return files


def _merge(pattern_filename: str, out_name: str, dedup_keys: list[str]) -> Path | None:
    files = _find_daily_files(pattern_filename)
    if not files:
        print(f"[MERGE][WARN] no files: {pattern_filename}")
        return None

    dfs = []
    for f in files:
        try:
            dfs.append(pd.read_csv(f))
        except Exception as e:
            print(f"[MERGE][WARN] failed read: {f} ({e})")

    if not dfs:
        print(f"[MERGE][WARN] no readable files: {pattern_filename}")
        return None

    df = pd.concat(dfs, ignore_index=True)

    # dedup_keys が存在するかチェック
    missing = [k for k in dedup_keys if k not in df.columns]
    if missing:
        raise ValueError(
            f"{out_name}: dedup key not found: {missing}. "
            f"columns={list(df.columns)}"
        )

    before = len(df)
    df = df.drop_duplicates(subset=dedup_keys, keep="last").reset_index(drop=True)
    after = len(df)

    ensure_dir(MERGED_ROOT)
    out_path = MERGED_ROOT / out_name
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"[MERGE] {out_name}: {before} -> {after} (dedup={dedup_keys})")
    return out_path


def merge_daily() -> dict[str, Path]:
    ensure_dir(MERGED_ROOT)
    outputs: dict[str, Path] = {}

    # ✅ dailyに保存している実ファイル名に合わせる
    p = _merge("keirin_ev_tickets.csv", "ev_tickets_all.csv", ["race_id", "買い目"])
    if p: outputs["ev_tickets"] = p

    p = _merge("keirin_ev_race_rank.csv", "ev_race_rank_all.csv", ["race_id"])
    if p: outputs["ev_race_rank"] = p

    p = _merge("keirin_results_sanrentan.csv", "results_sanrentan_all.csv", ["race_id"])
    if p: outputs["results_sanrentan"] = p

    p = _merge("keirin_kelly_bets.csv", "kelly_bets_all.csv", ["race_id"])
    if p: outputs["kelly_bets"] = p
    
    p = _merge("keirin_results_nirenpuku.csv", "results_nirenpuku_all.csv", ["race_id"])
    if p: outputs["results_nirenpuku"] = p
    
    p = _merge("keirin_ev_tickets_2shahuku.csv", "ev_tickets_2shahuku_all.csv", ["race_id", "買い目"])
    if p: outputs["ev_tickets_2shahuku"] = p

    p = _merge("keirin_ev_race_rank_2shahuku.csv", "ev_race_rank_2shahuku_all.csv", ["race_id"])
    if p: outputs["ev_race_rank_2shahuku"] = p

    return outputs


# =========================================================
# 3) バックテスト（統合データ：EV上位N点）
# =========================================================
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


def backtest_topN(ev_tickets_path: Path, results_path: Path) -> None:
    df_t = pd.read_csv(ev_tickets_path)
    df_r = pd.read_csv(results_path)

    # 結果突合
    df = df_t.merge(df_r, on="race_id", how="left")
    df["settled"] = df["sanrentan_result"].notna()

    # フィルタ
    for col in ["EV", "p", "odds", "買い目"]:
        if col not in df.columns:
            raise ValueError(f"必要列 '{col}' がありません。columns={list(df.columns)}")
    df = df[df["EV"] >= EV_MIN].copy()
    df = df[df["p"] >= P_MIN].copy()

    # EV上位N点（レース内順位）
    df = df.sort_values(["race_id", "EV"], ascending=[True, False])
    df["rank_in_race"] = df.groupby("race_id").cumcount() + 1
    df = df[df["rank_in_race"] <= TOP_N].copy()

    # 時系列順
    df = df.sort_values(["race_id", "rank_in_race"]).reset_index(drop=True)

    bankroll = INITIAL_BANKROLL
    max_bankroll = INITIAL_BANKROLL

    detail_records = []
    race_records = []

    for race_id, g in df.groupby("race_id", sort=True):
        g = g.copy()
        settled = bool(g["settled"].iloc[0])
        result = g["sanrentan_result"].iloc[0] if settled else None
        payout100 = g["payout_sanrentan_100"].iloc[0] if settled else None

        if not settled:
            for _, row in g.iterrows():
                detail_records.append({
                    "race_id": race_id, "買い目": row["買い目"],
                    "odds": row["odds"], "p": row["p"], "EV": row["EV"],
                    "rank_in_race": row["rank_in_race"],
                    "settled": False, "sanrentan_result": result,
                    "stake": 0, "hit": False, "payout": 0, "profit": 0,
                    "bankroll_after": bankroll
                })
            race_records.append({
                "race_id": race_id, "settled": False, "sanrentan_result": result,
                "stake_total": 0, "payout_total": 0, "profit_total": 0,
                "hit_any": False, "bankroll_after": bankroll, "drawdown": 0.0
            })
            continue

        # 点ごとのstake
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

        # レース上限で縮小
        race_cap_yen = round_down_to_unit(bankroll * RACE_CAP, BET_UNIT)
        stake_sum = int(g["stake"].sum())

        if race_cap_yen > 0 and stake_sum > race_cap_yen:
            scale = race_cap_yen / stake_sum
            g["stake"] = (g["stake"] * scale).apply(lambda x: round_down_to_unit(x, BET_UNIT))
            stake_sum = int(g["stake"].sum())

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
                "race_id": race_id, "買い目": bet,
                "odds": row["odds"], "p": row["p"], "EV": row["EV"],
                "rank_in_race": row["rank_in_race"],
                "settled": True, "sanrentan_result": result,
                "stake": stake, "hit": bool(hit),
                "payout": payout, "profit": profit
            })

        bankroll += profit_total
        max_bankroll = max(max_bankroll, bankroll)
        dd = (max_bankroll - bankroll) / max_bankroll if max_bankroll > 0 else 0.0

        race_records.append({
            "race_id": race_id, "settled": True, "sanrentan_result": result,
            "stake_total": stake_sum, "payout_total": payout_total, "profit_total": profit_total,
            "hit_any": hit_any, "bankroll_after": bankroll, "drawdown": dd
        })

    detail = pd.DataFrame(detail_records)
    race_summary = pd.DataFrame(race_records)

    # 出力
    out_detail = MERGED_ROOT / "backtest_detail_topN.csv"
    out_race = MERGED_ROOT / "backtest_race_summary_topN.csv"
    detail.to_csv(out_detail, index=False, encoding="utf-8-sig")
    race_summary.to_csv(out_race, index=False, encoding="utf-8-sig")

    settled_races = race_summary[race_summary["settled"] == True].copy()
    total_stake = int(settled_races["stake_total"].sum())
    total_payout = int(settled_races["payout_total"].sum())
    roi = (total_payout / total_stake) if total_stake > 0 else 0.0

    hits = int(settled_races["hit_any"].sum())
    n = len(settled_races)
    max_dd = float(settled_races["drawdown"].max()) if n > 0 else 0.0

    # 期待的中数（概算）
    if len(detail) > 0:
        p_race = detail.groupby("race_id")["p"].sum().clip(upper=1.0)
        expected_hits = float(p_race.sum())
    else:
        expected_hits = 0.0

    # 最大連敗（レース単位）
    max_losing_streak = 0
    cur = 0
    for h in settled_races["hit_any"].fillna(False).tolist():
        if h:
            cur = 0
        else:
            cur += 1
            max_losing_streak = max(max_losing_streak, cur)

    print("\n===== PIPELINE BACKTEST RESULT =====")
    print(f"TOP_N: {TOP_N}, KELLY_MULTIPLIER: {KELLY_MULTIPLIER}")
    print(f"EV_MIN: {EV_MIN}, P_MIN: {P_MIN}")
    print(f"RACE_CAP: {RACE_CAP*100:.2f}%, TICKET_CAP: {TICKET_CAP*100:.2f}%")
    print(f"対象（settled）: {n} レース")
    print(f"初期資金: {INITIAL_BANKROLL:,.0f} 円")
    print(f"最終資金: {settled_races['bankroll_after'].iloc[-1]:,.0f} 円" if n > 0 else f"最終資金: {INITIAL_BANKROLL:,.0f} 円")
    print(f"総投資額: {total_stake:,.0f} 円")
    print(f"総回収額: {total_payout:,.0f} 円")
    print(f"ROI: {roi*100:.2f}%")
    print(f"的中（レース単位）: {hits} / {n}（{(hits/n*100 if n else 0):.2f}%）")
    print(f"期待的中数（概算）: {expected_hits:.3f}")
    print(f"最大ドローダウン: {max_dd*100:.2f}%")
    print(f"最大連敗（レース単位）: {max_losing_streak}")
    print(f"[OUT] {out_detail}")
    print(f"[OUT] {out_race}")


# =========================================================
# 4) メイン：ワンコマンド
# =========================================================
def main():
    print("=== 1) SAVE DAILY ===")
    save_daily()

    print("\n=== 2) MERGE DAILY ===")
    outputs = merge_daily()

    # バックテストに必要な統合ファイル
    if "ev_tickets" not in outputs or "results_sanrentan" not in outputs:
        raise RuntimeError("統合ファイルが不足しています。ev_tickets / results_sanrentan を確認してください。")

    print("\n=== 3) BACKTEST (MERGED) ===")
    backtest_topN(outputs["ev_tickets"], outputs["results_sanrentan"])

    print("\n=== DONE ===")


if __name__ == "__main__":
    main()