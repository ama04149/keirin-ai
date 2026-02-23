# analyze_daily.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Optional, List, Dict

import numpy as np
import pandas as pd
from datetime import date

def _exists_cols(df: pd.DataFrame, cols: List[str]) -> List[str]:
    return [c for c in cols if c in df.columns]


def _to_bool_series(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s
    return s.astype(str).str.lower().isin(["true", "1", "yes", "y"])


def _safe_numeric(df: pd.DataFrame, cols: List[str]) -> None:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")


def _cut_safe(x: pd.Series, bins: List[float]) -> pd.Series:
    try:
        return pd.cut(x, bins=bins, right=True, include_lowest=True)
    except Exception:
        return pd.Series([np.nan] * len(x), index=x.index)


@dataclass
class BucketConfig:
    p_bins: List[float] = None
    odds_bins: List[float] = None
    ev_bins: List[float] = None

    def __post_init__(self):
        if self.p_bins is None:
            self.p_bins = [0.0, 0.001, 0.002, 0.003, 0.005, 0.008, 0.012, 0.02, 0.04, 1.0]
        if self.odds_bins is None:
            self.odds_bins = [0, 10, 50, 100, 300, 500, 1000, 3000, 10000, np.inf]
        if self.ev_bins is None:
            self.ev_bins = [0, 0.5, 0.8, 1.0, 1.2, 1.5, 2, 5, 10, 30, 100, np.inf]


def load_inputs(eval_csv: str, bets_csv: Optional[str] = None) -> pd.DataFrame:
    if not os.path.exists(eval_csv):
        raise FileNotFoundError(f"eval csv not found: {eval_csv}")

    df = pd.read_csv(eval_csv, encoding="utf-8-sig")
    from datetime import date
    df["bet_date"] = date.today().isoformat()


    # 型調整
    _safe_numeric(df, [
        "stake", "payout", "profit",
        "best_odds", "best_p", "max_EV", "expected_profit",
        "kelly_full", "kelly_frac_capped", "stake_raw",
        "payout_sanrentan_100",
    ])
    for c in _exists_cols(df, ["race_id", "競輪場", "レース番号", "開始時間", "best_bet", "sanrentan_result", "status", "reason_unsettled"]):
        df[c] = df[c].astype(str)

    # bool列
    for bc in ["settled", "hit_exact", "hit_set", "hit_first", "hit_second", "hit_third"]:
        if bc in df.columns:
            df[bc] = _to_bool_series(df[bc])

    # payout/profit が無い場合は補完
    if "payout" not in df.columns:
        df["payout"] = 0.0
    if "profit" not in df.columns:
        # profit = payout - stake
        if "stake" in df.columns:
            df["profit"] = df["payout"] - df["stake"]
        else:
            df["profit"] = df["payout"]

    # mult_ev（倍率EV）と ev_unit（1単位期待値）を追加
    if "best_p" in df.columns and "best_odds" in df.columns:
        df["mult_ev"] = df["best_p"] * df["best_odds"]
        df["ev_unit"] = df["mult_ev"] - 1.0
    else:
        df["mult_ev"] = np.nan
        df["ev_unit"] = np.nan

    # bets_csvで補完（必要なら）
    if bets_csv and os.path.exists(bets_csv):
        df_b = pd.read_csv(bets_csv, encoding="utf-8-sig")
        _safe_numeric(df_b, ["stake", "best_odds", "best_p", "max_EV", "expected_profit"])
        for c in _exists_cols(df_b, ["race_id", "best_bet", "競輪場", "レース番号", "開始時間"]):
            df_b[c] = df_b[c].astype(str)

        join_keys = [k for k in ["race_id", "best_bet"] if k in df.columns and k in df_b.columns]
        if join_keys:
            add_cols = [c for c in df_b.columns if c not in df.columns]
            df = df.merge(df_b[join_keys + add_cols], on=join_keys, how="left")

    return df


def make_daily_summary(df: pd.DataFrame) -> pd.DataFrame:
    settled_mask = df["settled"] if "settled" in df.columns else pd.Series([True]*len(df), index=df.index)
    unsettled_mask = ~settled_mask

    stake = df["stake"] if "stake" in df.columns else pd.Series([0]*len(df), index=df.index)
    payout = df["payout"]
    profit = df["profit"]

    # 的中は「完全一致(hit_exact)」を基本に、集合一致(hit_set)も併記
    hit_exact = df["hit_exact"] if "hit_exact" in df.columns else pd.Series([False]*len(df), index=df.index)
    hit_set = df["hit_set"] if "hit_set" in df.columns else pd.Series([False]*len(df), index=df.index)

    total_bets = len(df)
    settled_bets = int(settled_mask.sum())
    unsettled_bets = int(unsettled_mask.sum())

    realized_stake = float(stake[settled_mask].sum())
    pending_stake = float(stake[unsettled_mask].sum())

    realized_payout = float(payout[settled_mask].sum())
    realized_profit = float(profit[settled_mask].sum())

    hit_exact_cnt = int(hit_exact[settled_mask].sum())
    hit_set_cnt = int(hit_set[settled_mask].sum())

    hit_exact_rate = (hit_exact_cnt / settled_bets) if settled_bets > 0 else np.nan
    hit_set_rate = (hit_set_cnt / settled_bets) if settled_bets > 0 else np.nan

    row = {
        "bets": total_bets,
        "settled": settled_bets,
        "unsettled": unsettled_bets,
        "hit_exact": hit_exact_cnt,
        "hit_exact_rate": hit_exact_rate,
        "hit_set": hit_set_cnt,
        "hit_set_rate": hit_set_rate,
        "stake_realized": realized_stake,
        "stake_pending": pending_stake,
        "payout_realized": realized_payout,
        "profit_realized": realized_profit,
        # 参考統計
        "best_p_mean": float(pd.to_numeric(df.get("best_p", np.nan), errors="coerce").mean()),
        "best_odds_mean": float(pd.to_numeric(df.get("best_odds", np.nan), errors="coerce").mean()),
        "mult_ev_mean": float(pd.to_numeric(df.get("mult_ev", np.nan), errors="coerce").mean()),
    }
    return pd.DataFrame([row])


def make_race_summary(df: pd.DataFrame) -> pd.DataFrame:
    keys = _exists_cols(df, ["race_id", "競輪場", "レース番号", "開始時間"])
    if "race_id" not in keys:
        raise ValueError("race_id is required for race_summary")

    tmp = df.copy()
    tmp["_stake"] = tmp["stake"] if "stake" in tmp.columns else 0.0
    tmp["_payout"] = tmp["payout"]
    tmp["_profit"] = tmp["profit"]
    tmp["_settled"] = tmp["settled"].astype(int) if "settled" in tmp.columns else 1

    tmp["_hit_exact"] = tmp["hit_exact"].astype(int) if "hit_exact" in tmp.columns else 0
    tmp["_hit_set"] = tmp["hit_set"].astype(int) if "hit_set" in tmp.columns else 0

    out = tmp.groupby(keys, dropna=False).agg(
        bets=("_stake", "count"),
        settled_bets=("_settled", "sum"),
        stake=("_stake", "sum"),
        payout=("_payout", "sum"),
        profit=("_profit", "sum"),
        hit_exact=("_hit_exact", "sum"),
        hit_set=("_hit_set", "sum"),
    ).reset_index()

    out["hit_exact_rate"] = out.apply(lambda r: (r["hit_exact"]/r["settled_bets"]) if r["settled_bets"]>0 else np.nan, axis=1)
    out["hit_set_rate"] = out.apply(lambda r: (r["hit_set"]/r["settled_bets"]) if r["settled_bets"]>0 else np.nan, axis=1)

    out = out.sort_values(["開始時間", "競輪場", "レース番号"], ascending=[True, True, True], kind="mergesort")
    return out


def make_bucket_summary(df: pd.DataFrame, cfg: BucketConfig) -> pd.DataFrame:
    base = df[df["settled"]].copy() if "settled" in df.columns else df.copy()
    if len(base) == 0:
        return pd.DataFrame()

    base["_stake"] = base["stake"] if "stake" in base.columns else 0.0
    base["_payout"] = base["payout"]
    base["_profit"] = base["profit"]
    base["_hit_exact"] = base["hit_exact"].astype(int) if "hit_exact" in base.columns else 0

    if "best_p" in base.columns:
        base["_p_bucket"] = _cut_safe(base["best_p"], cfg.p_bins)
    else:
        base["_p_bucket"] = np.nan

    if "best_odds" in base.columns:
        base["_odds_bucket"] = _cut_safe(base["best_odds"], cfg.odds_bins)
    else:
        base["_odds_bucket"] = np.nan

    if "mult_ev" in base.columns:
        base["_ev_bucket"] = _cut_safe(base["mult_ev"], cfg.ev_bins)
    else:
        base["_ev_bucket"] = np.nan

    rows = []
    for col, name in [("_p_bucket", "best_p"), ("_odds_bucket", "best_odds"), ("_ev_bucket", "mult_ev")]:
        tmp = base.dropna(subset=[col]).copy()
        if len(tmp) == 0:
            continue
        g = tmp.groupby(col, dropna=False, observed=False).agg(
            count=("_stake", "count"),
            hit_exact=("_hit_exact", "sum"),
            stake=("_stake", "sum"),
            payout=("_payout", "sum"),
            profit=("_profit", "sum"),
            avg_best_p=("best_p", "mean") if "best_p" in tmp.columns else ("_stake", lambda x: np.nan),
            avg_best_odds=("best_odds", "mean") if "best_odds" in tmp.columns else ("_stake", lambda x: np.nan),
            avg_mult_ev=("mult_ev", "mean") if "mult_ev" in tmp.columns else ("_stake", lambda x: np.nan),
        ).reset_index().rename(columns={col: "bucket"})
        g["bucket_type"] = name
        g["hit_exact_rate"] = g.apply(lambda r: (r["hit_exact"]/r["count"]) if r["count"]>0 else np.nan, axis=1)
        rows.append(g)

    return pd.concat(rows, ignore_index=True).sort_values(["bucket_type", "bucket"], kind="mergesort")


def make_unsettled_list(df: pd.DataFrame) -> pd.DataFrame:
    if "settled" not in df.columns:
        return pd.DataFrame(columns=df.columns)
    return df[~df["settled"]].copy()


def run(eval_csv: str, bets_csv: Optional[str], out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    cfg = BucketConfig()

    df = load_inputs(eval_csv, bets_csv=bets_csv)

    daily = make_daily_summary(df)
    race = make_race_summary(df)
    bucket = make_bucket_summary(df, cfg)
    unsettled = make_unsettled_list(df)

    p1 = os.path.join(out_dir, "daily_summary.csv")
    p2 = os.path.join(out_dir, "race_summary.csv")
    p3 = os.path.join(out_dir, "bucket_summary.csv")
    p4 = os.path.join(out_dir, "unsettled_list.csv")

    daily.to_csv(p1, index=False, encoding="utf-8-sig")
    race.to_csv(p2, index=False, encoding="utf-8-sig")
    bucket.to_csv(p3, index=False, encoding="utf-8-sig")
    unsettled.to_csv(p4, index=False, encoding="utf-8-sig")

    # コンソール表示（最小）
    r = daily.iloc[0].to_dict()
    print("[DAILY]")
    print(f"bets={int(r['bets'])} settled={int(r['settled'])} unsettled={int(r['unsettled'])}")
    if pd.notna(r["hit_exact_rate"]):
        print(f"hit_exact={int(r['hit_exact'])} hit_exact_rate={r['hit_exact_rate']*100:.3f}%")
    else:
        print("hit_exact_rate=NA")
    if pd.notna(r["hit_set_rate"]):
        print(f"hit_set={int(r['hit_set'])} hit_set_rate={r['hit_set_rate']*100:.3f}%")
    print(f"realized_stake={r['stake_realized']:.0f} realized_payout={r['payout_realized']:.0f} realized_profit={r['profit_realized']:.0f}")
    print(f"pending_stake={r['stake_pending']:.0f}")

    print("[OUTPUT]")
    print(p1)
    print(p2)
    print(p3)
    print(p4)


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval_csv", default="keirin_eval_hit.csv")
    ap.add_argument("--bets_csv", default="keirin_kelly_bets.csv")
    ap.add_argument("--out_dir", default=".")
    return ap.parse_args()


if __name__ == "__main__":
    args = parse_args()
    bets_csv = args.bets_csv if args.bets_csv and os.path.exists(args.bets_csv) else None
    run(args.eval_csv, bets_csv=bets_csv, out_dir=args.out_dir)
