# src/scrape.py (出走表データ収集版)

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import datetime
from datetime import date, timedelta
from urllib.parse import urljoin
from tqdm import tqdm
import re
import sys

# --- 設定 ---
DATE_TO = date.today()
DATE_FROM = DATE_TO - timedelta(days=1)
SLEEP_TIME = 1
SAVE_PATH = 'data/raw/racecards_kdreams.csv' # 保存ファイル名を変更
BASE_URL = 'https://keirin.kdreams.jp'
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
}

def get_racecard_links_for_day(target_date: date) -> list:
    """
    /racecard/YYYY/MM/DD/ ページから、その日の全レースの「出走表」ページのURLを取得する
    """
    racecard_links = []
    url = urljoin(BASE_URL, f"/racecard/{target_date.strftime('%Y/%m/%d')}/")
    try:
        res = requests.get(url, headers=HEADERS)
        if res.status_code == 404:
            tqdm.write(f"INFO: No races on {target_date}. Skipping.")
            return []
        res.raise_for_status()
        
        soup = BeautifulSoup(res.content, 'html.parser')
        # HTMLを解析
        #soup = BeautifulSoup(res.content.decode("shift_jis", "ignore"),'html.parser')
        
        # === ★★★ 変更点 ★★★ ===
        # 「結果」ではなく、各レース（1R, 2R...）の「出走表」へのリンクを探す

        # 1. classが'JS_POST_THROW'である全ての<a>タグを見つける
        links = soup.find_all('a', class_='JS_POST_THROW')
        
        # 2. 抽出した各リンクからURL（href属性）を取り出してリストに保存する
        race_urls = []

        for link in links:
            # '一覧'のリンクを除外
            if "一覧" not in link.text:
                racecard_links.append(urljoin(BASE_URL, link['href']))

    except requests.exceptions.RequestException as e:
        print(f"Error fetching race card list for {target_date}: {e}")
    
    return list(set(racecard_links))


