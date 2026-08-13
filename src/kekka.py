import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
from itertools import permutations

def parse_numbers(value):
    """セルの値（ハイフン繋ぎやExcel保護用 ="1-2-3" 形式）から数字のみを抽出してリスト化"""
    if pd.isna(value):
        return []
    s = str(value).replace('="', '').replace('"', '')
    nums = re.findall(r'\d+', s)
    return nums

def parse_payoff(value):
    """配当金・オッズ文字列を堅牢にfloat変換する"""
    if pd.isna(value):
        return None
    s = re.sub(r'[^\d.]', '', str(value))
    try:
        val = float(s)
        return val if val > 0 else None
    except ValueError:
        return None

def extract_race_id(url_or_str):
    """URLや文字列から race_id (数字10〜16桁程度) を抽出"""
    if pd.isna(url_or_str):
        return ""
    s = str(url_or_str).split('.')[0] if '.' in str(url_or_str) and 'E' in str(url_or_str) else str(url_or_str)
    match = re.search(r'\d{10,16}', s)
    return match.group(0) if match else ""

def calculate_synthetic_odds(bet_list, odds_dict, fallback_hit_odds=None, num_bets=24):
    """
    買い目リストとオッズ辞書から合成オッズを計算。
    オッズ取得失敗時は確定配当金(fallback_hit_odds) / 点数 で補完。
    それでも計算できない場合は 0.00 を返す。
    """
    sum_inv_odds = 0.0
    valid_count = 0
    if odds_dict:
        for bet in bet_list:
            bet_key = tuple(str(x) for x in bet)
            odds = odds_dict.get(bet_key)
            if odds and odds > 0:
                sum_inv_odds += (1.0 / odds)
                valid_count += 1
                
    if valid_count > 0 and sum_inv_odds > 0:
        return round(1.0 / sum_inv_odds, 2)
    
    if fallback_hit_odds and fallback_hit_odds > 0 and len(bet_list) > 0:
        return round(fallback_hit_odds / len(bet_list), 2)
    
    return 0.00

def fetch_race_odds_dict(race_id):
    """
    指定された race_id の 3連単オッズ ページを取得し、
    {(車番1, 車番2, 車番3): オッズ(float)} の辞書形式で返す。
    """
    if not race_id or len(race_id) < 10:
        return {}
    
    urls = [
        f"https://keirin.kdreams.jp/racedetail/{race_id}/odds/",
        f"https://keirin.kdreams.jp/racedetail/{race_id}/odds/3rentan/"
    ]
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    odds_dict = {}

    for odds_url in urls:
        try:
            res = requests.get(odds_url, headers=headers, timeout=5)
            if res.status_code != 200:
                continue
            
            soup = BeautifulSoup(res.text, 'html.parser')
            elements = soup.find_all(['tr', 'li', 'div', 'td'])
            for elem in elements:
                text = elem.get_text(strip=True)
                match = re.search(r'(\d)\s*[\-ー－=]\s*(\d)\s*[\-ー－=]\s*(\d).*?(\d+\.\d+)', text)
                if match:
                    comb = (match.group(1), match.group(2), match.group(3))
                    try:
                        odds_val = float(match.group(4))
                        if comb not in odds_dict:
                            odds_dict[comb] = odds_val
                    except ValueError:
                        pass
            if odds_dict:
                break
        except Exception:
            continue

    return odds_dict

def reorder_columns_rates_to_end(df):
    """
    A率〜I率, CT値, スコア の列を末尾に移動させる
    """
    target_cols = ["A率", "B率", "C率", "D率", "E率", "F率", "G率", "H率", "I率", "CT値", "スコア"]
    
    # 存在する対象列を取り出す
    rates_in_df = [c for c in target_cols if c in df.columns]
    
    # 対象列以外を順番に並べる
    other_cols = [c for c in df.columns if c not in target_cols]
    
    # 最後に対象列を付加する
    new_order = other_cols + rates_in_df
    return df[new_order]

