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

def race_data_scrape(race_ids):
    entry_table = {}
    return_table = {}
    info_table = {}

    race_grs = ['ＧＰ','Ｇ１','Ｇ２','Ｇ３','Ｆ１','Ｆ２']

    session = requests.Session() # ループの前にセッションオブジェクトを作成

    try:  
        for i in tqdm(range(len(race_ids))):
            try:
                ur_1 = race_ids[i][:10]
                ur_2 = race_ids[i][:-2]
                ur_3 = race_ids[i][-2:]
                url = 'https://keirin.kdreams.jp/gamboo/keirin-kaisai/race-card/result/'+ur_1+'/'+ur_2+'/'+ur_3       
                #html = requests.get(url)
                html = session.get(url) # requests.get()の代わりにsession.get()を使う
                html.encoding = ["EUC-JP"]
                soup = BeautifulSoup(html.text,'html.parser')
                #p_htm = pd.read_html(url)
                p_htm = pd.read_html(StringIO(html.text))

                id_a = race_ids[i]
            except Exception as e:
                print('エラー')
                
            sleep(0.4)
            try:
                if len(p_htm) == 8:
                    pd_racecard = pd.DataFrame(p_htm[0])
                    pd_raceresult = pd.DataFrame(p_htm[6])
                    pd_harai = pd.DataFrame(p_htm[7])
                else:
                    pd_racecard = pd.DataFrame(p_htm[0])
                    pd_raceresult = pd.DataFrame(p_htm[3])
                    pd_harai = pd.DataFrame(p_htm[4]) 
                
                # --- ここから修正コードを挿入 ---
                # 払戻金テーブルのヘッダーがMultiIndex（階層的）かチェック
                if isinstance(pd_harai.columns, pd.MultiIndex):
                    # MultiIndexをフラットな1階層のインデックスに変換
                    # 例: ('2車単', '車番') -> '2車単_車番' という文字列に結合
                    pd_harai.columns = ['_'.join(map(str, col)).strip() for col in pd_harai.columns.values]
                # --- ここまで ---

                #race_grs = ['ＧＰ','Ｇ１','Ｇ２','Ｇ３','Ｆ１','Ｆ２']
                setcol = [ '予 想', '好 気 合',  '総 評', '枠 番', '車 番','選手名 府県/年齢/期別', '級 班', '脚 質','ギヤ 倍数', '競走得点',  'S', 'B', '逃', '捲', '差', 'マ', '1 着', '2 着', '3 着', '着 外', '勝 率', '2連 対率', '3連 対率', 'level_1','level_2']
                pd_racecard.columns = setcol

                pd_racecard = pd_racecard.drop(['好 気 合','level_1','level_2'],axis=1)
                pd_raceresult = pd_raceresult.sort_values('車 番')
                pd_raceresult = pd_raceresult.drop(['着差','上り','決ま り手','S ／ B','勝敗因'],axis=1)

                pd_racecard = pd.merge(pd_racecard,pd_raceresult,how='inner')
            except:
                pass
                
            # -----------------------選手名 府県/年齢/期別を分ける ----------------
            try:
                age = []
                gr_class = []
                sensyu = []
                #　name_sp = pd.DataFrame(columns=['name','age','class'])
                for name in pd_racecard['選手名 府県/年齢/期別']:
                    if '（欠車）' in name:
                        #print('（欠車）あり')
                        name = name.replace('（欠車）','')
                    age.append(int(name.split('/')[1]))
                    gr_class.append(int(name.split('/')[2]))
                    sensyu.append(name.split(' ')[0] + ' ' + name.split(' ')[1])
                pd_racecard['選手名'] = sensyu
                pd_racecard['年齢'] = age
                pd_racecard['期別'] = gr_class
                pd_racecard = pd_racecard.drop(['選手名 府県/年齢/期別'],axis=1)

                pd_racecard = pd_racecard.loc[:,['予 想','着 順', '総 評', '枠 番', '車 番', '選手名','競走得点','年齢','期別','級 班', '脚 質', 'ギヤ 倍数','S', 'B',
                    '逃', '捲', '差', 'マ', '1 着', '2 着', '3 着', '着 外', '勝 率', '2連 対率', '3連 対率'
                        ]]
            except:
                pass

            #pd_racecard.insert(loc = 0,column ='ID',value =all_race_ids['ID'][i])

            #-----------------------ライン構成の読み取り ----------------
            try:
                line_position = soup.find('div',attrs={'class':'line_position_inner'}).text
                p = line_position.replace('\n',"P")
                line_n = ['mmmmmm','mmmmmm','mmmmmm','mmmmmm','mmmmmm','mmmmmm','mmmmmm','mmmmmm','mmmmmm',
                            'mmmmmm','mmmmmm','mmmmmm','mmmmmm','mmmmmm','mmmmmm','mmmmmm','mmmmmm','mmmmmm']
                
                n = 0
                for i in range(len(p)):
                    
                    po_1 = p[i-2]
                    po_2 = p[i-1]

                    if re.findall(r'\d+',p[i]):
                        n += 1
                        line_n[n] = str(p[i])
                        
                        if po_1 == po_2:
                            line_n[n] = str("mmmmmm")
                            n += 1
                            line_n[n] = str(p[i])
                        
                line_n = "".join(line_n) + 'mmmmmm'
            except:
                pass

            #----------------------ライン構成の分析 ------------------
            try:
                make_line = []

                syusso_n = len(pd_racecard)
                for j in range(1,syusso_n+1,1):
                    for k in range(len(line_n)):
                        check_str = line_n[k]
                        if str(j) == check_str :
                            if line_n[k-1]=='m' :
                                if line_n[k+1] == 'm':
                                    make_line.append([j,line_n[k],0]) #単騎
                                else:    
                                    make_line.append([j,line_n[k],1]) #先頭
                            else:    
                                if line_n[k-2] == 'm':
                                    make_line.append([j,line_n[k-1],2]) #番手
                                else:
                                    if line_n[k-3] == 'm':
                                        make_line.append([j,line_n[k-2],3]) #３番手
                                    else:
                                        if line_n[k-4] == 'm':
                                            make_line.append([j,line_n[k-3],4]) #４番手
                                        else:
                                            if line_n[-5] == 'm':
                                                make_line.append([j,line_n[k-4],5])  #５番手
                                                
                line_k = re.findall(r'\d+',line_n)
                kousei = str()
                kousei2 = str()
                for i in range(len(line_k)):
                    kousei += str(len(line_k[i]))
                kousei = sorted(kousei,reverse=True)
                for i in range(len(kousei)):
                    kousei2 += kousei[i]+'-'
                kousei2 = kousei2[:-1]
                
                # ----------------------ライン構成を追加 ----------------------------
                pd_make_line = pd.DataFrame(make_line)

                pd_make_line.columns=['車 番','ライン','番手']
                pd_racecard2 = pd.merge(pd_racecard,pd_make_line,how='inner')

                # ---------------------競走得点順位を追加 -----------------------
                toku_jyun = [i for i in range(1,len(pd_make_line)+1)]
                pd_racecard2 = pd_racecard2.sort_values('競走得点',ascending=False)
                pd_racecard2['得点順位']=toku_jyun
                pd_racecard2 = pd_racecard2.sort_values('車 番')
            except:
                pass

            
            #----------------------re-suinnfome-syonn ---------------------
        
            #----------------------re-suinnfome-syonn ---------------------
            try:
                race_header_span = soup.find('div', attrs={'class': "race_header"}).find('span')
                if race_header_span:
                    race_header = race_header_span.text
                    race_info_header = re.findall(r'\w+', race_header)
                    race_info_day = id_a[2:6] + '-' + race_info_header[2][:2] + '-' + race_info_header[2][3:5]
                else:
                    race_info_header = ['不明'] * 4
                    race_info_day = '不明'

                race_title_span = soup.find('div', attrs={'class': "race_title_header"}).find('span')
                race_title = race_title_span.text if race_title_span else '不明'
            
                race_stadium_span = soup.find('span', attrs={'class': "velodrome"})
                race_stadium = race_stadium_span.text if race_stadium_span else '不明'
            
                race_name_span = soup.find('span', attrs={'class': "race"})
                race_name = "".join(race_name_span.text.split('\u3000')) if race_name_span else '不明'
            
                grade_h1 = soup.find('h1', attrs={'class': "section_title"})
                race_gr = [t for t in race_grs if t in grade_h1.text][0] if grade_h1 else '不明'

                # エラーの原因箇所を修正
                race_start_time = '不明'
                time_dl = soup.find('dl', attrs={'class': "time"})
                dd_elements = time_dl.find_all('dd') if time_dl else []
                if len(dd_elements) > 0:
                    race_start_time = dd_elements[0].text

                # エラーの原因箇所を修正
                race_condition_weather = '不明'
                race_condition_wind = '不明'
                weather_p = soup.find('p', attrs={'class': "weather_info"})
                # weather_pが見つかった場合のみ、中の情報を探しにいく
                if weather_p:
                    race_condition_spans = weather_p.find_all('span') # spanタグをすべて取得
                    # 取得したspanタグが1つ以上あれば、1つ目から天気を取得
                    if len(race_condition_spans) > 0:
                        race_condition_weather = race_condition_spans[0].text[-1]
                    # 取得したspanタグが2つ以上あれば、2つ目から風速を取得
                    if len(race_condition_spans) > 1:
                        race_condition_wind = race_condition_spans[1].text[2:-1]

                info_table[id_a] = {'レースタイトル': race_title, '競輪場': race_stadium, 'レース名': race_name, 'グレード': race_gr,
                                '開始時間': race_start_time, '天気': race_condition_weather, '風速': race_condition_wind,
                                'レース番号': race_info_header[0], '開催日': race_info_day, '開催番号': race_info_header[3], '車立': len(pd_racecard),
                                'ライン数': len(line_k), 'ライン構成': kousei2}

                # ★ここが最重要：race_cardに race_id 列を付ける
                pd_racecard2["race_id"] = str(id_a)

                # （任意）indexにも残すならOK            
                pd_racecard2.index = [id_a] * len(pd_racecard2)
                entry_table[id_a] = pd_racecard2

                # ★払戻も後で使うなら列を付ける（強く推奨）
                pd_harai["race_id"] = str(id_a)
            
                pd_harai.index = [id_a] * len(pd_harai)
                return_table[id_a] = pd_harai
            
            except Exception as e:
                # 修正後もエラーが出る場合は、ここで確認
                print(f"--- 情報取得ブロックで予期せぬエラー ---")
                print(f"レースID: {id_a}")
                print(f"エラー内容: {e}")
                print(f"------------------------------------")
                pass
        
    except IndexError:
        print('中止みたいです')
        print(id_a) 
  
        #---------------------------------------------
    info_table = pd.DataFrame(info_table).T
    entry_table = pd.concat([entry_table[key] for key in entry_table])        
    return_table = pd.concat([return_table[key] for key in return_table])          
            
    return info_table,entry_table,return_table

# main関数
if __name__ == '__main__':
    #race_ids = pd.read_pickle('race_id_202106-202206.pkl')
    race_ids = pd.read_pickle('race_id_202601-202601.pkl')
    race_data = race_data_scrape(race_ids)
    pd.to_pickle(race_data[0],'race_info_202601-202601.pkl')
    pd.to_pickle(race_data[1],'race_card_202601-202601.pkl')
    pd.to_pickle(race_data[2].iloc[:,:11],'race_return_202601-202601.pkl')