import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re

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
        response.raise_for_status()  # HTTPエラーがあれば例外を発生させる
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
        if not header or '2車単' not in header.get_text():
           continue  # 3連単以外はスキップ
        
        # velodromeクラスで競輪場名を抽出（修正済み）
        velodrome_tags = block.find_all("span", class_="velodrome")
        if not velodrome_tags:
            continue

        for v in velodrome_tags:
            keirinjo_name = v.get_text(strip=True)
            if not keirinjo_name:
                print("警告: 競輪場名が特定できませんでした。")
                continue

            # そのvelodromeタグから次にあるtableを取得する（ブロック内で動的に切り替え）
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

                # 着順（pタグのclassがnumのテキストから数字抽出）
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
                    '2車単_的中': order,
                    '2車単_配当金(円)': refund_amount,
                    '人気': popularity
                }

    # 必要なカラムをCSVに追加
    for col in ['2車単_的中', '2車単_配当金(円)', '人気']:
        if col not in df.columns:
            df[col] = ''

    # 抽出データでCSVの該当行を更新
    for index, row in df.iterrows():
        key = f"{row.get('競輪場')}_{str(row.get('レース番号'))}"
        if key in extracted_data:
            result = extracted_data[key]
            df.loc[index, '2車単_的中'] = result['2車単_的中']
            df.loc[index, '2車単_配当金(円)'] = result['2車単_配当金(円)']
            df.loc[index, '人気'] = result['人気']

    # 更新後のCSVファイル保存
    try:
        output_file = 'updated_keirin_race_summary2.csv'
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
