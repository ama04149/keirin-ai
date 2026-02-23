import re
import time
import math
import requests
import pandas as pd
from bs4 import BeautifulSoup
from tqdm import tqdm
import numpy as np


BASE = "https://keirin.kdreams.jp/gamboo/keirin-kaisai/race-card/odds"


def build_odds_url(race_id: str) -> str:
    """
    race_id例: 73202601290401
      - race_id_1: 7320260129 (10桁)
      - kaisai_id: 732026012904 (12桁)
      - race_no: 1..12 (末尾2桁)
    既知URL形式:
      /odds/{race_id_1}/{kaisai_id}00/{race_no}/3rentan/#detail
    """
    race_id_1 = race_id[:10]
    kaisai_id = race_id[:12]
    race_no = int(race_id[-2:])  # "01" -> 1
    return f"{BASE}/{race_id_1}/{kaisai_id}00/{race_no}/3rentan/#detail"


def _text_to_float(s: str):
    s = s.strip()
    if not s:
        return None
    s = s.replace(",", "")
    try:
        return float(s)
    except:
        return None


def fetch_sanrentan_odds(race_id: str, session: requests.Session, timeout=20, sleep_sec=0.2) -> pd.DataFrame:
    """
    3連単オッズ（全通り）を DataFrame にして返す
    columns: first, second, third, odds
    """
    url = build_odds_url(race_id)
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
    }

    r = session.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    html = r.text

    # ページに odds_table が無い場合は空を返す
    if "odds_table" not in html:
        return pd.DataFrame(columns=["first", "second", "third", "odds"])

    soup = BeautifulSoup(html, "html.parser")
    tables = soup.select("table.odds_table")
    rows = []

    for tb in tables:
        trs = tb.find_all("tr")
        if len(trs) < 4:
            continue

        # first：display:none でない th の span.number
        first_num = None
        for th in trs[0].find_all("th"):
            style = (th.get("style") or "").replace(" ", "").lower()
            if "display:none" in style:
                continue
            sp = th.select_one("span.number")
            if sp and sp.get_text(strip=True).isdigit():
                first_num = int(sp.get_text(strip=True))
                break
        if first_num is None:
            continue

        # third_nums：2行目の th（rowspanなし）から列番号
        third_nums = []
        for th in trs[1].find_all("th"):
            if th.get("rowspan"):
                continue
            cls = " ".join(th.get("class") or [])
            m = re.search(r"n(\d+)", cls)
            if m:
                third_nums.append(int(m.group(1)))

        if not third_nums:
            continue

        # データ行
        for tr in trs[3:]:
            th = tr.find("th")
            if not th:
                continue
            cls = " ".join(th.get("class") or [])
            m = re.search(r"n(\d+)", cls)
            if not m:
                continue
            #second_num = int(m.group(1))
            third_num = int(m.group(1))

            tds = tr.find_all("td")
            if not tds:
                continue

            for k, td in enumerate(tds):
                if k >= len(third_nums):
                    break
                #third_num = third_nums[k]
                second_num = third_nums[k]

                # emptyセルはスキップ（ただし列位置は進む）
                td_cls = " ".join(td.get("class") or [])
                if "empty" in td_cls:
                    continue

                odds = _text_to_float(td.get_text(" ", strip=True))
                if odds is None:
                    continue

                rows.append((first_num, second_num, third_num, odds))

    df = pd.DataFrame(rows, columns=["first", "second", "third", "odds"])
    # 念のため重複除去
    df = df.drop_duplicates(subset=["first", "second", "third"]).reset_index(drop=True)

    time.sleep(sleep_sec)
    return df


def pl_prob_triplet(order_triplet: tuple[int, int, int], win_scores: dict, top3_scores: dict) -> float:
    """
    逐次選択（Plackett-Luce風）で 3連単の確率を近似:
      P(a-b-c) = P1(a)*P2(b|a)*P3(c|a,b)
    """
    a, b, c = order_triplet

    # 候補が欠けている場合は0
    if a not in win_scores or b not in top3_scores or c not in top3_scores:
        return 0.0

    # 1着：win_scores 正規化
    denom1 = sum(max(win_scores[k], 1e-9) for k in win_scores)
    p1 = max(win_scores[a], 1e-9) / denom1 if denom1 > 0 else 0.0

    # 2着：残りから top3_scores 正規化
    remaining2 = [k for k in top3_scores.keys() if k != a]
    denom2 = sum(max(top3_scores[k], 1e-9) for k in remaining2)
    p2 = max(top3_scores.get(b, 0), 1e-9) / denom2 if (denom2 > 0 and b in remaining2) else 0.0

    # 3着：残りから top3_scores 正規化
    remaining3 = [k for k in top3_scores.keys() if (k != a and k != b)]
    denom3 = sum(max(top3_scores[k], 1e-9) for k in remaining3)
    p3 = max(top3_scores.get(c, 0), 1e-9) / denom3 if (denom3 > 0 and c in remaining3) else 0.0

    return p1 * p2 * p3


