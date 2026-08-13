import pandas as pd
import numpy as np
import re

TICKETS = "data/merged/odds_distortion_2shahuku_all.csv"
RESULTS = "data/merged/results_nirenpuku_all.csv"
OUT_RACE = "data/merged/ev_explosion_race_analysis_2shahuku.csv"
OUT_RULE = "data/merged/ev_explosion_rule_scan_2shahuku.csv"

BET = 100
TOP_N = 1


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


def safe_qcut(series: pd.Series, q: int, labels=None):
    """
    重複値が多くても落ちにくい qcut
    """
    try:
        return pd.qcut(series, q=q, labels=labels, duplicates="drop")
    except Exception:
        # だめならcutにフォールバック
        return pd.cut(series, bins=q, labels=labels)


def summarize_group(df: pd.DataFrame, group_col: str):
    rows = []
    for key, g in df.groupby(group_col, dropna=False):
        bets = len(g)
        hits = int(g["hit"].sum())
        stake = bets * BET
        payout = int(g["payout"].sum())
        roi = payout / stake if stake > 0 else 0.0
        rows.append({
            "group": str(key),
            "bets": bets,
            "hits": hits,
            "hit_rate": hits / bets if bets > 0 else 0.0,
            "stake": stake,
            "payout": payout,
            "ROI": roi,
            "mean_EV": g["EV"].mean(),
            "mean_p": g["p"].mean(),
            "mean_odds": g["odds"].mean(),
            "mean_distortion_ratio": g["distortion_ratio"].mean() if "distortion_ratio" in g.columns else np.nan,
            "mean_rank_gap": g["rank_gap"].mean() if "rank_gap" in g.columns else np.nan,
            "mean_distortion_score": g["distortion_score"].mean() if "distortion_score" in g.columns else np.nan,
        })
    out = pd.DataFrame(rows).sort_values("ROI", ascending=False)
    return out


