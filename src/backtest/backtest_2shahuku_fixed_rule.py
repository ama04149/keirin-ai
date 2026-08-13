import pandas as pd
import re

TICKETS = "data/merged/odds_distortion_2shahuku_all.csv"
RESULTS = "data/merged/results_nirenpuku_all.csv"

BET = 100
INITIAL = 100_000

# 暫定固定ルール（更新版）
TOP_N = 1
EV_MIN = 5.0
ODDS_MIN = 120.0
ODDS_MAX = 200.0
RANK_GAP_MIN = 8.0


def norm(s: str) -> str:
    s = str(s).strip()
    s = re.sub(r"[－―−–—]", "-", s)
    s = re.sub(r"\s+", "", s)
    return s


def normalize_pair(s: str) -> str:
    t = norm(s)
    a, b = t.split("-")
    x, y = sorted([int(a), int(b)])
    return f"{x}-{y}"


def main():
    df_t = pd.read_csv(TICKETS)
    df_r = pd.read_csv(RESULTS)

    df = df_t.merge(df_r, on="race_id", how="inner").copy()

    # 数値化
    for c in ["EV", "odds", "rank_gap", "p", "distortion_ratio", "distortion_score"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # 基本クリーニング
    df = df.dropna(subset=["race_id", "買い目", "EV", "odds", "rank_gap"])
    df = df[(df["odds"] > 1) & (df["odds"] < 9999)]

    # ルール適用
    cond = (
        (df["EV"] >= EV_MIN) &
        (df["odds"] >= ODDS_MIN) &
        (df["odds"] <= ODDS_MAX) &
        (df["rank_gap"] >= RANK_GAP_MIN)
    )
    df = df[cond].copy()

    if df.empty:
        print("該当レースがありません。")
        return

    # レース内で distortion_score 優先、なければ EV
    sort_col = "distortion_score" if "distortion_score" in df.columns else "EV"
    df = df.sort_values(["race_id", sort_col], ascending=[True, False]).copy()
    df["rank"] = df.groupby("race_id").cumcount() + 1
    df = df[df["rank"] <= TOP_N].copy()

    bankroll = INITIAL
    stake_total = 0
    payout_total = 0
    hit_races = 0
    detail_rows = []

    for rid, g in df.groupby("race_id"):
        true_pair = normalize_pair(g["nirenpuku_result"].iloc[0])

        race_hit = False

        for _, row in g.iterrows():
            bet_pair = normalize_pair(row["買い目"])
            payout100 = int(row["payout_nirenpuku_100"])

            stake_total += BET
            bankroll -= BET

            hit = bet_pair == true_pair
            payout = payout100 if hit else 0

            if hit:
                race_hit = True
                payout_total += payout
                bankroll += payout

            detail_rows.append({
                "race_id": rid,
                "競輪場": row.get("競輪場", ""),
                "レース番号": row.get("レース番号", ""),
                "開始時間": row.get("開始時間", ""),
                "買い目": row["買い目"],
                "true_pair": true_pair,
                "hit": int(hit),
                "odds": row["odds"],
                "p": row.get("p", None),
                "EV": row["EV"],
                "rank_gap": row.get("rank_gap", None),
                "distortion_ratio": row.get("distortion_ratio", None),
                "distortion_score": row.get("distortion_score", None),
                "stake": BET,
                "payout": payout,
                "bankroll_after_bet": bankroll,
            })

        if race_hit:
            hit_races += 1

    roi = payout_total / stake_total if stake_total > 0 else 0.0
    bought_races = df["race_id"].nunique()

    print("===== FIXED RULE BACKTEST =====")
    print(f"TOP_N = {TOP_N}")
    print(f"EV_MIN = {EV_MIN}")
    print(f"ODDS_MIN = {ODDS_MIN}")
    print(f"ODDS_MAX = {ODDS_MAX}")
    print(f"RANK_GAP_MIN = {RANK_GAP_MIN}")
    print(f"bought_races = {bought_races}")
    print(f"hit_races = {hit_races}")
    print(f"stake = {stake_total}")
    print(f"payout = {payout_total}")
    print(f"ROI = {roi:.6f}")
    print(f"final_bankroll = {bankroll}")

    out = pd.DataFrame(detail_rows)
    out_path = "data/merged/backtest_2shahuku_fixed_rule_detail.csv"
    out.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"[OUT] {out_path}")


if __name__ == "__main__":
    main()