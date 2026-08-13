import glob
import re
import unicodedata
import pandas as pd

PAT = re.compile(r"(?P<a>\d)[=\-](?P<b>\d)\s*(?P<pay>[\d,]+)円")

def norm(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    s = unicodedata.normalize("NFKC", str(x))
    s = "".join(ch for ch in s if not ch.isspace())
    return s

def find_bet_block(vals: list[str], target: str, max_block: int = 4):
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

def extract_nirenpuku(row) -> tuple[str|None, int|None]:
    vals = [norm(v) for v in row.iloc[:11].tolist()]
    hit = find_bet_block(vals, "2車連複", max_block=4)
    if hit is None:
        return None, None
    start, k = hit
    tail = "".join(vals[start + k:])
    m = PAT.search(tail)
    if not m:
        return None, None
    a = int(m.group("a")); b = int(m.group("b"))
    pay = int(m.group("pay").replace(",", ""))
    x, y = sorted([a, b])
    return f"{x}-{y}", pay

def load_one_pkl(path: str) -> pd.DataFrame:
    df = pd.read_pickle(path)

    # race_id は index の場合が多いので idx から採用
    rec = []
    for idx, row in df.iterrows():
        race_id = str(idx)
        res, pay = extract_nirenpuku(row)
        if res is None:
            continue
        rec.append({"race_id": race_id, "nirenpuku_result": res, "payout_nirenpuku_100": pay})
    return pd.DataFrame(rec)

def main():
    pkls = sorted(glob.glob("race_return_*.pkl"))
    if not pkls:
        raise FileNotFoundError("race_return_*.pkl not found")

    all_df = []
    for p in pkls:
        try:
            d = load_one_pkl(p)
            if not d.empty:
                all_df.append(d)
        except Exception:
            continue

    out = pd.concat(all_df, ignore_index=True) if all_df else pd.DataFrame(
        columns=["race_id","nirenpuku_result","payout_nirenpuku_100"]
    )

    if out.empty:
        print("[WARN] extracted 0 rows from all pkls")
    else:
        out["race_id"] = out["race_id"].astype("string")
        out["payout_nirenpuku_100"] = pd.to_numeric(out["payout_nirenpuku_100"], errors="coerce").fillna(0).astype(int)
        out = out.drop_duplicates(subset=["race_id"], keep="last").reset_index(drop=True)

    out_csv = "data/keirin_results_nirenpuku.csv"
    out.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print("[OK]", out_csv, "rows:", len(out))
    if len(out) > 0:
        print(out.head(10).to_string(index=False))

if __name__ == "__main__":
    main()