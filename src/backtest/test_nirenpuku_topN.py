import pandas as pd
import re

TICKETS = "data/merged/ev_tickets_all.csv"
RESULTS = "data/merged/results_sanrentan_all.csv"

TOP_N = 3          # 二車複で買う上位ペア数
BET = 100          # 固定100円（ROI計算するなら配当が必要）
INITIAL_BANKROLL = 100_000

def normalize(s: str) -> str:
    s = str(s).strip()
    # 区切りゆれ対策（念のため）
    s = s.replace("－", "-").replace("―", "-").replace("−", "-").replace("–", "-").replace("—", "-")
    s = re.sub(r"\s+", "", s)
    return s

def parse_trifecta(ticket: str):
    t = normalize(ticket)
    parts = t.split("-")
    if len(parts) != 3:
        return None
    return parts[0], parts[1], parts[2]

def true_pair_from_sanrentan_result(res: str):
    # sanrentan_result は "a-b-c"（順序付き）のはず → 二車複は上位2人の集合
    a, b, _ = parse_trifecta(res)
    # unordered pair key
    x, y = sorted([a, b], key=lambda z: int(z))
    return f"{x}-{y}"

def pair_key(a: str, b: str) -> str:
    x, y = sorted([a, b], key=lambda z: int(z))
    return f"{x}-{y}"

# 読み込み
df_t = pd.read_csv(TICKETS)
df_r = pd.read_csv(RESULTS)

# 結果のあるレースだけ
df = df_t.merge(df_r[["race_id", "sanrentan_result"]], on="race_id", how="inner").copy()

# 三連単→二車複ペア確率へ集約
rows = []
for race_id, g in df.groupby("race_id"):
    # 真の二車複（1着2着のペア）
    true_pair = true_pair_from_sanrentan_result(g["sanrentan_result"].iloc[0])

    # ペア確率を蓄積： Σ p(a-b-c) + p(b-a-c)
    pair_prob = {}

    for _, r in g.iterrows():
        parsed = parse_trifecta(r["買い目"])
        if parsed is None:
            continue
        a, b, c = parsed
        p = float(r["p"])

        # a,b が1-2着の順序付き三連単だけを二車複の確率に足す（cは3着）
        k = pair_key(a, b)
        pair_prob[k] = pair_prob.get(k, 0.0) + p

    # 上位TOP_Nのペアを選ぶ
    ranked = sorted(pair_prob.items(), key=lambda x: x[1], reverse=True)[:TOP_N]
    chosen_pairs = [k for k, _ in ranked]

    hit = true_pair in chosen_pairs

    rows.append({
        "race_id": race_id,
        "true_pair": true_pair,
        "chosen_pairs": ",".join(chosen_pairs),
        "hit": hit,
        "top_pair_prob": ranked[0][1] if ranked else 0.0,
    })

res = pd.DataFrame(rows)

# 固定BETで「投資額」だけは計算（回収は二車複配当が無いので未計算）
races = len(res)
hit_races = int(res["hit"].sum())
stake = races * TOP_N * BET
hit_rate = hit_races / races if races else 0

print("races:", races)
print(f"TOP_N (pairs): {TOP_N}")
print("hit races:", hit_races, "/", races, f"({hit_rate*100:.2f}%)")
print("stake (yen):", stake)

# 詳細出力
out_path = "data/merged/test_nirenpuku_topN_detail.csv"
res.to_csv(out_path, index=False)
print("[OUT]", out_path)