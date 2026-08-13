# src/ev_ranker_2shahuku.py
import re
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from tqdm import tqdm


BASE = "https://keirin.kdreams.jp/gamboo/keirin-kaisai/race-card/odds"


def build_odds_url(race_id: str, bet_type: str) -> str:
    """
    /odds/{race_id_1}/{kaisai_id}00/{race_no}/{bet_type}/#detail
    bet_type例:
      - 3rentan
      - 2shahuku  (2車複)
    """
    race_id_1 = race_id[:10]
    kaisai_id = race_id[:12]
    race_no = int(race_id[-2:])
    return f"{BASE}/{race_id_1}/{kaisai_id}00/{race_no}/{bet_type}/#detail"


def _text_to_float(s: str):
    s = s.strip()
    if not s:
        return None
    s = s.replace(",", "")
    try:
        return float(s)
    except:
        return None


def fetch_2shahuku_odds(
    race_id: str,
    session: requests.Session,
    timeout=20,
    sleep_sec=0.2
) -> pd.DataFrame:
    """
    2車複オッズを DataFrame にして返す
    columns: a, b, odds （a<bに正規化）
    """
    url = build_odds_url(race_id, bet_type="2shahuku")
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
    }

    r = session.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    html = r.text

    if "odds_table" not in html:
        return pd.DataFrame(columns=["a", "b", "odds"])

    soup = BeautifulSoup(html, "html.parser")
    tb = soup.select_one("table.odds_table")
    if tb is None:
        return pd.DataFrame(columns=["a", "b", "odds"])

    trs = tb.find_all("tr")
    if len(trs) < 3:
        return pd.DataFrame(columns=["a", "b", "odds"])

    # 1行目：列ヘッダ（th.n1..n7）
    col_nums = []
    for th in trs[0].find_all("th"):
        cls = " ".join(th.get("class") or [])
        m = re.search(r"n(\d+)", cls)
        if m:
            col_nums.append(int(m.group(1)))

    if not col_nums:
        for th in trs[0].find_all("th"):
            t = th.get_text(strip=True)
            if t.isdigit():
                col_nums.append(int(t))

    if not col_nums:
        return pd.DataFrame(columns=["a", "b", "odds"])

    rows = []

    # trs[1] は選手名行。trs[2:] がオッズ行列
    for tr in trs[2:]:
        th = tr.find("th")
        if not th:
            continue

        cls = " ".join(th.get("class") or [])
        m = re.search(r"n(\d+)", cls)
        if m:
            row_num = int(m.group(1))
        else:
            t = th.get_text(strip=True)
            if not t.isdigit():
                continue
            row_num = int(t)

        tds = tr.find_all("td")
        if not tds:
            continue

        for j, td in enumerate(tds):
            if j >= len(col_nums):
                break
            col_num = col_nums[j]

            td_cls = " ".join(td.get("class") or [])
            if "empty" in td_cls:
                continue

            odds = _text_to_float(td.get_text(" ", strip=True))
            if odds is None:
                continue

            a, b = sorted([row_num, col_num])
            if a == b:
                continue
            rows.append((a, b, odds))

    df = pd.DataFrame(rows, columns=["a", "b", "odds"])
    df = df.drop_duplicates(subset=["a", "b"]).reset_index(drop=True)

    time.sleep(sleep_sec)
    return df


def pl_prob_2shahuku(a: int, b: int, win_scores: dict, top3_scores: dict) -> float:
    """
    二車複（順不同）PL風近似:
      P({a,b}) = P(a1着)*P(b2着|a) + P(b1着)*P(a2着|b)
    """
    if a not in win_scores or b not in win_scores or a not in top3_scores or b not in top3_scores:
        return 0.0

    denom1 = sum(max(win_scores[k], 1e-9) for k in win_scores)
    if denom1 <= 0:
        return 0.0

    def p1(x):
        return max(win_scores[x], 1e-9) / denom1

    def p2(y, first):
        remaining = [k for k in top3_scores.keys() if k != first]
        denom2 = sum(max(top3_scores[k], 1e-9) for k in remaining)
        if denom2 <= 0 or y not in remaining:
            return 0.0
        return max(top3_scores.get(y, 0), 1e-9) / denom2

    return p1(a) * p2(b, a) + p1(b) * p2(a, b)


