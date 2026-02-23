import pandas as pd
import re
from time import sleep
from bs4 import BeautifulSoup
import requests
from tqdm import tqdm
from datetime import datetime, timedelta
import calendar
import sys


def race_id_scrape(kaisai_nengetu) :

    session = requests.Session() # ★★★ 1. セッションオブジェクトを作成 ★★★
    
    ul1 = "https://keirin.kdreams.jp/gamboo/schedule/search/" + kaisai_nengetu
    #res = requests.get(ul1)
    res = session.get(ul1) # ★★★ 2. session.get() を使用 ★★★
    res.encoding = ['EUC-JP']
    soup = BeautifulSoup(res.text, 'html.parser')
    kaisai_sches = soup.find_all('td',attrs={'class':'kaisai'}) 
    nen = kaisai_nengetu[0:4]
    gatu = kaisai_nengetu[5:7]
    first_day = datetime.strptime(kaisai_nengetu + '01',"%Y/%m/%d")
    last_day = datetime.strptime(kaisai_nengetu + str(calendar.monthrange(int(nen), int(gatu))[1]),"%Y/%m/%d")
    kaisai_lists = []
    kaisai_list = []


    for i in range(len(kaisai_sches)):
        if  kaisai_sches[i].find('a'):
            sche_ht = str(kaisai_sches[i].find('a'))
            sche_re = re.findall(r'\d+',sche_ht)
            kaisai_lists.append(sche_re[1])
        else :
            continue
    
    print(' {}年 {}月 の解析をしました。'.format(nen,gatu))
    
    # -----------------------------------------------------------------------
    # ------------------- 開催リストから開催日数分のリストを作る ----------------
    print('開催の日数をを調べます。')
    
    race_id_url = 'https://keirin.kdreams.jp/gamboo/keirin-kaisai/race-card/result/'


    for i in tqdm(range(len(kaisai_lists))): #len(kaisai_lists)
        
        
        # ------------------------URLの生成-------------------------------
        race_id_2 = kaisai_lists[i]
        race_id_1 = kaisai_lists[i] [0:10]
        race_id_3 = '01/'
        race_url = race_id_url + race_id_1 +"/"+race_id_2+"/"+race_id_3
        
        # -----------------------htmlの取得-------------------------------
        #race_id_res = requests.get(race_url)
        race_id_res = session.get(race_url) # ★★★ 3. session.get() を使用 ★★★
        race_id_res.encoding = ['EUC-JP']
        race_id_soup = BeautifulSoup(race_id_res.text, 'html.parser')
        
        # -----------------------開催日数の所得------------------------------
        day_len = len(race_id_soup.find_all('span',attrs={'class':'day'}))
        date_str = kaisai_lists[i]
        
    
        # -----------------------開催日数分のリストを追加---------------------
        for j in range(2,day_len+1):
            
            date_list =list(date_str)
            date_list[11:12] = str(j)
            date_list = ''.join(date_list)
            kaisai_lists.append(date_list) 
    
        sleep(0.4)        
    kaisai_lists.sort()    
    
    # -----------------------------月始から月末までを抜き取る ----------------
    for lis in kaisai_lists:
        r_date = datetime.strptime(lis[2:6]+'/'+lis[6:8]+'/'+lis[8:10],"%Y/%m/%d")
        ad_date = int(lis[10:12])-1
        r_date = r_date + timedelta(days=ad_date)
        
        if first_day <= r_date <= last_day :
            kaisai_list.append(lis)
    
    
    # -----------------------------------------------------------------------
    # ------------------------- すべてのレースIDを取得 ------------------------
    print('すべてのレースIDをを調べます。')
    
    all_race_ids = []
    race_id_url = 'https://keirin.kdreams.jp/gamboo/keirin-kaisai/race-card/result/'
    
    for i in tqdm(range(len(kaisai_list))):#len(kaisai_lists)
        race_id_2 = kaisai_list[i]
        race_id_1 = kaisai_list[i] [0:10]
        race_id_3 = '01/'
        race_url = race_id_url + race_id_1 +"/"+race_id_2+"/"+race_id_3
        
        # -----------------------htmlの取得-------------------------------
        #race_id_res = requests.get(race_url)
        race_id_res = session.get(race_url) # ★★★ 4. session.get() を使用 ★★★
        race_id_res.encoding = ['EUC-JP']
        race_id_soup = BeautifulSoup(race_id_res.text, 'html.parser')
        
        sleep(0.4)
        
        #------------------------レース数の取得----------------------------
        try:
            if re.findall(r'\d+',race_id_soup.find('div',attrs={'class':'kaisai_race_data_nav'}).find_all('li')[-1].text)[0]:
                race_max_num = int(re.findall(r'\d+',race_id_soup.find('div',attrs={'class':'kaisai_race_data_nav'}).find_all('li')[-1].text)[0]) 
                #------------------------すべてのレースIDの取得--------------------
                for j in range(1,race_max_num+1,1):
                    all_race_url_num = str(j).zfill(2)
                    all_race_id = str(race_id_2+all_race_url_num)
                    all_race_ids.append(all_race_id)
                else:
                    continue
                
        except AttributeError:
            print(all_race_id,'開催が中止されています')
                    
            
        except IndexError:
            print('レースが中止されています')
            
    
    print(' {}年 {}月 の全 {} レースのIDを取得しました。'.format(nen,gatu,len(all_race_ids)))
    
    return all_race_ids

# main関数
if __name__ == '__main__':
    # 過去4ヶ月分の全レースIDを格納するリストを準備
    all_race_ids = []
    
    # 基準となる今日の日付を取得
    today = datetime.today()

    print("先月から過去12ヶ月分のレースIDの取得を開始します。")

    # 【変更点】ループの開始を1にすることで、今月を除外し先月から開始する
    # 1:先月, 2:2ヶ月前, 3:3ヶ月前, 4:4ヶ月前
    #for i in range(39, 51):
    for i in range(1,2): #1か月分だけはこっち
    #for i in range(1,4): #1か月分だけはこっち
        # 基準日から月を遡る計算
        target_date = today.replace(day=1)
        for _ in range(i):
            target_date = target_date - timedelta(days=1)
            target_date = target_date.replace(day=1)
        
        # "YYYY/MM/" 形式の文字列を作成
        month_to_scrape = target_date.strftime("%Y/%m/")
        
        print(f"\n>> {month_to_scrape} のデータを取得中...")
        
        # 各月のレースIDを取得
        monthly_ids = race_id_scrape(month_to_scrape)
        
        # 取得したIDを全体のリストに追加
        all_race_ids.extend(monthly_ids)
        
        print(f"{month_to_scrape} の処理が完了しました。")

    print(f"\n--- 全ての処理が完了しました ---")
    print(f"合計 {len(all_race_ids)} 件のレースIDを取得しました。")

    # 取得した全IDを一つのpklファイルに保存
    # ファイル名が分かりやすいように、期間を明記
    # ループ終了時のtarget_dateが最も古い月（4ヶ月前）になっている
    start_month = target_date.strftime("%Y%m")
    # 先月の年月を計算
    last_month_date = today.replace(day=1) - timedelta(days=1)
    end_month = last_month_date.strftime("%Y%m")
    
    output_filename = f'race_id_{start_month}-{end_month}.pkl'

    pd.to_pickle(all_race_ids, output_filename)
    print(f"全レースIDを {output_filename} に保存しました。")