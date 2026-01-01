import pandas as pd
import re
from time import sleep
from bs4 import BeautifulSoup
import requests
from tqdm import tqdm
from datetime import datetime, timedelta
import calendar
import sys
import importlib
# from race_data_scrape import race_data_scrape
# from back_sabun import back_sabun, bankcho
# from def_line_kyoudo import line_kyoudo

race_id_scrape = importlib.import_module("1_race_id_scrape")
race_data_scrape = importlib.import_module("2_race_data_scrape")
back_sabun = importlib.import_module("3_back_sabun")
bankcho = importlib.import_module("3_back_sabun")
line_kyoudo = importlib.import_module("4_def_line_kyoudo")

def race_id_scrape(kaisai_nengetu) :
    
    ul1 = "https://keirin.kdreams.jp/gamboo/schedule/search/" + kaisai_nengetu
    res = requests.get(ul1)
    res.encoding = ['EUC-JP']
    soup = BeautifulSoup(res.text, 'html.parser')
    kaisai_sches = soup.find_all('td',attrs={'class':'kaisai'}) 
    nen = kaisai_nengetu[0:4]
    gatu = kaisai_nengetu[5:7]
    # first_day = datetime.strptime(kaisai_nengetu + '01',"%Y/%m/%d")
    # last_day = datetime.strptime(kaisai_nengetu + str(calendar.monthrange(int(nen), int(gatu))[1]),"%Y/%m/%d")
    to_day = datetime.today()
    hi = to_day.day
    to_day = to_day.replace(hour=0, minute=0, second=0, microsecond=0)
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
        race_id_res = requests.get(race_url)
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
    
        sleep(1)        
    kaisai_lists.sort()    
    
    # -----------------------------月始から月末までを抜き取る ----------------
    for lis in kaisai_lists:
        r_date = datetime.strptime(lis[2:6]+'/'+lis[6:8]+'/'+lis[8:10],"%Y/%m/%d")
        ad_date = int(lis[10:12])-1
        r_date = r_date + timedelta(days=ad_date)
        #print(r_date)
        #sys.exit()  # デバッグ用に追加。実際の使用時は削除してください。

        if to_day == r_date :
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
        race_id_res = requests.get(race_url)
        race_id_res.encoding = ['EUC-JP']
        race_id_soup = BeautifulSoup(race_id_res.text, 'html.parser')
        
        sleep(1)
        
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
            
    
    print(' {}年 {}月 {}日の全 {} レースのIDを取得しました。'.format(nen,gatu,hi,len(all_race_ids)))
    
    return all_race_ids

# main関数
if __name__ == '__main__':

    # 今日の日付を取得
    to_day_date = datetime.today().date()

    # strftime()を使って "yyyy/mm/" 形式の文字列に変換し、変数に代入
    to_day = to_day_date.strftime("%Y/%m/")
    to_day_yyyymmdd = to_day_date.strftime("%Y%m%d")

    race_id = race_id_scrape(to_day)
    # race_idが空でないことを確認
    if not race_id:
        print(f"{to_day_yyyymmdd}に開催されるレースはありませんでした。処理を終了します。")
        sys.exit()  # スクリプトを正常に終了
    pd.to_pickle(race_id,'race_id_' + to_day_yyyymmdd + '.pkl')

    # レースIDを取得したら、レースデータをスクレイプ
    race_ids = pd.read_pickle('race_id_' + to_day_yyyymmdd + '.pkl')
    race_data = race_data_scrape.race_data_scrape(race_ids)
    pd.to_pickle(race_data[0],'race_info_' + to_day_yyyymmdd + '.pkl')
    pd.to_pickle(race_data[1],'race_card_' + to_day_yyyymmdd + '.pkl')
    pd.to_pickle(race_data[2].iloc[:,:11],'race_return_' + to_day_yyyymmdd + '.pkl')

    # レースカードのデータをバックサブン処理
    r_syu= pd.read_pickle('race_card_' + to_day_yyyymmdd + '.pkl')
    r_syu_s = back_sabun.back_sabun(r_syu)

    r_inf = pd.read_pickle('race_info_' + to_day_yyyymmdd + '.pkl')
    r_inf_b = bankcho.bankcho(r_inf)

    pd.to_pickle(r_syu_s,'race_card2_' + to_day_yyyymmdd + '.pkl')
    pd.to_pickle(r_inf_b,'today_race_info2.pkl')

    # ライン強度を計算
    r_syu2= pd.read_pickle('race_card2_' + to_day_yyyymmdd + '.pkl')
    r_syu_s2 = line_kyoudo.line_kyoudo(r_syu2)

    pd.to_pickle(r_syu_s2,'today_race_card3.pkl')