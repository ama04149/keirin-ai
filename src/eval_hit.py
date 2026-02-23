# src/eval_hit.py
import os
import re
import glob
import argparse
from datetime import datetime
from typing import Optional, Tuple, Dict, Any

import pandas as pd


# ---------------------------
# Utilities
# ---------------------------

def _read_latest_race_return_pkl(pattern: str = "race_return_*.pkl") -> Tuple[str, pd.DataFrame]:
    """race_return_YYYYMMDD.pkl を最新日付のものから読み込む。"""
    files = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No files matched: {pattern}")

    # ファイル名から日付抽出して最新を選ぶ（失敗したら末尾優先）
    def _extract_date(fp: str) -> str:
        m = re.search(r"race_return_(\d{8})\.pkl$", os.path.basename(fp))
        return m.group(1) if m else "00000000"

    files = sorted(files, key=_extract_date)
    latest = files[-1]
    df = pd.read_pickle(latest)
    return latest, df


def _safe_to_int(x) -> Optional[int]:
    try:
        if pd.isna(x):
            return None
        return int(x)
    except Exception:
        return None


def _parse_result_from_return_row(row: pd.Series) -> Tuple[Optional[str], Optional[float]]:
    """
    race_return の1行（= 3連単/3連複/ワイド等が混ざる）から
    「3連勝 単」の結果 "1-3-5" と払戻金(100円あたり)を返す。
    見つからなければ (None, None)
    """

    # まず "3 連 勝","単" の行だけ対象
    # あなたのデータ例： col6="3 連 勝" col7="単" col8="1-3-5  7,930円(32)"
    # ただし列名が 0..10 の数字だったりするので、値で判定する
    vals = [str(v) if not pd.isna(v) else "" for v in row.tolist()]

    # "3 連 勝" と "単" が含まれているか
    has_3ren = any("3" in v and "連" in v and "勝" in v for v in vals)
    has_tan = any(v.strip() == "単" or ("単" in v and "単勝" not in v) for v in vals)

    if not (has_3ren and has_tan):
        return None, None

    # 結果+払戻が入っていそうなセルを探す（"1-3-5  7,930円(32)" みたいなやつ）
    target = ""
    for v in vals:
        if re.search(r"\d+\s*-\s*\d+\s*-\s*\d+", v) and ("円" in v):
            target = v
            break

    if not target:
        # 形式が違う場合に備えて結果だけでも拾う
        for v in vals:
            if re.search(r"\d+\s*-\s*\d+\s*-\s*\d+", v):
                target = v
                break

    if not target:
        return None, None

    # 結果 "a-b-c" を抽出
    m_res = re.search(r"(\d+)\s*-\s*(\d+)\s*-\s*(\d+)", target)
    if not m_res:
        return None, None

    a, b, c = m_res.group(1), m_res.group(2), m_res.group(3)
    result = f"{int(a)}-{int(b)}-{int(c)}"

    # 払戻（100円あたり） "7,930円" を抽出
    m_pay = re.search(r"([\d,]+)\s*円", target)
    payout_100 = None
    if m_pay:
        payout_100 = float(m_pay.group(1).replace(",", ""))

    return result, payout_100


def build_sanrentan_result_table(df_return: pd.DataFrame) -> pd.DataFrame:
    """
    race_return（複数行/レース）から、
    race_id ごとの 3連単結果と払戻(100円)をまとめたテーブルを作る。
    return: columns = [race_id, sanrentan_result, payout_sanrentan_100]
    """

    # 期待：index が race_id（例: 2320260131030001）で重複あり
    if df_return.index is None:
        raise ValueError("race_return must have race_id as index (duplicated allowed).")

    # indexを列化
    df = df_return.copy()
    df["race_id"] = df.index.astype("string")

    rows = []
    for rid, grp in df.groupby("race_id"):
        found_res = None
        found_pay = None

        # 3連単行を探す
        for _, r in grp.iterrows():
            res, pay = _parse_result_from_return_row(r.drop(labels=["race_id"], errors="ignore"))
            if res is not None:
                found_res = res
                found_pay = pay
                break

        rows.append({
            "race_id": str(rid),
            "sanrentan_result": found_res,
            "payout_sanrentan_100": found_pay
        })

    out = pd.DataFrame(rows)
    return out


def add_hit_columns(df_eval: pd.DataFrame) -> pd.DataFrame:
    """
    best_bet と sanrentan_result を使って的中系の列を追加する
    """
    df = df_eval.copy()

    def _to_set(s):
        if pd.isna(s) or s is None or str(s).strip() == "":
            return None
        try:
            return set(map(int, str(s).split("-")))
        except Exception:
            return None

    def _nth(s, n):
        if pd.isna(s) or s is None or str(s).strip() == "":
            return None
        try:
            return int(str(s).split("-")[n])
        except Exception:
            return None

    df["bet_set"] = df["best_bet"].apply(_to_set)
    df["result_set"] = df["sanrentan_result"].apply(_to_set)

    # settled 判定：結果がある
    df["settled"] = df["sanrentan_result"].notna() & (df["sanrentan_result"].astype(str).str.len() > 0)

    # 的中（完全一致）
    df["hit_exact"] = df["settled"] & (df["best_bet"].astype(str) == df["sanrentan_result"].astype(str))

    # 3人一致（順不同）
    df["hit_set"] = df["settled"] & (df["bet_set"] == df["result_set"])

    # 着順別一致
    df["res_1"] = df["sanrentan_result"].apply(lambda x: _nth(x, 0))
    df["res_2"] = df["sanrentan_result"].apply(lambda x: _nth(x, 1))
    df["res_3"] = df["sanrentan_result"].apply(lambda x: _nth(x, 2))

    df["hit_first"] = df["settled"] & (df["first"].apply(_safe_to_int) == df["res_1"])
    df["hit_second"] = df["settled"] & (df["second"].apply(_safe_to_int) == df["res_2"])
    df["hit_third"] = df["settled"] & (df["third"].apply(_safe_to_int) == df["res_3"])

    # ステータス
    df["status"] = df["settled"].map(lambda x: "settled" if x else "pending")
    df["reason_unsettled"] = ""
    df.loc[df["status"] == "pending", "reason_unsettled"] = "before_start_or_not_scraped"

    return df


