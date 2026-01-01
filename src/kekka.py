import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
from itertools import permutations # 順列を生成するためにitertoolsを追加

def parse_numbers(value):
    """セルの値から数字を抽出してリスト化"""
    if pd.isna(value):
        return []
    s = str(value).replace('="', '').replace('"', '')
    nums = re.findall(r'\d+', s)
    return nums

def triple_equal(order, nums):
    """3連単的中データと[1着,2着,3着]の完全一致を判定"""
    order_nums = parse_numbers(order)
    return order_nums == [str(x) for x in nums]


def fetch_and_update_keirin_data(csv_file, date_str):
    """
    指定された日付のKドリームスサイトから払戻金データを取得し、CSVを更新する関数。

    Args:
        csv_file (str): 更新するCSVファイルのパス。
        date_str (str): 情報を取得する日付（例: '2024/09/20'）。
    """
    # 日付文字列を YYYY/MM/DD 形式に変換
    try:
        url_date = datetime.strptime(date_str, '%Y/%m/%d').strftime('%Y/%m/%d')
        # URLを構築
        url = f"https://keirin.kdreams.jp/harailist/{url_date}/"
    except ValueError:
        print("エラー: 日付の形式が無効です。'YYYY/MM/DD'形式で指定してください。")
        return

    try:
        # ウェブサイトにアクセスしてHTMLコンテンツを取得
        print(f"URL: {url} から情報を取得中...")
        response = requests.get(url, timeout=10)
        response.raise_for_status() # HTTPエラーがあれば例外を発生させる
        html_content = response.text
        print("情報取得に成功しました。")
    except requests.exceptions.RequestException as e:
        print(f"エラー: ウェブサイトへのアクセスに失敗しました。{e}")
        return

    # CSVファイルのエンコードを自動判別して読み込む
    try:
        df = pd.read_csv(csv_file, encoding='utf-8')
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(csv_file, encoding='cp932')
        except Exception as e:
            print(f"エラー: CSVファイルの読み込み中にエラーが発生しました: {e}")
            return
    except FileNotFoundError:
        print(f"エラー: '{csv_file}' が見つかりません。")
        return

    # BeautifulSoupでHTMLを解析
    soup = BeautifulSoup(html_content, 'html.parser')
    extracted_data = {}

    # daily-refund-result-listのブロックをすべて抽出
    daily_blocks = soup.find_all('div', class_='daily-refund-result-list')
    if not daily_blocks:
        print("警告: ウェブサイトから払戻金データが見つかりませんでした。")
        return

    for block in daily_blocks:
        # 3連単のヘッダーがあるか確認
        header = block.find('h3', class_='daily-refund-result-list_heading')
        if not header or '3連単' not in header.get_text():
           continue # 3連単以外はスキップ
        
        # velodromeクラスで競輪場名を抽出
        velodrome_tags = block.find_all("span", class_="velodrome")
        if not velodrome_tags:
            continue

        for v in velodrome_tags:
            keirinjo_name = v.get_text(strip=True)
            if not keirinjo_name:
                print("警告: 競輪場名が特定できませんでした。")
                continue

            # そのvelodromeタグから次にあるtableを取得する
            table = v.find_next('table')
            if not table:
                continue

            print(f"抽出された競輪場名: {keirinjo_name}")

            # テーブルのヘッダー行を除き、レース情報を抽出
            for row in table.find_all('tr')[1:]:
                cells = row.find_all('td')
                if len(cells) < 4:
                    continue

                # レース番号
                race_number = cells[0].get_text(strip=True)

                # 着順
                order_cells = cells[1].find('p', class_='num')
                if order_cells:
                    numbers = re.findall(r'\d+', order_cells.get_text(strip=True))
                    order = '-'.join(numbers)
                    order = f'="{order}"'
                else:
                    order = ''

                # 配当金取得
                refund_tag = row.find('td', class_='refund')
                if refund_tag:
                    attention_span = refund_tag.find('span', class_='attention')
                    refund_amount = attention_span.get_text(strip=True).replace(',', '') if attention_span else refund_tag.get_text(strip=True).replace(',', '')
                else:
                    refund_amount = ''

                # 人気取得
                pop_tag = row.find('td', class_='pop')
                if pop_tag:
                    attention_span = pop_tag.find('span', class_='attention')
                    popularity = attention_span.get_text(strip=True) if attention_span else pop_tag.get_text(strip=True)
                else:
                    popularity = ''

                # 辞書格納例（複合キー）
                key = f"{keirinjo_name}_{race_number}"
                if key not in extracted_data:
                    extracted_data[key] = {}
                    extracted_data[key] = {
                        '3連単_的中': order,
                        '3連単_配当金(円)': refund_amount,
                        '人気': popularity
                    }

    # 必要なカラムをCSVに追加
    for col in ['3連単_的中', '3連単_配当金(円)', '人気']:
        if col not in df.columns:
            df[col] = ''

    # 抽出データでCSVの該当行を更新
    for index, row in df.iterrows():
        key = f"{row.get('競輪場')}_{str(row.get('レース番号'))}"
        if key in extracted_data:
            result = extracted_data[key]
            df.loc[index, '3連単_的中'] = result['3連単_的中']
            df.loc[index, '3連単_配当金(円)'] = result['3連単_配当金(円)']
            df.loc[index, '人気'] = result['人気']

    # === 判定列を追加 ===
    df["A=B-abcd判定"] = ""
    # ① A=B-abcdCD判定を A=B-CD判定に変更
    df["A=B-CD判定"] = ""
    # ① AB-abc-abc判定を A-BCD-BCD判定に変更
    df["A-BCD-BCD判定"] = ""
    # ② B-ACD-ACD判定を追加
    df["B-ACD-ACD判定"] = ""
    df["ABCD-ABCD-ABCD判定"] = ""

    # ★★★ 新規追加 ★★★
    df["ABCボックス判定"] = ""
    df["ABDボックス判定"] = ""

    for i, row in df.iterrows():
        combo_1 = parse_numbers(row.get("3連単_1着")) # 例: [1, 5, 3]
        abc_list_full = parse_numbers(row.get("3連単_3着以内")) # 例: [7, 2, 4]
        D_list = parse_numbers(row.get("1着_補欠")) # 例: [2]
        d_list = parse_numbers(row.get("3着以内_補欠")) # 例: [3]
        order = row.get("3連単_的中")

        # 少なくともA, B, abcd_listが必要
        if len(combo_1) < 2 or not abc_list_full:
            continue

        A = combo_1[0]
        B = combo_1[1]
        # ★★★ ここから定義を修正 ★★★
        # C (大文字): 3連単_1着の右端
        C = combo_1[2] if len(combo_1) >= 3 else None
        # D (大文字): 1着_補欠
        D = D_list[0] if D_list else None

        # --- 小文字 a, b, c, d の新しい定義 ---
        # 3連単_3着以内 の車番
        a = abc_list_full[0] 
        b = abc_list_full[1]
        c = abc_list_full[2]
        
        # c (小文字): 3連単_3着以内の右端 12/01修正
        # c = abc_list_full[-1] if abc_list_full else None
        
        # d (小文字): 3着以内_補欠
        d = d_list[0] if d_list else None
        
        # a, b, c のリスト (小文字)
        abc_list = abc_list_full
        
        # d を含む abcd リスト（A=B-abcd判定で使用）
        abcd_list_with_d = abc_list + ([d] if d else [])
        
        # 着順別判定に必要な候補リストを準備
        # '3連単_1着' (A, B, C) と '1着_補欠' (D) のユニークなリスト
        all_fixed_candidates = list(set([x for x in combo_1[:3] + D_list if x]))

        # 実際に的中した着順をパース（文字列リスト）
        actual_nums = parse_numbers(order)

        # 3連単が成立しない場合はスキップ
        if len(actual_nums) != 3:
            continue

        actual_1, actual_2, actual_3 = actual_nums

        # --- 判定①: A=B−abcd（折り返し） ---
        hit1 = False
        # 3着候補を abcd_list_with_d に変更
        if abcd_list_with_d:
            for x in abcd_list_with_d:
                if triple_equal(order, [A, B, x]) or triple_equal(order, [B, A, x]):
                    hit1 = True
                    break
        df.loc[i, "A=B-abcd判定"] = "的中" if hit1 else "不的中"

        # --- 判定②: A=B−CD（折り返し + C,D追加） ---
        # 3着候補を C (大文字) と D (大文字) のみに限定する
        candidates_CD_new = []
        if C:
            candidates_CD_new.append(C)
        if D:
            candidates_CD_new.append(D)
        
        candidates_CD_new = list(set(candidates_CD_new))

        hit2 = False
        if candidates_CD_new:
            for x in candidates_CD_new:
                if triple_equal(order, [A, B, x]) or triple_equal(order, [B, A, x]):
                    hit2 = True
                    break
        df.loc[i, "A=B-CD判定"] = "的中" if hit2 else "不的中"

    # --- 新規判定③: A-BCD-BCD判定 (1着:A固定, 2,3着:BCDで流し) ---
        hit3 = False
        if A and len(all_fixed_candidates) >= 2:
            # 2着・3着の候補リスト (B, C, D)
            # A以外のすべての確定候補 [B, C, D] を抽出
            candidates_2_3 = [c for c in all_fixed_candidates if c != A]
            
            # 実際に的中した着順をパース
            actual_nums = parse_numbers(order)
            
            if len(actual_nums) == 3:
                actual_1, actual_2, actual_3 = actual_nums
                
                # 1着判定
                is_1_hit = actual_1 == A
                
                # 2着判定: BCDに含まれ、かつ1着ではないこと
                is_2_hit = actual_2 in candidates_2_3 and actual_2 != actual_1
                
                # 3着判定: BCDに含まれ、かつ1着でも2着でもないこと
                is_3_hit = actual_3 in candidates_2_3 and actual_3 != actual_1 and actual_3 != actual_2
                
                if is_1_hit and is_2_hit and is_3_hit:
                    hit3 = True

        df.loc[i, "A-BCD-BCD判定"] = "的中" if hit3 else "不的中"

        # --- 新規判定④: B-ACD-ACD判定 (1着:B固定, 2,3着:ACDで流し) ---
        hit4 = False
        if B and len(all_fixed_candidates) >= 2:
            # 2着・3着の候補リスト (A, C, D)
            # B以外のすべての確定候補 [A, C, D] を抽出
            candidates_2_3_B = [c for c in all_fixed_candidates if c != B]
            
            # 実際に的中した着順をパース
            actual_nums = parse_numbers(order)
            
            if len(actual_nums) == 3:
                actual_1, actual_2, actual_3 = actual_nums
                
                # 1着判定
                is_1_hit_B = actual_1 == B
                
                # 2着判定: ACDに含まれ、かつ1着ではないこと
                is_2_hit_B = actual_2 in candidates_2_3_B and actual_2 != actual_1
                
                # 3着判定: ACDに含まれ、かつ1着でも2着でもないこと
                is_3_hit_B = actual_3 in candidates_2_3_B and actual_3 != actual_1 and actual_3 != actual_2
                
                if is_1_hit_B and is_2_hit_B and is_3_hit_B:
                    hit4 = True

        df.loc[i, "B-ACD-ACD判定"] = "的中" if hit4 else "不的中"   
    # --- 新規判定⑤: ABCD-ABCD-ABCD判定（ABCDボックス買い） ---
        hit5 = False
        
        # 買い目候補プール: A, B, C, D を含むユニークなリスト（all_fixed_candidatesを再利用）
        # 例: A=1, B=5, C=3, D=2 の場合、候補は [1, 5, 3, 2]
        candidates_ABCD = all_fixed_candidates
        
        # 実際に的中した着順をパース
        actual_nums = parse_numbers(order)

        if len(actual_nums) == 3 and len(candidates_ABCD) >= 3:
            # 候補プールから3つ選ぶすべての順列（ボックス買い）を生成
            all_bets = list(permutations(candidates_ABCD, 3))

            # 実際の的中着順が買い目リストに含まれるかチェック
            # actual_nums = [1, 3, 4]
            # all_bets の要素はタプル (例: ('1', '5', '3')) なので、リストと比較するために変換
            actual_tuple = tuple(actual_nums)
            
            if actual_tuple in all_bets:
                hit5 = True

        df.loc[i, "ABCD-ABCD-ABCD判定"] = "的中" if hit5 else "不的中"
    
    # --- 新規判定⑥: C=B-A判定_前回定義 (4点: C-B-A, B-C-A, C-B-D, B-C-Dと仮定) ---
        # 1,2着はCとBの折り返し、3着はAまたはD (A, B, C, Dは'3連単_1着'と'1着_補欠'から抽出された車番)
        hit6 = False
        candidates_3rd = []
        if A:
            candidates_3rd.append(A)
        if D:
            candidates_3rd.append(D)
            
        candidates_3rd = list(set(candidates_3rd))

        if candidates_3rd and C and B:
            for x in candidates_3rd:
                # C-B-X, B-C-X
                if triple_equal(order, [C, B, x]) or triple_equal(order, [B, C, x]):
                    hit6 = True
                    break
        df.loc[i, "C=B-AD判定"] = "的中" if hit6 else "不的中"
    
    # --- 新規判定⑦: C=B-A判定_今回定義 (4点: C-B-A, C-B-残) のロジックを修正 ---
        # C, B, A は大文字C, B, A (3連単_1着) を使う
        hit7 = False
        if C and B and A:
            if actual_1 == C and actual_2 == B:
                third_place = actual_3
                
                # S = {A, B, C} 以外の車番を「残車」とする
                all_racers = set(str(n) for n in range(1, 10)) # 全ての車番候補 (文字列として)
                key_racers = {str(A), str(B), str(C)}
                remaining_racers = all_racers - key_racers

                # 3着が A または 残車 の場合に的中
                if third_place == str(A) or third_place in remaining_racers:
                    hit7 = True
        df.loc[i, "C=B-A判定"] = "的中" if hit7 else "不的中"
    
    # --- 新規判定⑧: c=b-a判定_今回定義 (4点: c-b-a, b-c-a) のロジックを修正 ---
        # c, b, a は小文字c, b, a (3連単_3着以内) を使う
        hit8 = False
        if c and b and a:
            # 3着が a であることが必須
            if actual_3 == str(a):
                # 1着が c、2着が b
                case_1 = (actual_1 == str(c) and actual_2 == str(b))
                # 1着が b、2着が c
                case_2 = (actual_1 == str(b) and actual_2 == str(c))
                
                if case_1 or case_2:
                    hit8 = True
        df.loc[i, "c=b-a判定"] = "的中" if hit8 else "不的中"
    
    # --- 新規判定⑨: ABCボックス判定 (6点: A, B, Cの全順列) ---
        hit9 = False
        candidates_ABC = list(set([A, B, C]))
        
        # 候補が3つ揃っていることを確認
        if len(candidates_ABC) == 3:
            # 候補車番を文字列に変換してから順列を生成
            str_candidates_ABC = [str(x) for x in candidates_ABC]
            all_bets = list(permutations(str_candidates_ABC, 3))

            actual_tuple = tuple(actual_nums)
            
            if actual_tuple in all_bets:
                hit9 = True

        df.loc[i, "ABCボックス判定"] = "的中" if hit9 else "不的中" 

        
        # --- 新規判定⑩: ABDボックス判定 (6点: A, B, Dの全順列) ---
        hit10 = False
        candidates_ABD = list(set([A, B, D]))
        
        # 候補が3つ揃っていることを確認
        if len(candidates_ABD) == 3:
             # 候補車番を文字列に変換してから順列を生成
            str_candidates_ABD = [str(x) for x in candidates_ABD]
            all_bets = list(permutations(str_candidates_ABD, 3))

            actual_tuple = tuple(actual_nums)
            
            if actual_tuple in all_bets:
                hit10 = True

        df.loc[i, "ABDボックス判定"] = "的中" if hit10 else "不的中"

    # 更新後のCSVファイル保存
    try:
        output_file = 'updated_keirin_race_summary.csv'
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"CSVファイルが正常に更新され、'{output_file}'として保存されました。")
    except Exception as e:
        print(f"エラー: CSVファイルの保存中にエラーが発生しました: {e}")


if __name__ == '__main__':
    # 取得したい日付を指定
    now = datetime.now()

    # yyyy/mm/dd形式の文字列に変換
    formatted_date = now.strftime("%Y/%m/%d")
    
    target_date = formatted_date

    # CSVファイル名
    csv_filename = 'keirin_race_summary.csv'

    fetch_and_update_keirin_data(csv_filename, target_date)