def main():
    # 入力
    PRED_CSV = "keirin_prediction_result_combined.csv"
    RACE_INFO_PKL = "today_race_info2.pkl"   # ここに race_id が入っている想定（today_race_id_scrapeで付与）
    OUT_TICKETS = "keirin_ev_tickets.csv"
    OUT_RACES = "keirin_ev_race_rank.csv"

    df_pred = pd.read_csv(
        PRED_CSV,
        encoding="utf-8-sig",
        dtype={"race_id_kdreams": "string"}
    )
    race_info = pd.read_pickle(RACE_INFO_PKL).copy()

    if "race_id" not in race_info.columns:
        raise RuntimeError("today_race_info2.pkl に race_id 列がありません。today_race_id_scrape.pyで race_info に race_id を付けてください。")

    # df_pred 側に race_id が無いなら、競輪場・レース番号・開催日・開始時間…等から結合する必要が出ますが、
    # まずは df_pred に race_id を足す方が堅い（t_race.pyの new_data に race_info を mergeする段階で race_id を持たせるのが最善）
    if "race_id" not in df_pred.columns:
        # 最低限の救済：競輪場×レース番号×開始時間で結合（同名衝突があると危険）
        # 可能なら t_race.py 側で race_id を出力して下さい（強く推奨）
        key_cols = ["競輪場", "レース番号", "開始時間"]
        m = race_info.reset_index().rename(columns={"index": "race_key"})[key_cols + ["race_id"]]
        df_pred = df_pred.merge(m, on=key_cols, how="left")
        if df_pred["race_id"].isna().any():
            missing = df_pred[df_pred["race_id"].isna()][key_cols].drop_duplicates().head(10)
            raise RuntimeError(
                "予測CSVに race_id が付与できませんでした。"
                "t_race.pyの時点で race_id を列として出力する構成にしてください。"
                f"（例: マッチできないキー例）\n{missing}"
            )

    # レース一覧
    race_ids = race_info["race_id"].astype(str).unique().tolist()

    session = requests.Session()

    ticket_rows = []

    for rid in tqdm(race_ids, desc="odds+EV"):
        # レースの予測データ
        g = df_pred[df_pred["race_id"].astype(str) == str(rid)].copy()

        # 欠場等で選手が少ないレースは除外
        if len(g) < 3:
            continue

        # 車番をintに
        g["車_番"] = g["車_番"].astype(int)

        # win/top3 スコア辞書
        win_scores = dict(zip(g["車_番"], g["prediction_score_1st"].astype(float)))
        top3_scores = dict(zip(g["車_番"], g["prediction_score_top3"].astype(float)))

        # オッズ取得
        try:
            df_odds = fetch_sanrentan_odds(str(rid), session=session)
        except Exception:
            continue

        if df_odds.empty:
            continue

        # 表示用情報
        one = g.iloc[0]
        place = one.get("競輪場", "")
        raceno = one.get("レース番号", "")
        st = one.get("開始時間", "")

        # EV計算（全買い目）
        for _, r in df_odds.iterrows():
            a = int(r["first"]); b = int(r["second"]); c = int(r["third"])
            odds = float(r["odds"])

            p = pl_prob_triplet((a, b, c), win_scores, top3_scores)
            ev = p * odds - 1.0  # 1単位賭けの期待値

            ticket_rows.append({
                "race_id": str(rid),
                "競輪場": place,
                "レース番号": raceno,
                "開始時間": st,
                "買い目": f"{a}-{b}-{c}",
                "first": a,
                "second": b,
                "third": c,
                "odds": odds,
                "p": p,
                "EV": ev,
            })

    df_tickets = pd.DataFrame(ticket_rows)
    if df_tickets.empty:
        raise RuntimeError("EV計算結果が0件でした（オッズ取得/結合に失敗している可能性）")

    # チケット単位：EV順
    df_tickets = df_tickets.sort_values(["EV"], ascending=False).reset_index(drop=True)
    print("df_tickets columns:", df_tickets.columns.tolist())
    df_tickets.to_csv(OUT_TICKETS, encoding="utf-8-sig", index=False)

    # レース単位：各レースの最大EVを代表に
    idx = df_tickets.groupby("race_id")["EV"].idxmax()
    df_race = df_tickets.loc[idx].sort_values("EV", ascending=False)
    df_race = df_race.rename(columns={"買い目": "best_bet", "EV": "max_EV", "p": "best_p", "odds": "best_odds"})
    df_race = df_race.sort_values("max_EV", ascending=False).reset_index(drop=True)
    df_race.to_csv(OUT_RACES, encoding="utf-8-sig", index=False)

    print(f"[OK] チケットEV一覧: {OUT_TICKETS}")
    print(f"[OK] レースEVランキング: {OUT_RACES}")
    print(df_race.head(20))

    print(df_race[["race_id", "競輪場", "レース番号", "max_EV"]].head())

