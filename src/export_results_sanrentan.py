# src/export_results_sanrentan.py
import os
import re
import glob
import pandas as pd

def find_latest_race_return(pattern="race_return_*.pkl") -> str:
    files = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError(f"no race_return pkl found: {pattern}")
    return files[-1]

def parse_sanrentan_from_race_return(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # ★ race_id が列にあるならそれを使う。無い場合だけ index → race_id 化
    if "race_id" not in df.columns:
        # index 名が None のこともあるので、素直に reset_index してから race_id にする
        df = df.reset_index(drop=False)
        # reset_index後の列名は index名 or "index"
        if "race_id" not in df.columns:
            if "index" in df.columns:
                df = df.rename(columns={"index": "race_id"})
            else:
                # まれに index名が入っている場合
                idx_name = df.index.name
                if idx_name and idx_name in df.columns:
                    df = df.rename(columns={idx_name: "race_id"})

    # 型は文字列に統一
    df["race_id"] = df["race_id"].astype("string")

    df = df.reset_index().rename(columns={df.index.name: "race_id"})

    # 列名が 0..10 の想定（あなたの表示に合わせる）
    # 3連勝単: col6="3 連 勝", col7="単", col8="1-3-5  7,930円(32)" のような文字列
    if 8 not in df.columns or 6 not in df.columns or 7 not in df.columns:
        # 列が文字列 "6" "7" "8" になっているケースも吸収
        cols = set(map(str, df.columns))
        if {"6", "7", "8"}.issubset(cols):
            df = df.rename(columns={"6": 6, "7": 7, "8": 8})
        else:
            raise KeyError(f"unexpected race_return columns: {df.columns.tolist()}")

    # 3連勝・単の行だけ
    m = (df[6].astype(str).str.contains("3", na=False)) & (df[6].astype(str).str.contains("連", na=False)) \
        & (df[6].astype(str).str.contains("勝", na=False)) \
        & (df[7].astype(str).str.contains("単", na=False))

    tmp = df.loc[m, ["race_id", 8]].copy()
    tmp.columns = ["race_id", "text"]

    # 例: "1-3-5  7,930円(32)"
    pat = re.compile(r"(?P<res>\d+-\d+-\d+)\s+(?P<pay>[\d,]+)円")
    tmp["sanrentan_result"] = tmp["text"].astype(str).str.extract(pat)["res"]
    tmp["payout_sanrentan_100"] = (
        tmp["text"].astype(str).str.extract(pat)["pay"]
        .str.replace(",", "", regex=False)
    )

    # 数値化（欠損は0）
    tmp["payout_sanrentan_100"] = pd.to_numeric(tmp["payout_sanrentan_100"], errors="coerce").fillna(0).astype(int)

    out = tmp[["race_id", "sanrentan_result", "payout_sanrentan_100"]].copy()
    # race_idごとに1行に（同じレースが重複したら最後を採用）
    out = out.dropna(subset=["race_id"]).drop_duplicates(subset=["race_id"], keep="last").reset_index(drop=True)
    return out

def main():
    latest = find_latest_race_return()
    print(f"[INFO] use latest race_return: {latest}")

    df_return = pd.read_pickle(latest)
    df_res = parse_sanrentan_from_race_return(df_return)

    out_csv = "keirin_results_sanrentan.csv"
    df_res.to_csv(out_csv, index=False, encoding="utf-8-sig")

    print(f"[OK] results csv: {out_csv}")
    print(df_res.head(5).to_string(index=False))

if __name__ == "__main__":
    main()