def scrape_racecard_page(racecard_url: str) -> list:
    """
    単一の出走表ページから全選手のデータを抽出する
    """
    race_data = []
    try:
        res = requests.get(racecard_url, headers=HEADERS)
        res.raise_for_status()
        # soup = BeautifulSoup(res.content.decode("shift_jis", "ignore"), 'html.parser')
        soup = BeautifulSoup(res.content, 'html.parser')

        # === ★★★ 変更点 ★★★ ===
        # URLの形式からrace_idを取得
        # 1. URLからrace_idをより安全に取得します (正規表現を使用)
        race_id_match = re.search(r'/(\d+)/?$', racecard_url)
        race_id = race_id_match.group(1) if race_id_match else "N/A"

        # 2. ページ内のテキストから日付を取得します (こちらの方が確実です)
        date_tag = soup.select_one('head > title')
        date_str_raw = date_tag.text if date_tag else "日付不明"
        date_match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', date_str_raw)
        race_date = f"{date_match.group(1)}{int(date_match.group(2)):02}{int(date_match.group(3)):02}" if date_match else "N/A"

        keirin_details = date_str_raw.replace('| ','').replace('【楽天Kドリームス】','').replace('<title>','').split(' ') # タイトルから詳細情報を抽出
        race_place = keirin_details[0] if len(keirin_details) > 0 else "不明" # 競輪場名
        race_name = keirin_details[2] if len(keirin_details) > 1 else "不明" # レース名
        race_num = keirin_details[3] if len(keirin_details) > 2 else "不明" # レース番号
        race_kubun = keirin_details[4] if len(keirin_details) > 3 else "不明" # レース区分
        race_date_wareki = keirin_details[5] if len(keirin_details) > 4 else "不明" # 開催日（和暦）

        # 並び予想テーブルからライン配置を抽出

        
        line_position = soup.find("div", attrs={"class":"line_position"}).text
        # テーブルが見つからなかった場合は、ライン配置にNAを代入します。
        if not line_position:
            line_config_str = "N/A" # ライン配置が見つからない場合は"N/A"を設定
            print(f"Warning: 'racecard_table' not found on {racecard_url}")
        
        # ライン配置のテキストを処理
        else:
            p = re.sub(r"[\n先行追込追上自在イン待押え先カマシ]","P",line_position).replace('PPP','').replace('P','mmmmmm').replace('mmmmmm←','')
            line_config = [a.strip() for a in p.split('mmmmmm') if a.strip()]
            line_config_len = []
            for a in line_config:
                line_config_len.append(len(str(a)))        
                line_config_str = ''.join(str(line_config_len)).replace(', ','-') # ライン配置の長さをハイフン区切りで連結

        # 出走表のテーブルからデータを抽出
        table = soup.find("table", class_="racecard_table")

        # テーブルが見つからなかった場合は、何もせずに関数を終了します。
        if not table:
            print(f"Warning: 'racecard_table' not found on {racecard_url}")
            return []
        
        # テーブル本体(tbody)の行(tr)をすべて取得します。
        all_rows = table.select('tr')

        # 最初の1行（ヘッダー）を除いた、データ部分の行だけをスライスで取得します
        result_rows = all_rows[2:]

        for row in result_rows:
            cols = row.find_all('td') # 表のヘッダーは除く

            if len(cols) < 23: continue # 出走表の列数に合わせて調整
            
            # 1. 正規表現パターンを作成する
            # 'icon icon_t'で始まり、その後に1桁の数字が続くクラス名を意味する
            yosou_tag = row.find('span', class_=re.compile(r'icon icon_t\d'))
            yosou = yosou_tag.text if yosou_tag else "" # タグがあればテキストを、なければ空文字を設定

            # 予想マークがない場合は、インデックスを調整
            # 予想マークがない場合は、インデックスを0に設定
            if yosou is None:
                i = 1
            # 予想マークがある場合は、インデックスを1に設定
            elif yosou:
                i = 0

            # 選手名とその他の情報を分割
            # cols[5] には選手名と都道府県、年齢、期別が含まれている
            # 例: "選手名 / 都道府県 / 年齢 / 期別"
            # cols[5] のテキストをスラッシュで分割して、
            player_details = cols[i+5].text.replace('\t',"").replace('\n','/').replace('\u3000','').strip().split('/') # 選手名をスラッシュで分割

            # koukiai = cols.find_all("td", class_="kiai") if koukiai else "N/A" # 好気合 # 不具合のため一旦コメントアウト
            # souhyou = cols.find_all("td", class_="evaluation bdr_r") if souhyou else "N/A" # 総評 # 不具合のため一旦コメントアウト　

            # 抽出するデータを変更
            race_data.append({
                'race_id': race_id,
                'race_date': race_date,
                'race_place': race_place,
                'race_name': race_name,
                'race_num' : race_num,
                'race_kubun': race_kubun,
                'yosou': yosou, # 予想マーク
                # 'koukiai': koukiai, # 好気合
                # 'souhyou': souhyou, # 総評
                'frame_number': cols[i+2].text.strip(), # 枠番
                'car_number': cols[i+3].text.strip(), # 車番
                'player_name': player_details[1], # 選手名
                'prefectures': player_details[2], # 都道府県
                'age_class': player_details[3], # 年齢
                'piriod': player_details[4], # 期別
                'classgroup': cols[i+6].text.strip(), # 級班
                'leg_type': cols[i+7].text.strip(),   # 脚質
                'gear_ratio': cols[i+8].text.strip(), # ギヤ倍数
                'race_points': cols[i+9].text.strip(),# 競走得点
                'start': cols[i+10].text.strip(), # S回数
                'back': cols[i+11].text.strip(), # B回数
                'nige': cols[i+12].text.strip(), # 逃回数
                'makuri': cols[i+13].text.strip(), # 捲回数
                'sasi': cols[i+14].text.strip(), # 差回数
                'mark': cols[i+15].text.strip(), # マーク回数
                '1st': cols[i+16].text.strip(), # 1st回数
                '2nd': cols[i+17].text.strip(), # 2nd回数
                '3rd': cols[i+18].text.strip(), # 3rd回数
                'tyakugai': cols[i+19].text.strip(), # 着外回数
                'winrate': cols[i+20].text.strip(), # 勝率
                '2rentairitu': cols[i+21].text.strip(), # 2連対率
                '3rentairitu': cols[i+22].text.strip() # 3連対率
            })
            
    except Exception as e:
        print(f"\nAn unexpected error occurred on {racecard_url}: {e}")

    return race_data

if __name__ == '__main__':
    all_entrants = []
    target_dates = [DATE_FROM + timedelta(days=i) for i in range((DATE_TO - DATE_FROM).days + 1)]

    # 1. まず、過去1年間の全レースの出走表ページのURLをすべて集める
    all_racecard_urls = []
    for day in tqdm(target_dates, desc="Phase 1: Finding all racecard URLs"):
        racecard_links = get_racecard_links_for_day(day)
        all_racecard_urls.extend(racecard_links)
        time.sleep(SLEEP_TIME)
    
    all_racecard_urls = sorted(list(set(all_racecard_urls)))
    print(f"Found {len(all_racecard_urls)} total racecards to scrape.")

    # 2. 集めたURLの出走表を一つずつ取得する
    if all_racecard_urls:
        for url in tqdm(all_racecard_urls, desc="Phase 2: Scraping Racecards"):
            result = scrape_racecard_page(url)
            all_entrants.extend(result)
            time.sleep(SLEEP_TIME)

        df = pd.DataFrame(all_entrants)
        df.to_csv(SAVE_PATH, index=False, encoding='shift_jis')
        print(f"\nScraping finished. Saved {len(df)} rows to {SAVE_PATH}")
    else:
        print("\nNo data was scraped.")