def add_kelly_for_best_bet(
    df_rank: pd.DataFrame,
    bankroll: int = 50_000,
    kelly_fraction: float = 0.5,          # 1/2 Kelly
    cap_fraction_per_bet: float = 0.005,  # 1点あたり資金の最大0.5%
    min_stake: int = 100,                 # 最低100円
    stake_unit: int = 100,                # 100円単位
    min_ev: float = 0.00,                 # ★純EVの下限（0.00=プラスのみ、0.10=+10%以上など）
    drop_odds_sentinel: float = 9999.9,   # 9999.9系を除外
    top_n: int = 20,                      # 上位Nだけ買う
    max_total_stake: int = 5000,          # 総賭け金上限
) -> pd.DataFrame:
    """
    df_rank には最低限これらの列がある想定：
      race_id, 競輪場, レース番号, 開始時間, best_bet, best_odds, best_p, max_EV
    max_EV は「純EV」(p*odds - 1) の想定。
    """

    df = df_rank.copy()

    # ---- 必須列チェック（事故る前に落とす）----
    required = ["race_id", "best_bet", "best_odds", "best_p", "max_EV"]
    miss = [c for c in required if c not in df.columns]
    if miss:
        raise KeyError(f"df_rank missing columns: {miss}")

    # ---- 型を揃える ----
    df["best_odds"] = pd.to_numeric(df["best_odds"], errors="coerce")
    df["best_p"] = pd.to_numeric(df["best_p"], errors="coerce")
    df["max_EV"] = pd.to_numeric(df["max_EV"], errors="coerce")

    # ---- 欠損除外 ----
    df = df.dropna(subset=["best_odds", "best_p", "max_EV"]).copy()

    # ---- オッズの番兵除外 ----
    # 9999.9 ぴったりだけ落とす（9999.0も落としたいなら条件を広げる）
    df = df[~np.isclose(df["best_odds"].astype(float), float(drop_odds_sentinel))].copy()

    # ---- 確率・オッズの妥当性 ----
    df = df[(df["best_p"] > 0) & (df["best_p"] < 1) & (df["best_odds"] > 1)].copy()

    # ---- ★純EVフィルタ（ここが超重要）----
    df = df[df["max_EV"] >= float(min_ev)].copy()

    # ここまでで0件なら終了（空を返す）
    if df.empty:
        df["kelly_full"] = []
        df["kelly_frac_capped"] = []
        df["stake_raw"] = []
        df["stake"] = []
        df["expected_profit"] = []
        return df

    # ---- Kelly（純オッズ b = odds-1）----
    # f* = (p*(b+1)-1)/b = (p*odds - 1)/(odds - 1) = max_EV / (odds-1)
    b = df["best_odds"] - 1.0
    df["kelly_full"] = df["max_EV"] / b

    # 負は買わない
    df["kelly_full"] = df["kelly_full"].clip(lower=0.0)

    # 1/2 Kelly + 1点cap
    df["kelly_frac_capped"] = (df["kelly_full"] * float(kelly_fraction)).clip(
        upper=float(cap_fraction_per_bet)
    )

    # ---- 賭け金（丸め前）----
    df["stake_raw"] = df["kelly_frac_capped"] * float(bankroll)

    # ---- 賭け金（100円単位に丸め）----
    # 最小賭け金未満は0に落とす（ここで stake=0 が大量に出るのは「設計どおり」）
    df["stake"] = (
        (df["stake_raw"] / float(stake_unit)).round() * float(stake_unit)
    ).astype(int)

    df.loc[df["stake"] < int(min_stake), "stake"] = 0

    # ---- 期待利益（純EV × 賭け金）----
    df["expected_profit"] = df["stake"] * df["max_EV"]

    # ---- stake>0 のみ残す ----
    df = df[df["stake"] > 0].copy()
    if df.empty:
        return df

    # ---- 期待利益の高い順に TOP_N ----
    df = df.sort_values("expected_profit", ascending=False).head(int(top_n)).reset_index(drop=True)

    # ---- 総賭け金上限でカット（上から順に積む）----
    cum = df["stake"].cumsum()
    df = df[cum <= int(max_total_stake)].copy()

    return df

if __name__ == "__main__":
    main()
    
    # ev_ranker.py の出力を読む
    df_rank = pd.read_csv("keirin_ev_race_rank.csv", encoding="utf-8-sig")

    df_kelly = add_kelly_for_best_bet(df_rank, bankroll=50000)
    
    df_kelly.to_csv("keirin_kelly_bets.csv", index=False, encoding="utf-8-sig")
    
    print("stake_raw describe:\n", df_kelly["stake_raw"].describe())
    print("stake value_counts:\n", df_kelly["stake"].value_counts().head(10))
    print("stake sum:", df_kelly["stake"].sum())
    print(df_kelly[["race_id","best_bet","best_odds","best_p","max_EV","kelly_full","kelly_frac_capped","stake_raw","stake","expected_profit"]].head(15))