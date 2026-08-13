import glob
import re
import unicodedata
import pandas as pd

# "3=62,480円(6)" / "6-3 3,460円(13)" などから拾う
PAT = re.compile(r"(?P<a>\d)[=\-](?P<b>\d)\s*(?P<pay>[\d,]+)円")

def norm(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    s = unicodedata.normalize("NFKC", str(x))
    # 空白除去
    s = "".join(ch for ch in s if not ch.isspace())
    return s

def extract_nirenpuku_from_row(row) -> tuple[str|None, int|None]:
    """
    row全体（全列）を結合して "2車連複" の直後から結果を抽出する
    """
    # ✅ 先頭11だけでなく、全列を対象にする
    vals = [norm(v) for v in row.tolist()]
    blob = "".join(vals)

    # 2車連単と混ざらないよう、まず「2車連複」の位置を確定
    key = "2車連複"
    pos = blob.find(key)
    if pos < 0:
        return None, None

    tail = blob[pos + len(key):]  # 2車連複の後ろ全部

    m = PAT.search(tail)
    if not m:
        return None, None

    a = int(m.group("a"))
    b = int(m.group("b"))
    pay = int(m.group("pay").replace(",", ""))

    x, y = sorted([a, b])
    return f"{x}-{y}", pay

def load_one_pkl(path: str) -> pd.DataFrame:
    df = pd.read_pickle(path)

    rec = []
    for idx, row in df.iterrows():
        race_id = str(idx)  # indexがrace_id
        res, pay = extract_nirenpuku_from_row(row)
        if res is None:
            continue
        rec.append({
            "race_id": race_id,
            "nirenpuku_result": res,
            "payout_nirenpuku_100": pay
        })
    return pd.DataFrame(rec)

def main():
    pkls = sorted(glob.glob("race_return_????????.pkl"))
    if not pkls:
        raise FileNotFoundError("race_return_YYYYMMDD.pkl not found")

    frames = []
    for p in pkls:
        try:
            d = load_one_pkl(p)
            if not d.empty:
                frames.append(d)
        except Exception as e:
            print("[WARN] skip:", p, "err:", repr(e))

    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["race_id", "nirenpuku_result", "payout_nirenpuku_100"]
    )

    if out.empty:
        print("[WARN] extracted 0 rows")
    else:
        out["race_id"] = out["race_id"].astype("string")
        out["payout_nirenpuku_100"] = pd.to_numeric(out["payout_nirenpuku_100"], errors="coerce").fillna(0).astype(int)
        out = out.drop_duplicates(subset=["race_id"], keep="last").reset_index(drop=True)

    out_csv = "keirin_results_nirenpuku.csv"  # run_pipeline SAVE対象名
    out.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print("[OK] written:", out_csv, "rows:", len(out))
    if len(out) > 0:
        print(out.head(10).to_string(index=False))

if __name__ == "__main__":
    main()