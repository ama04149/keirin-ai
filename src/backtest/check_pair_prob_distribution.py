import pandas as pd
import re

TICKETS = "data/merged/ev_tickets_all.csv"

def normalize(s: str) -> str:
    s = str(s).strip()
    s = re.sub(r"[－―−–—]", "-", s)
    s = re.sub(r"\s+", "", s)
    return s

def parse_trifecta(ticket: str):
    t = normalize(ticket)
    parts = t.split("-")
    if len(parts) != 3:
        return None
    return parts[0], parts[1], parts[2]

def pair_key(a: str, b: str) -> str:
    x, y = sorted([int(a), int(b)])
    return f"{x}-{y}"

def main():
    df = pd.read_csv(TICKETS)

    top_probs = []

    for race_id, g in df.groupby("race_id"):
        pair_prob = {}
        for _, r in g.iterrows():
            parsed = parse_trifecta(r["買い目"])
            if parsed is None:
                continue
            a, b, _ = parsed
            p = float(r["p"])
            k = pair_key(a, b)
            pair_prob[k] = pair_prob.get(k, 0.0) + p

        ranked = sorted(pair_prob.items(), key=lambda x: x[1], reverse=True)
        if ranked:
            top_probs.append(ranked[0][1])

    s = pd.Series(top_probs)

    print("races:", len(s))
    print("mean:", s.mean())
    print("median:", s.median())
    print("max:", s.max())
    print("quantiles:")
    print(s.quantile([0.5, 0.75, 0.9, 0.95, 0.99]))

if __name__ == "__main__":
    main()