def fetch_and_update_keirin_data(csv_file, date_str):
    try:
        url_date = datetime.strptime(date_str, '%Y/%m/%d').strftime('%Y/%m/%d')
        url = f"https://keirin.kdreams.jp/harailist/{url_date}/"
    except ValueError:
        print("エラー: 日付の形式が無効です。'YYYY/MM/DD'形式で指定してください。")
        return

    try:
        print(f"URL: {url} から払戻金一覧を取得中...")
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        html_content = response.text
        print("払戻金一覧情報の取得に成功しました。")
    except requests.exceptions.RequestException as e:
        print(f"エラー: ウェブサイトへのアクセスに失敗しました。{e}")
        return

    # CSVファイルの読み込み
    try:
        df = pd.read_csv(csv_file, encoding='utf-8', dtype={'race_id': str})
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(csv_file, encoding='cp932', dtype={'race_id': str})
        except Exception as e:
            print(f"エラー: CSVファイルの読み込み中にエラーが発生しました: {e}")
            return
    except FileNotFoundError:
        print(f"エラー: '{csv_file}' が見つかりません。")
        return

    soup = BeautifulSoup(html_content, 'html.parser')
    extracted_data_by_id = {}
    extracted_data_by_key = {}

    daily_blocks = soup.find_all('div', class_='daily-refund-result-list')
    for block in daily_blocks:
        header = block.find('h3', class_='daily-refund-result-list_heading')
        if not header or '3連単' not in header.get_text():
            continue 
        
        velodrome_tags = block.find_all("span", class_="velodrome")
        if not velodrome_tags:
            continue

        for v in velodrome_tags:
            keirinjo_name = v.get_text(strip=True)
            if not keirinjo_name:
                continue

            table = v.find_next('table')
            if not table:
                continue

            for row in table.find_all('tr')[1:]:
                cells = row.find_all('td')
                if len(cells) < 4:
                    continue

                race_id = ""
                race_link = row.find('a', href=True)
                if race_link:
                    race_id = extract_race_id(race_link['href'])

                raw_race_num = cells[0].get_text(strip=True)
                race_num_match = re.search(r'\d+', raw_race_num)
                race_number = race_num_match.group(0) if race_num_match else raw_race_num

                order_cells = cells[1].find('p', class_='num')
                if order_cells:
                    numbers = re.findall(r'\d+', order_cells.get_text(strip=True))
                    order = '-'.join(numbers)
                    order = f'="{order}"'
                else:
                    order = ''

                refund_tag = row.find('td', class_='refund')
                if refund_tag:
                    attention_span = refund_tag.find('span', class_='attention')
                    refund_amount = attention_span.get_text(strip=True).replace(',', '') if attention_span else refund_tag.get_text(strip=True).replace(',', '')
                else:
                    refund_amount = ''

                pop_tag = row.find('td', class_='pop')
                if pop_tag:
                    attention_span = pop_tag.find('span', class_='attention')
                    popularity = attention_span.get_text(strip=True) if attention_span else pop_tag.get_text(strip=True)
                else:
                    popularity = ''

                res_dict = {
                    'race_id': race_id,
                    '3連単_的中': order,
                    '3連単_配当金(円)': refund_amount,
                    '人気': popularity
                }

                if race_id:
                    extracted_data_by_id[race_id] = res_dict

                fallback_key = f"{keirinjo_name}_{race_number}"
                if fallback_key not in extracted_data_by_key:
                    extracted_data_by_key[fallback_key] = res_dict

    # カラムの追加・型キャスト
    for col in ['3連単_的中', '3連単_配当金(円)', '人気']:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].astype(object)

    new_cols = [
        "1着モデル_A-BCD流し判定", "1着モデル_A-BCD流し_合成オッズ",
        "1着モデル_ボックス判定", "1着モデル_ボックス_合成オッズ",
        "3着以内モデル_A-BCD流し判定", "3着以内モデル_A-BCD流し_合成オッズ",
        "3着以内モデル_ボックス判定", "3着以内モデル_ボックス_合成オッズ",
        "運用判定_3着以内モデル判定", "運用判定_3着以内モデル_合成オッズ",
        "運用判定_1着モデル判定", "運用判定_1着モデル_合成オッズ"
    ]
    for col in new_cols:
        df[col] = ""
        df[col] = df[col].astype(object)

    print("各レースのオッズ取得および合成オッズ計算処理を開始します...")

    for i, row in df.iterrows():
        matched_result = None
        row_race_id = extract_race_id(row.get('race_id', '')) or extract_race_id(row.get('URL', '')) or extract_race_id(row.get('url', ''))
        
        if row_race_id and row_race_id in extracted_data_by_id:
            matched_result = extracted_data_by_id[row_race_id]
        else:
            raw_r_num = str(row.get('レース番号', ''))
            r_num_match = re.search(r'\d+', raw_r_num)
            clean_r_num = r_num_match.group(0) if r_num_match else raw_r_num
            fallback_key = f"{row.get('競輪場')}_{clean_r_num}"
            if fallback_key in extracted_data_by_key:
                matched_result = extracted_data_by_key[fallback_key]

        if matched_result:
            df.loc[i, '3連単_的中'] = str(matched_result['3連単_的中'])
            df.loc[i, '3連単_配当金(円)'] = str(matched_result['3連単_配当金(円)'])
            df.loc[i, '人気'] = str(matched_result['人気'])
            if not row_race_id and matched_result.get('race_id'):
                row_race_id = matched_result['race_id']

        # 全オッズ辞書の取得
        odds_dict = fetch_race_odds_dict(row_race_id)

        # 確定配当オッズ（フォールバック用）
        payoff_val = parse_payoff(df.loc[i, '3連単_配当金(円)'])
        fallback_hit_odds = (payoff_val / 100.0) if payoff_val else None

        order = df.loc[i, "3連単_的中"]
        actual_nums = parse_numbers(order)

        cars_1st_base = parse_numbers(row.get("3連単_1着"))
        cars_1st_hoketsu = parse_numbers(row.get("1着_補欠"))
        cars_top3_base = parse_numbers(row.get("3連単_3着以内"))
        cars_top3_hoketsu = parse_numbers(row.get("3着以内_補欠"))

        # ==========================================
        # Ⅰ. 1着モデル基準
        # ==========================================
        if len(cars_1st_base) >= 3:
            combined_1st = list(dict.fromkeys(cars_1st_base + cars_1st_hoketsu))
            candidates_1st_4 = combined_1st[:4]
            A_1st, BCD_1st = candidates_1st_4[0], candidates_1st_4[1:]

            bets_nagashi_1st = [(A_1st, b, c) for b, c in permutations(BCD_1st, 2)]
            if len(actual_nums) == 3:
                is_hit = any(actual_nums == [A_1st, b, c] for b, c in permutations(BCD_1st, 2))
                df.loc[i, "1着モデル_A-BCD流し判定"] = "的中" if is_hit else "不的中"
            df.loc[i, "1着モデル_A-BCD流し_合成オッズ"] = calculate_synthetic_odds(bets_nagashi_1st, odds_dict, fallback_hit_odds)

            bets_box_1st = list(permutations(candidates_1st_4, 3))
            if len(actual_nums) == 3:
                is_hit = tuple(actual_nums) in bets_box_1st
                df.loc[i, "1着モデル_ボックス判定"] = "的中" if is_hit else "不的中"
            df.loc[i, "1着モデル_ボックス_合成オッズ"] = calculate_synthetic_odds(bets_box_1st, odds_dict, fallback_hit_odds)
        else:
            df.loc[i, "1着モデル_A-BCD流し判定"] = "出目なし"
            df.loc[i, "1着モデル_ボックス判定"] = "出目なし"
            df.loc[i, "1着モデル_A-BCD流し_合成オッズ"] = 0.00
            df.loc[i, "1着モデル_ボックス_合成オッズ"] = 0.00

        # ==========================================
        # Ⅱ. 3着以内モデル基準
        # ==========================================
        if len(cars_top3_base) >= 3:
            combined_top3 = list(dict.fromkeys(cars_top3_base + cars_top3_hoketsu))
            candidates_top3_4 = combined_top3[:4]
            A_top3, BCD_top3 = candidates_top3_4[0], candidates_top3_4[1:]

            bets_nagashi_top3 = [(A_top3, b, c) for b, c in permutations(BCD_top3, 2)]
            if len(actual_nums) == 3:
                is_hit = any(actual_nums == [A_top3, b, c] for b, c in permutations(BCD_top3, 2))
                df.loc[i, "3着以内モデル_A-BCD流し判定"] = "的中" if is_hit else "不的中"
            df.loc[i, "3着以内モデル_A-BCD流し_合成オッズ"] = calculate_synthetic_odds(bets_nagashi_top3, odds_dict, fallback_hit_odds)

            bets_box_top3 = list(permutations(candidates_top3_4, 3))
            if len(actual_nums) == 3:
                is_hit = tuple(actual_nums) in bets_box_top3
                df.loc[i, "3着以内モデル_ボックス判定"] = "的中" if is_hit else "不的中"
            df.loc[i, "3着以内モデル_ボックス_合成オッズ"] = calculate_synthetic_odds(bets_box_top3, odds_dict, fallback_hit_odds)
        else:
            df.loc[i, "3着以内モデル_A-BCD流し判定"] = "出目なし"
            df.loc[i, "3着以内モデル_ボックス判定"] = "出目なし"
            df.loc[i, "3着以内モデル_A-BCD流し_合成オッズ"] = 0.00
            df.loc[i, "3着以内モデル_ボックス_合成オッズ"] = 0.00

        # ==========================================
        # Ⅲ. 運用判定基準 (24点ボックス)
        # ==========================================
        op_logic = str(row.get("運用判定", "")).strip()

        # パターン指定 (見送り等の場合は A-B-C-E として合成オッズを算出)
        effective_op_pattern = op_logic if op_logic in ["A-B-C-E", "A-B-D-E"] else "A-B-C-E"

        # 【3着以内モデル運用】
        combined_top3 = list(dict.fromkeys(cars_top3_base + cars_top3_hoketsu))
        if len(combined_top3) >= 5:
            A3, B3, C3, D3, E3 = combined_top3[:5]
            box_cars_top3 = [A3, B3, C3, E3] if effective_op_pattern == "A-B-C-E" else [A3, B3, D3, E3]
            bets_op_top3 = list(permutations(box_cars_top3, 3))
            
            if op_logic in ["A-B-C-E", "A-B-D-E"]:
                if len(actual_nums) == 3:
                    is_hit = tuple(actual_nums) in bets_op_top3
                    df.loc[i, "運用判定_3着以内モデル判定"] = "的中" if is_hit else "不的中"
            else:
                df.loc[i, "運用判定_3着以内モデル判定"] = "見送り" if op_logic == "見送り" else "対象外"

            df.loc[i, "運用判定_3着以内モデル_合成オッズ"] = calculate_synthetic_odds(bets_op_top3, odds_dict, fallback_hit_odds)
        else:
            df.loc[i, "運用判定_3着以内モデル判定"] = "出目なし"
            df.loc[i, "運用判定_3着以内モデル_合成オッズ"] = 0.00

        # 【1着モデル運用】
        combined_1st = list(dict.fromkeys(cars_1st_base + cars_1st_hoketsu))
        if len(combined_1st) >= 5:
            A1, B1, C1, D1, E1 = combined_1st[:5]
            box_cars_1st = [A1, B1, C1, E1] if effective_op_pattern == "A-B-C-E" else [A1, B1, D1, E1]
            bets_op_1st = list(permutations(box_cars_1st, 3))
            
            if op_logic in ["A-B-C-E", "A-B-D-E"]:
                if len(actual_nums) == 3:
                    is_hit = tuple(actual_nums) in bets_op_1st
                    df.loc[i, "運用判定_1着モデル判定"] = "的中" if is_hit else "不的中"
            else:
                df.loc[i, "運用判定_1着モデル判定"] = "見送り" if op_logic == "見送り" else "対象外"

            df.loc[i, "運用判定_1着モデル_合成オッズ"] = calculate_synthetic_odds(bets_op_1st, odds_dict, fallback_hit_odds)
        else:
            df.loc[i, "運用判定_1着モデル判定"] = "出目なし"
            df.loc[i, "運用判定_1着モデル_合成オッズ"] = 0.00

    # A率〜I率、CT値、スコア の列を一番最後に移動
    df = reorder_columns_rates_to_end(df)

    try:
        output_file = 'updated_keirin_race_summary.csv'
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"CSVファイルが正常に更新され、'{output_file}'として保存されました。")
    except Exception as e:
        print(f"エラー: CSVファイルの保存中にエラーが発生しました: {e}")

if __name__ == '__main__':
    now = datetime.now()
    target_date = now.strftime("%Y/%m/%d")
    csv_filename = 'updated_keirin_race_summary.csv'
    fetch_and_update_keirin_data(csv_filename, target_date)