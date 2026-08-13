import numpy as np
import pandas as pd

INPUT = "data/merged/ev_tickets_2shahuku_all.csv"
OUT_DETAIL = "data/merged/odds_distortion_2shahuku_all.csv"
OUT_RACE = "data/merged/odds_distortion_race_summary_2shahuku.csv"

ODDS_SENTINEL = 9999.0
EPS = 1e-12


def safe_zscore(s: pd.Series) -> pd.Series:
    std = s.std(ddof=0)
    if std == 0 or pd.isna(std):
        return pd.Series(np.zeros(len(s)), index=s.index)
    return (s - s.mean()) / std


def main():
    df = pd.read_csv(INPUT).copy()

    # 型変換
    df["odds"] = pd.to_numeric(df["odds"], errors="coerce")
    df["p"] = pd.to_numeric(df["p"], errors="coerce")
    df["EV"] = pd.to_numeric(df["EV"], errors="coerce")

    # 番兵・欠損除外
    df = df.dropna(subset=["race_id", "買い目", "odds", "p"])
    df = df[(df["odds"] > 1) & (df["odds"] < ODDS_SENTINEL)]
    df = df[(df["p"] > 0) & (df["p"] < 1)]

    # 市場の生確率
    df["market_raw"] = 1.0 / df["odds"]

    # レース内で正規化した市場確率
    race_sum = df.groupby("race_id")["market_raw"].transform("sum")
    df["market_prob"] = df["market_raw"] / race_sum

    # 控除率っぽい指標（参考）
    # 市場生確率の総和。1より大きいほど控除率が乗っているイメージ
    df["market_overround"] = race_sum

    # 歪み指標
    df["distortion_ratio"] = df["p"] / (df["market_prob"] + EPS)
    df["distortion_log"] = np.log((df["p"] + EPS) / (df["market_prob"] + EPS))

    # レース内順位
    df["model_rank"] = df.groupby("race_id")["p"].rank(ascending=False, method="min")
    df["market_rank"] = df.groupby("race_id")["market_prob"].rank(ascending=False, method="min")
    df["ev_rank"] = df.groupby("race_id")["EV"].rank(ascending=False, method="min")

    # 順位差
    # + ならモデル順位の方が高い（市場より買いたい）
    df["rank_gap"] = df["market_rank"] - df["model_rank"]

    # レース内 z-score
    df["distortion_z"] = df.groupby("race_id")["distortion_log"].transform(safe_zscore)
    df["ev_z"] = df.groupby("race_id")["EV"].transform(safe_zscore)

    # 実戦向けスコア
    # 歪み × 確率 × EV を軽く混ぜる
    df["distortion_score"] = (
        df["distortion_z"] * 0.5
        + df["ev_z"] * 0.3
        + np.log(df["p"] + EPS) * 0.2
    )

    # 出力1: 全買い目詳細
    df = df.sort_values(["race_id", "distortion_score"], ascending=[True, False]).reset_index(drop=True)
    df.to_csv(OUT_DETAIL, index=False, encoding="utf-8-sig")

    # 出力2: レース単位サマリ
    idx = df.groupby("race_id")["distortion_score"].idxmax()
    race = df.loc[idx, [
        "race_id", "競輪場", "レース番号", "開始時間",
        "買い目", "odds", "p", "EV",
        "market_prob", "distortion_ratio", "distortion_log",
        "distortion_z", "rank_gap", "distortion_score"
    ]].copy()

    race = race.rename(columns={
        "買い目": "best_bet_distortion",
        "odds": "best_odds_distortion",
        "p": "best_p_distortion",
        "EV": "best_EV_distortion",
    })

    race = race.sort_values("distortion_score", ascending=False).reset_index(drop=True)
    race.to_csv(OUT_RACE, index=False, encoding="utf-8-sig")

    print("[OK]", OUT_DETAIL)
    print("[OK]", OUT_RACE)
    print("\n=== detail columns ===")
    print(df.columns.tolist())
    print("\n=== top race summary ===")
    print(race.head(20).to_string(index=False))


if __name__ == "__main__":
    main()