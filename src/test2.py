import re
import requests
import pandas as pd
from bs4 import BeautifulSoup

def fetch_sanrentan_odds_from_odds_grid(url: str) -> pd.DataFrame:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    }
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    rows = []
    # 3連単ブロック：table class="odds_table bt5 ..."
    tables = soup.select("table.odds_table.bt5")
    if not tables:
        raise RuntimeError("odds_table(bt5) が見つかりません。URLが3連単の /odds/ ページか確認してください。")

    for tbl in tables:
        # --- 1着(first)の特定 ---
        # 最初の<tr>に th.n1..n9 が並んでいて、表示されている(th styleなし)のがそのテーブルの1着
        first = None
        first_header_tr = tbl.find("tr")
        if not first_header_tr:
            continue

        for th in first_header_tr.find_all("th"):
            cls = th.get("class", [])
            # classに n1/n2... が付く
            m = next((re.match(r"n(\d+)", c) for c in cls if re.match(r"n(\d+)", c)), None)
            if not m:
                continue
            num = int(m.group(1))
            style = (th.get("style") or "").replace(" ", "")
            # display:none じゃないものが表示対象
            if "display:none" not in style.lower():
                first = num
                break

        if first is None:
            # たまにstyleが空でも全部none…みたいなケースはほぼ無いが念のため
            continue

        # --- 列見出し（third候補）の特定 ---
        # 2行目に <th class="n2">2</th> <th class="n3">3</th> ... が並んでいる行がある
        # （rowspan="2"の空白thが混じるので nX だけ拾う）
        header_row = None
        tr_list = tbl.find_all("tr")
        for tr in tr_list:
            ths = tr.find_all("th")
            if not ths:
                continue
            nums = []
            for th in ths:
                cls = th.get("class", [])
                m = next((re.match(r"n(\d+)", c) for c in cls if re.match(r"n(\d+)", c)), None)
                if m and th.get_text(strip=True).isdigit():
                    nums.append(int(m.group(1)))
            # third候補が3つ以上並んでる行をヘッダ扱い
            if len(nums) >= 3:
                header_row = nums
                break

        if not header_row:
            continue

        third_candidates_all = header_row[:]  # 例: [2,3,4,5,6,7]
        # --- データ行の処理 ---
        # 形式： <tr><th class="n2">2</th><td class="empty"></td><td>639.9</td>...<th class="n2">2</th></tr>
        for tr in tr_list:
            ths = tr.find_all("th")
            if len(ths) < 2:
                continue
            # 行頭thが second
            second_txt = ths[0].get_text(strip=True)
            if not second_txt.isdigit():
                continue
            second = int(second_txt)

            # second行のtdを拾う
            tds = tr.find_all("td")
            if not tds:
                continue

            # third候補は「ヘッダ全体」から second を除いた順
            third_candidates = [x for x in third_candidates_all if x != second]

            # tdのうち empty を除いたものが odds の並び
            odds_cells = []
            for td in tds:
                if "empty" in (td.get("class") or []):
                    continue
                val = td.get_text(strip=True)
                val = val.replace(",", "")
                if re.fullmatch(r"\d+(?:\.\d+)?", val):
                    odds_cells.append(float(val))

            if len(odds_cells) != len(third_candidates):
                # 想定と違う時はスキップ（安全側）
                continue

            for third, odd in zip(third_candidates, odds_cells):
                # 3連単 first-second-third
                rows.append((first, second, third, odd))

    df = pd.DataFrame(rows, columns=["first", "second", "third", "odds"])
    if df.empty:
        raise RuntimeError("オッズが1件も取れませんでした。HTML構造が想定と違う可能性があります。")
    return df

# 使い方
# ※ #detail はHTTP的には無意味（フロントのスクロール用）なので外してOK
url = "https://keirin.kdreams.jp/gamboo/keirin-kaisai/race-card/odds/7320260129/73202601290400/2/3rentan/"
df_grid = fetch_sanrentan_odds_from_odds_grid(url)
print(df_grid.head(20))
print("件数:", len(df_grid))
