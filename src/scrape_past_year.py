import pandas as pd
import re
from time import sleep
from bs4 import BeautifulSoup
import requests
from tqdm import tqdm
from datetime import datetime, timedelta
import calendar
import sys
from io import StringIO
import importlib
# from race_id_scrape import race_id_scrape # 仮に別ファイルから関数をインポート
# from race_data_scrape import race_data_scrape # 仮に別ファイルから関数をインポート

race_id_scrape = importlib.import_module("1_race_id_scrape")
race_data_scrape = importlib.import_module("2_race_data_scrape")

# main関数
if __name__ == '__main__':
    # 過去13ヶ月〜24ヶ月分の全レースIDを格納するリスト
    all_race_ids = []
    
    today = datetime.today()

    print("過去13ヶ月～24ヶ月分のレースIDの取得を開始します。")

    # ★★★ 変更点 ★★★
    # 13ヶ月前から24ヶ月前までを取得するために、ループの範囲を変更
    for i in range(13, 25):
        # 基準日から月を遡る計算
        target_date = today.replace(day=1)
        for _ in range(i):
            target_date = target_date - timedelta(days=1)
            target_date = target_date.replace(day=1)
        
        month_to_scrape = target_date.strftime("%Y/%m/")
        
        print(f"\n>> {month_to_scrape} のデータを取得中...")
        
        monthly_ids = race_id_scrape(month_to_scrape)
        all_race_ids.extend(monthly_ids)
        
        print(f"{month_to_scrape} の処理が完了しました。")

    print(f"\n--- 全ての処理が完了しました ---")
    print(f"合計 {len(all_race_ids)} 件のレースIDを取得しました。")

    # 取得したIDを元に、出走表・レース情報・払戻金データを取得
    # race_data_scrape関数は、提示されたコードと同じものを使用
    race_data = race_data_scrape(all_race_ids)
    
    # 結合用に、一時的なファイル名で保存
    pd.to_pickle(race_data[0], 'race_info_PAST.pkl')
    pd.to_pickle(race_data[1], 'race_card_PAST.pkl')
    # ilocは元のままと仮定
    pd.to_pickle(race_data[2].iloc[:,:11], 'race_return_PAST.pkl')

    print(f"追加の過去データを '..._PAST.pkl' として一時保存しました。")