def main():
    # 入力（既存と同じ）
    PRED_CSV = "keirin_prediction_result_combined.csv"
    RACE_INFO_PKL = "today_race_info2.pkl"

    # 出力（別ファイルで並行運用）
    OUT_TICKETS = "keirin_ev_tickets_2shahuku.csv"
    OUT_RACES = "keirin_ev_race_rank_2shahuku.csv"

    df_pred = pd.read_csv(PRED_CSV, encoding="utf-8-sig", dtype={"race_id_kdreams": "string"})
    race_info = pd.read_pickle(RACE_INFO_PKL).copy()

    if "race_id" not in race_info.columns:
        raise RuntimeError("today_race_info2.pkl に race_id 列がありません。")

    if "race_id" not in df_pred.columns:
        key_cols = ["競輪場", "レース番号", "開始時間"]
        m = race_info.reset_index().rename(columns={"index": "race_key"})[key_cols + ["race_id"]]
        df_pred = df_pred.merge(m, on=key_cols, how="left")
        if df_pred["race_id"].isna().any():
            missing = df_pred[df_pred["race_id"].isna()][key_cols].drop_duplicates().head(10)
            raise RuntimeError(f"予測CSVに race_id が付与できませんでした:\n{missing}")

    race_ids = race_info["race_id"].astype(str).unique().tolist()
    session = requests.Session()

    ticket_rows = []

    for rid in tqdm(race_ids, desc="odds+EV(2shahuku)"):
        g = df_pred[df_pred["race_id"].astype(str) == str(rid)].copy()
        if len(g) < 2:
            continue

        g["車_番"] = g["車_番"].astype(int)

        win_scores = dict(zip(g["車_番"], g["prediction_score_1st"].astype(float)))
        top3_scores = dict(zip(g["車_番"], g["prediction_score_top3"].astype(float)))

        try:
            df_odds = fetch_2shahuku_odds(str(rid), session=session)
        except Exception:
            continue

        if df_odds.empty:
            continue

        one = g.iloc[0]
        place = one.get("競輪場", "")
        raceno = one.get("レース番号", "")
        st = one.get("開始時間", "")

        for _, r in df_odds.iterrows():
            a = int(r["a"]); b = int(r["b"])
            odds = float(r["odds"])
            if odds >= 9999:
                continue

            p = pl_prob_2shahuku(a, b, win_scores, top3_scores)
            ev = p * odds - 1.0

            ticket_rows.append({
                "race_id": str(rid),
                "競輪場": place,
                "レース番号": raceno,
                "開始時間": st,
                "買い目": f"{a}-{b}",
                "a": a, "b": b,
                "odds": odds,
                "p": p,
                "EV": ev,
            })

    df_tickets = pd.DataFrame(ticket_rows)
    if df_tickets.empty:
        raise RuntimeError("EV計算結果が0件でした（2車複オッズ取得に失敗の可能性）")

    df_tickets = df_tickets.sort_values(["EV"], ascending=False).reset_index(drop=True)
    df_tickets.to_csv(OUT_TICKETS, encoding="utf-8-sig", index=False)

    idx = df_tickets.groupby("race_id")["EV"].idxmax()
    df_race = df_tickets.loc[idx].sort_values("EV", ascending=False)
    df_race = df_race.rename(columns={"買い目": "best_bet", "EV": "max_EV", "p": "best_p", "odds": "best_odds"})
    df_race = df_race.sort_values("max_EV", ascending=False).reset_index(drop=True)
    df_race.to_csv(OUT_RACES, encoding="utf-8-sig", index=False)

    print(f"[OK] チケットEV一覧: {OUT_TICKETS}")
    print(f"[OK] レースEVランキング: {OUT_RACES}")
    print(df_race.head(20))


if __name__ == "__main__":
    main()