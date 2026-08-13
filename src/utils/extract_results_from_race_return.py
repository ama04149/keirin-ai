import re
from pathlib import Path
import pandas as pd

# ===== 入力（ここだけ実ファイルに合わせる）=====
RACE_RETURN_PKL = Path("race_return_20260227.pkl")  # ←最新のpklに合わせて変更

# ===== 出力 =====
OUT_NIRENPUKU = Path("data/keirin_results_nirenpuku.csv")
OUT_SANRENTAN = Path("data/keirin_results_sanrentan.csv")  # すでにあるなら上書きOK


def norm_text(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    s = str(x)
    s = re.sub(r"\s+", "", s)  # 全部の空白を消す（"2 車 連 複" -> "2車連複"）
    return s


def parse_payout_100(s: str):
    """
    "2,480円(6)" -> 2480
    "未発売" -> None
    """
    s = norm_text(s)
    if not s or "未発売" in s:
        return None
    m = re.search(r"([\d,]+)円", s)
    if not m:
        return None
    return int(m.group(1).replace(",", ""))


def normalize_result(s: str) -> str:
    """
    "3=6" -> "3-6"
    "6-3-1" -> "6-3-1" （そのまま）
    "1=3=6" -> "1-3-6"
    """
    s = norm_text(s)
    if not s:
        return ""
    s = s.replace("=", "-")
    return s


def extract_from_row(row, bet_name: str):
    """
    row内に "2車連複" などが見つかったら、その右隣2セルを (result, payout) として返す想定。
    例:
      [ ..., "2車連複", "3=6", "2,480円(6)", ... ]
    """
    values = [norm_text(v) for v in row.tolist()]
    for i, v in enumerate(values):
        if v == bet_name:
            result = values[i + 1] if i + 1 < len(values) else ""
            payout = values[i + 2] if i + 2 < len(values) else ""
            return normalize_result(result), parse_payout_100(payout)
    return "", None


def main():
    if not RACE_RETURN_PKL.exists():
        raise FileNotFoundError(f"Not found: {RACE_RETURN_PKL}")

    df = pd.read_pickle(RACE_RETURN_PKL)

    # race_id が列としても index としてもあり得るので両対応
    if "race_id" in df.columns:
        race_ids = df["race_id"].astype(str)
    else:
        race_ids = df.index.astype(str)

    # 列0..10に賭式情報が入っているようなので「全列」対象にして探す
    # （余計な列があっても extract_from_row がスキャンするので問題なし）
    niren_records = []
    sanrentan_records = []

    for idx, row in df.iterrows():
        race_id = str(row["race_id"]) if "race_id" in df.columns else str(idx)

        # 2車連複（=二車複）
        niren_res, niren_pay = extract_from_row(row, "2車連複")
        if niren_res and niren_pay is not None:
            niren_records.append({
                "race_id": race_id,
                "nirenpuku_result": niren_res,
                "payout_nirenpuku_100": int(niren_pay),
            })

        # 3連勝単（=三連単）
        san_res, san_pay = extract_from_row(row, "3連勝単")
        if san_res and san_pay is not None:
            sanrentan_records.append({
                "race_id": race_id,
                "sanrentan_result": san_res,
                "payout_sanrentan_100": int(san_pay),
            })

    # race_idごとに1行へ（同じrace_idが複数行あるため）
    if niren_records:
        df_n = pd.DataFrame(niren_records).drop_duplicates(subset=["race_id"], keep="last")
        df_n.to_csv(OUT_NIRENPUKU, index=False)
        print("[OK] wrote:", OUT_NIRENPUKU, "rows:", len(df_n))
    else:
        print("[WARN] no nirenpuku records extracted")

    if sanrentan_records:
        df_s = pd.DataFrame(sanrentan_records).drop_duplicates(subset=["race_id"], keep="last")
        df_s.to_csv(OUT_SANRENTAN, index=False)
        print("[OK] wrote:", OUT_SANRENTAN, "rows:", len(df_s))
    else:
        print("[WARN] no sanrentan records extracted")


if __name__ == "__main__":
    main()