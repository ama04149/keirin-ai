# src/export_results_nirenpuku.py
import glob
import re
import unicodedata
import pandas as pd


def find_latest_race_return(pattern="race_return_*.pkl") -> str:
    files = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError(f"no race_return pkl found: {pattern}")
    return files[-1]


def norm(x) -> str:
    """NFKC + 全空白除去"""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    s = unicodedata.normalize("NFKC", str(x))
    s = "".join(ch for ch in s if not ch.isspace())
    return s


def get_race_id(idx, row) -> str:
    if "race_id" in row.index:
        v = row["race_id"]
        if v is not None and not (isinstance(v, float) and pd.isna(v)):
            return str(v)
    return str(idx)


def find_bet_block(vals: list[str], target: str, max_block: int = 4):
    """
    連続セル結合で target になる場所 (start, k) を返す。
    例: ["2車連","複"] -> "2車連複"
    """
    n = len(vals)
    for start in range(n):
        acc = ""
        for k in range(1, max_block + 1):
            if start + k > n:
                break
            acc += vals[start + k - 1]
            if acc == target:
                return start, k
    return None


# 重要：車番は基本 1桁（1〜9）なので、結果は1桁-1桁として抜く
# 例: "3=62,480円(6)" でも a=3 b=6 pay=2,480 を正しく拾える
PAT = re.compile(r"(?P<a>\d)[=\-](?P<b>\d)\s*(?P<pay>[\d,]+)円")


def extract_nirenpuku_from_first11(row):
    """
    先頭11セルで「2車連複」をセルまたぎで検出し、
    その“以降の文字列を結合”したものから 結果(1桁-1桁) と 配当 を抽出する。
    """
    vals = [norm(v) for v in row.iloc[:11].tolist()]

    hit = find_bet_block(vals, target="2車連複", max_block=4)
    if hit is None:
        return None, None

    start, k = hit
    tail = "".join(vals[start + k :])  # 直後以降を全部結合して検索

    m = PAT.search(tail)
    if not m:
        return None, None

    a = int(m.group("a"))
    b = int(m.group("b"))
    pay = int(m.group("pay").replace(",", ""))

    # 二車複は順不同なので小さい順に統一
    x, y = sorted([a, b])
    res = f"{x}-{y}"

    return res, pay


def parse_nirenpuku(df: pd.DataFrame) -> pd.DataFrame:
    rec = []
    for idx, row in df.iterrows():
        race_id = get_race_id(idx, row)
        res, pay = extract_nirenpuku_from_first11(row)
        if res and (pay is not None):
            rec.append(
                {"race_id": race_id, "nirenpuku_result": res, "payout_nirenpuku_100": int(pay)}
            )

    out = pd.DataFrame(rec)
    if out.empty:
        return out
    out["race_id"] = out["race_id"].astype("string")
    out = out.drop_duplicates(subset=["race_id"], keep="last").reset_index(drop=True)
    return out


def main():
    latest = find_latest_race_return()
    print(f"[INFO] use latest race_return: {latest}")

    df = pd.read_pickle(latest)
    out = parse_nirenpuku(df)

    out_csv = "keirin_results_nirenpuku.csv"
    out.to_csv(out_csv, index=False, encoding="utf-8-sig")

    print(f"[OK] results csv: {out_csv}")
    print("rows:", len(out))
    if len(out) > 0:
        print(out.head(10).to_string(index=False))
    else:
        print("\n[WARN] extracted 0 rows.")
        print("[DIAG] row0 first11 norm tokens:")
        vals0 = [norm(v) for v in df.iloc[0, :11].tolist()]
        print(vals0)
        print("[DIAG] concatenations around tokens:")
        for i in range(len(vals0)):
            for k in range(1, 5):
                if i + k <= len(vals0):
                    s = "".join(vals0[i:i+k])
                    if "車" in s or "連" in s or "複" in s:
                        print(i, k, s)


if __name__ == "__main__":
    main()