def main():
    df_t = pd.read_csv(TICKETS)
    df_r = pd.read_csv(RESULTS)

    # 使う列の整形
    num_cols = ["EV", "p", "odds", "distortion_ratio", "distortion_log", "distortion_z", "rank_gap", "distortion_score"]
    for c in num_cols:
        if c in df_t.columns:
            df_t[c] = pd.to_numeric(df_t[c], errors="coerce")

    df = df_t.merge(df_r, on="race_id", how="inner").copy()

    # 番兵・欠損除外
    df = df.dropna(subset=["EV", "p", "odds"])
    df = df[(df["odds"] > 1) & (df["odds"] < 9999)]

    # レースごとTOP1（distortion_scoreがあるならそれを優先、なければEV）
    sort_col = "distortion_score" if "distortion_score" in df.columns else "EV"
    df = df.sort_values(["race_id", sort_col], ascending=[True, False]).copy()
    df["rank"] = df.groupby("race_id").cumcount() + 1
    df_top = df[df["rank"] <= TOP_N].copy()

    # 的中判定
    df_top["bet_pair"] = df_top["買い目"].apply(normalize_pair)
    df_top["true_pair"] = df_top["nirenpuku_result"].apply(normalize_pair)
    df_top["hit"] = (df_top["bet_pair"] == df_top["true_pair"]).astype(int)
    df_top["payout"] = np.where(df_top["hit"] == 1, df_top["payout_nirenpuku_100"], 0)

    # EV爆発フラグ
    df_top["ev_gt_1"] = (df_top["EV"] > 1).astype(int)
    df_top["ev_gt_2"] = (df_top["EV"] > 2).astype(int)
    df_top["ev_gt_3"] = (df_top["EV"] > 3).astype(int)
    df_top["ev_gt_5"] = (df_top["EV"] > 5).astype(int)
    df_top["ev_gt_10"] = (df_top["EV"] > 10).astype(int)

    # ビン作成
    df_top["EV_bin"] = pd.cut(
        df_top["EV"],
        bins=[-999, 0, 1, 2, 3, 5, 10, 9999],
        labels=["<0", "0-1", "1-2", "2-3", "3-5", "5-10", "10+"]
    )

    df_top["p_bin"] = pd.cut(
        df_top["p"],
        bins=[0, 0.02, 0.04, 0.06, 0.08, 0.10, 1.0],
        labels=["0-2%", "2-4%", "4-6%", "6-8%", "8-10%", "10%+"]
    )

    df_top["odds_bin"] = pd.cut(
        df_top["odds"],
        bins=[0, 20, 50, 80, 120, 200, 300, 500, 99999],
        labels=["<20", "20-50", "50-80", "80-120", "120-200", "200-300", "300-500", "500+"]
    )

    if "distortion_ratio" in df_top.columns:
        df_top["ratio_bin"] = pd.cut(
            df_top["distortion_ratio"],
            bins=[0, 1, 1.5, 2, 3, 5, 10, 9999],
            labels=["<1", "1-1.5", "1.5-2", "2-3", "3-5", "5-10", "10+"]
        )
    else:
        df_top["ratio_bin"] = np.nan

    if "rank_gap" in df_top.columns:
        df_top["rank_gap_bin"] = pd.cut(
            df_top["rank_gap"],
            bins=[-999, 0, 3, 5, 8, 12, 999],
            labels=["<=0", "1-3", "4-5", "6-8", "9-12", "13+"]
        )
    else:
        df_top["rank_gap_bin"] = np.nan

    if "distortion_score" in df_top.columns:
        df_top["distortion_score_q"] = safe_qcut(df_top["distortion_score"], q=5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"])
    else:
        df_top["distortion_score_q"] = np.nan

    # レース単位保存
    race_cols = [
        "race_id", "競輪場", "レース番号", "開始時間", "買い目", "nirenpuku_result",
        "odds", "p", "EV", "hit", "payout",
        "distortion_ratio", "distortion_log", "distortion_z",
        "rank_gap", "distortion_score",
        "EV_bin", "p_bin", "odds_bin", "ratio_bin", "rank_gap_bin", "distortion_score_q"
    ]
    race_cols = [c for c in race_cols if c in df_top.columns]
    df_top[race_cols].to_csv(OUT_RACE, index=False, encoding="utf-8-sig")

    print("\n===== OVERALL =====")
    bets = len(df_top)
    hits = int(df_top["hit"].sum())
    stake = bets * BET
    payout = int(df_top["payout"].sum())
    roi = payout / stake if stake > 0 else 0.0
    print(f"bets={bets} hits={hits} hit_rate={hits / bets if bets else 0:.4f} stake={stake} payout={payout} ROI={roi:.4f}")

    print("\n===== EV BIN =====")
    ev_summary = summarize_group(df_top, "EV_bin")
    print(ev_summary.to_string(index=False))

    print("\n===== ODDS BIN =====")
    odds_summary = summarize_group(df_top, "odds_bin")
    print(odds_summary.to_string(index=False))

    print("\n===== P BIN =====")
    p_summary = summarize_group(df_top, "p_bin")
    print(p_summary.to_string(index=False))

    if "ratio_bin" in df_top.columns:
        print("\n===== DISTORTION RATIO BIN =====")
        ratio_summary = summarize_group(df_top, "ratio_bin")
        print(ratio_summary.to_string(index=False))
    else:
        ratio_summary = pd.DataFrame()

    if "rank_gap_bin" in df_top.columns:
        print("\n===== RANK GAP BIN =====")
        gap_summary = summarize_group(df_top, "rank_gap_bin")
        print(gap_summary.to_string(index=False))
    else:
        gap_summary = pd.DataFrame()

    if "distortion_score_q" in df_top.columns:
        print("\n===== DISTORTION SCORE QUINTILE =====")
        ds_summary = summarize_group(df_top, "distortion_score_q")
        print(ds_summary.to_string(index=False))
    else:
        ds_summary = pd.DataFrame()

    # ルール走査
    rules = []
    ev_mins = [0, 1, 2, 3, 5]
    odds_min_list = [0, 20, 50, 80]
    odds_max_list = [120, 200, 300, 500]
    ratio_mins = [1.0, 1.5, 2.0, 3.0, 5.0] if "distortion_ratio" in df_top.columns else [0]
    gap_mins = [0, 3, 5, 8, 12] if "rank_gap" in df_top.columns else [0]

    for ev_min in ev_mins:
        for odds_min in odds_min_list:
            for odds_max in odds_max_list:
                if odds_min >= odds_max:
                    continue
                for ratio_min in ratio_mins:
                    for gap_min in gap_mins:
                        cond = (df_top["EV"] >= ev_min) & (df_top["odds"] >= odds_min) & (df_top["odds"] < odds_max)
                        if "distortion_ratio" in df_top.columns:
                            cond &= (df_top["distortion_ratio"] >= ratio_min)
                        if "rank_gap" in df_top.columns:
                            cond &= (df_top["rank_gap"] >= gap_min)

                        g = df_top[cond]
                        if len(g) == 0:
                            continue

                        bets = len(g)
                        hits = int(g["hit"].sum())
                        stake = bets * BET
                        payout = int(g["payout"].sum())
                        roi = payout / stake if stake > 0 else 0.0

                        rules.append({
                            "EV_MIN": ev_min,
                            "odds_min": odds_min,
                            "odds_max": odds_max,
                            "ratio_min": ratio_min,
                            "rank_gap_min": gap_min,
                            "bets": bets,
                            "hits": hits,
                            "hit_rate": hits / bets if bets else 0.0,
                            "stake": stake,
                            "payout": payout,
                            "ROI": roi,
                            "mean_EV": g["EV"].mean(),
                            "mean_p": g["p"].mean(),
                            "mean_odds": g["odds"].mean(),
                        })

    rule_df = pd.DataFrame(rules)

    # 実用的なものだけ
    rule_df = rule_df[rule_df["bets"] >= 20].copy()
    rule_df = rule_df.sort_values(["ROI", "bets"], ascending=[False, False]).reset_index(drop=True)
    rule_df.to_csv(OUT_RULE, index=False, encoding="utf-8-sig")

    print("\n===== TOP RULES (bets>=20) =====")
    print(rule_df.head(30).to_string(index=False))

    print(f"\n[OUT] {OUT_RACE}")
    print(f"[OUT] {OUT_RULE}")


if __name__ == "__main__":
    main()