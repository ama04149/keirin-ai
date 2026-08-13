import pandas as pd
import numpy as np

# 入力（merged）
TICKETS = "data/merged/ev_tickets_all.csv"
RESULTS = "data/merged/results_sanrentan_all.csv"

INITIAL_BANKROLL = 100_000
BET_UNIT = 100
KELLY_MULTIPLIER = 0.5
TICKET_CAP = 0.005
MIN_BET = 100

def kelly_fraction(p: float, odds: float) -> float:
    if pd.isna(p) or pd.isna(odds) or odds <= 1 or p <= 0:
        return 0.0
    b = odds - 1.0
    f = (b * p - (1.0 - p)) / b
    return max(0.0, float(f))

def round_down(x: float, unit: int) -> int:
    if x <= 0:
        return 0
    return int(x // unit) * unit

def simulate(df_all: pd.DataFrame, top_n: int, p_min: float, ev_min: float, race_cap: float):
    # フィルタ
    df = df_all[(df_all["p"] >= p_min) & (df_all["EV"] >= ev_min)].copy()
    if df.empty:
        return None

    # EV上位N点
    df = df.sort_values(["race_id", "EV"], ascending=[True, False])
    df["rank_in_race"] = df.groupby("race_id").cumcount() + 1
    df = df[df["rank_in_race"] <= top_n].copy()
    if df.empty:
        return None

    bankroll = INITIAL_BANKROLL
    max_bankroll = INITIAL_BANKROLL

    stake_total = 0
    payout_total = 0
    hit_races = 0
    settled_races = 0
    max_losing_streak = 0
    cur_ls = 0
    max_dd = 0.0

    for race_id, g in df.groupby("race_id", sort=True):
        # 結果がないレースは除外（念のため）
        if g["sanrentan_result"].isna().all():
            continue

        settled_races += 1
        result = str(g["sanrentan_result"].iloc[0])
        payout100 = int(g["payout_sanrentan_100"].iloc[0])

        # 点ごとのstake
        stakes = []
        for _, row in g.iterrows():
            p = float(row["p"])
            odds = float(row["odds"])
            f = min(kelly_fraction(p, odds) * KELLY_MULTIPLIER, TICKET_CAP)
            stake = round_down(bankroll * f, BET_UNIT)
            if 0 < stake < MIN_BET:
                stake = MIN_BET
            stakes.append(stake)

        g = g.copy()
        g["stake"] = stakes

        # レース上限
        race_cap_yen = round_down(bankroll * race_cap, BET_UNIT)
        ssum = int(g["stake"].sum())
        if race_cap_yen > 0 and ssum > race_cap_yen:
            scale = race_cap_yen / ssum
            g["stake"] = (g["stake"] * scale).apply(lambda x: round_down(x, BET_UNIT))
            ssum = int(g["stake"].sum())

        if ssum <= 0:
            # 買わないレースとして扱う
            cur_ls += 1
            max_losing_streak = max(max_losing_streak, cur_ls)
            continue

        stake_total += ssum

        # 精算
        hit_any = False
        payout_race = 0
        for _, row in g.iterrows():
            bet = str(row["買い目"])
            stake = int(row["stake"])
            if stake <= 0:
                continue
            if bet == result:
                hit_any = True
                payout_race += payout100 * (stake // 100)

        payout_total += payout_race
        bankroll += (payout_race - ssum)

        max_bankroll = max(max_bankroll, bankroll)
        dd = (max_bankroll - bankroll) / max_bankroll if max_bankroll else 0.0
        max_dd = max(max_dd, dd)

        if hit_any:
            hit_races += 1
            cur_ls = 0
        else:
            cur_ls += 1
            max_losing_streak = max(max_losing_streak, cur_ls)

    roi = (payout_total / stake_total) if stake_total > 0 else 0.0
    hit_rate = (hit_races / settled_races) if settled_races > 0 else 0.0

    return {
        "TOP_N": top_n,
        "P_MIN": p_min,
        "EV_MIN": ev_min,
        "RACE_CAP": race_cap,
        "races": settled_races,
        "hit_races": hit_races,
        "hit_rate": hit_rate,
        "stake": stake_total,
        "payout": payout_total,
        "ROI": roi,
        "max_DD": max_dd,
        "final_bankroll": bankroll,
        "max_losing_streak": max_losing_streak,
    }

def main():
    df_t = pd.read_csv(TICKETS)
    df_r = pd.read_csv(RESULTS)
    df = df_t.merge(df_r, on="race_id", how="inner")

    required = ["race_id","買い目","odds","p","EV","sanrentan_result","payout_sanrentan_100"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}. columns={list(df.columns)}")

    # 探索範囲（まずは現実的な範囲）
    TOP_NS = [1, 3, 5]
    P_MINS = [0.0, 0.002, 0.003, 0.004]
    EV_MINS = [0.0, 1.0, 2.0, 5.0]
    RACE_CAPS = [0.003, 0.005, 0.01]

    rows = []
    for top_n in TOP_NS:
        for p_min in P_MINS:
            for ev_min in EV_MINS:
                for race_cap in RACE_CAPS:
                    res = simulate(df, top_n, p_min, ev_min, race_cap)
                    if res:
                        rows.append(res)

    out = pd.DataFrame(rows)
    if out.empty:
        print("No valid results. Try loosening filters.")
        return

    # “勝ってる”順にソート（ROI優先、DDも見る）
    out = out.sort_values(["ROI", "max_DD"], ascending=[False, True])

    out.to_csv("data/merged/grid_search_results.csv", index=False)
    print("Saved: data/merged/grid_search_results.csv")

    # 上位10件表示
    cols = ["TOP_N","P_MIN","EV_MIN","RACE_CAP","races","hit_races","hit_rate","stake","payout","ROI","max_DD","final_bankroll","max_losing_streak"]
    print("\nTop 10:")
    print(out[cols].head(10).to_string(index=False))

if __name__ == "__main__":
    main()