def calc_payout_profit(df_eval: pd.DataFrame) -> pd.DataFrame:
    """
    payout_sanrentan_100 と stake を使って payout / profit を計算
    """
    df = df_eval.copy()

    # 払戻：的中なら (payout_sanrentan_100 * stake/100)
    df["payout"] = 0.0
    mask_hit = df["hit_exact"].fillna(False)
    df.loc[mask_hit, "payout"] = df.loc[mask_hit, "payout_sanrentan_100"].fillna(0) * (df.loc[mask_hit, "stake"] / 100.0)

    # profit = payout - stake（settled/pendingに関係なく計算列として持つ）
    df["profit"] = df["payout"] - df["stake"]

    return df


def summarize(df_eval: pd.DataFrame) -> None:
    """
    コンソールにサマリを出す（あなたの出力に合わせた形）
    """
    total_bets = len(df_eval)

    settled = df_eval[df_eval["settled"]].copy()
    pending = df_eval[~df_eval["settled"]].copy()

    hit = int(settled["hit_exact"].sum()) if len(settled) else 0
    hit_rate = (hit / len(settled) * 100.0) if len(settled) else 0.0

    realized_stake = int(settled["stake"].sum()) if len(settled) else 0
    pending_stake = int(pending["stake"].sum()) if len(pending) else 0

    payout = float(settled["payout"].sum()) if len(settled) else 0.0
    realized_profit = payout - realized_stake

    print(f"[SUMMARY] bets={total_bets} settled={len(settled)} unsettled={len(pending)}")
    print(f"[SUMMARY] hit={hit} hit_rate={hit_rate:.3f}%")
    print(f"[SUMMARY] realized_stake={realized_stake} payout={int(payout)} profit={int(realized_profit)}")
    print(f"[SUMMARY] pending_stake={pending_stake}")


# ---------------------------
# Main pipeline
# ---------------------------

def run_eval(
    bets_csv: str = "keirin_kelly_bets.csv",
    race_return_pkl: Optional[str] = None,
    out_csv: str = "keirin_eval_hit.csv"
) -> pd.DataFrame:
    # 1) bets 読み込み
    if not os.path.exists(bets_csv):
        raise FileNotFoundError(f"bets csv not found: {bets_csv}")

    df_bets = pd.read_csv(bets_csv, dtype={"race_id": "string"})
    #df_bets["payout"] = pd.to_numeric(df_bets.get("payout", 0), errors="coerce").fillna(0.0).astype(float)
    df_bets["payout"] = pd.to_numeric(df_bets["payout"] if "payout" in df_bets.columns else pd.Series(0, index=df_bets.index), errors="coerce").fillna(0.0).astype(float)
    required = ["race_id", "best_bet", "first", "second", "third", "stake"]
    for c in required:
        if c not in df_bets.columns:
            raise KeyError(f"bets_csv missing column: {c}")

    # 2) race_return 読み込み
    if race_return_pkl is None:
        fp, df_return = _read_latest_race_return_pkl("race_return_*.pkl")
        print(f"[INFO] use latest race_return: {fp}")
    else:
        if not os.path.exists(race_return_pkl):
            raise FileNotFoundError(f"race_return pkl not found: {race_return_pkl}")
        df_return = pd.read_pickle(race_return_pkl)
        print(f"[INFO] use race_return: {race_return_pkl}")

    # 3) 結果テーブル作成（race_id -> sanrentan_result, payout_100）
    df_res = build_sanrentan_result_table(df_return)

    # 4) マージ
    df_eval = pd.merge(df_bets, df_res, on="race_id", how="left")

    # 5) 判定列追加
    df_eval = add_hit_columns(df_eval)

    # 6) 払戻/損益計算
    df_eval = calc_payout_profit(df_eval)

    # 7) 出力
    df_eval.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"[OK] eval csv: {out_csv}")

    # 8) サマリ
    summarize(df_eval)

    return df_eval


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bets", default="keirin_kelly_bets.csv", help="bets csv path")
    ap.add_argument("--return", dest="race_return", default=None, help="race_return pkl path (optional)")
    ap.add_argument("--out", default="keirin_eval_hit.csv", help="output csv path")
    args = ap.parse_args()

    run_eval(bets_csv=args.bets, race_return_pkl=args.race_return, out_csv=args.out)


if __name__ == "__main__":
    main()
