import pandas as pd
import re
from time import sleep
from bs4 import BeautifulSoup
import requests
from tqdm import tqdm
from datetime import datetime, timedelta
import calendar
import sys

def back_sabun(r_card):
    card = r_card.copy()
    race_card = {}
    
    s_lists = ['競走得点','B', '逃','捲','差','マ']
    i_lists = card.index.unique()
    for i_list in tqdm(i_lists):
        df = card[card.index == i_list]
        
        for s_list in s_lists:
                df_2  = df.sort_values(s_list,ascending=False)

                # ベクトル化した操作を使用
                max_val = df_2[s_list].max()
                df_2[s_list+'_sa'] = max_val - df_2[s_list]

#                if (s_list == 'B' or s_list == '逃'):                
#                    df_2[s_list +'_sa2'] = df_2[s_list].iloc[0] - df_2[s_list].iloc[1]
#                    df_2[s_list +'_suu'] = (df_2[s_list] >=10).sum()
#                df_2 = df_2.sort_values('車 番')
                if (s_list == 'B' or s_list == '逃'):
                    # 2行未満（欠場/スクレイプ欠け等）でも落ちないようにする
                    if len(df_2) >= 2:
                        df_2[s_list + '_sa2'] = df_2[s_list].iloc[0] - df_2[s_list].iloc[1]
                    elif len(df_2) == 1:
                        df_2[s_list + '_sa2'] = 0  # 2番手がいないので差は0扱い（np.nanでも可）
                    else:
                        df_2[s_list + '_sa2'] = 0  # 空のとき（ほぼ無いはず）

                    df_2[s_list + '_suu'] = (df_2[s_list] >= 10).sum()

                 # 列名ゆれに対応（車 番 / 車_番）
                sort_col = '車 番' if '車 番' in df_2.columns else ('車_番' if '車_番' in df_2.columns else None)
                if sort_col is not None:
                    df_2 = df_2.sort_values(sort_col)

                df = df_2
                race_card[i_list] = df
                              
    race_card = pd.concat(race_card.values())
    return race_card

def bankcho(r_info):
    df = r_info.copy()
    list_1 = ['前橋','松戸','小田原','伊東','富山','奈良','防府']
    list_2 = ['大宮','宇都宮','高知','熊本']
    try:    
        for id in tqdm(df.index):
            jo = df.loc[id,'競輪場'][:-2]
            if jo in list_1:
                df.loc[id,'1周'] = '333'
            elif jo in list_2:
                df.loc[id,'1周'] = '500'
            else:
                df.loc[id,'1周'] = '400'
    except:
        print(id)
        
    return df

# main関数
if __name__ == '__main__':
    r_syu= pd.read_pickle('race_card_202601-202601.pkl')
    r_syu_s = back_sabun(r_syu)

    r_inf = pd.read_pickle('race_info_202601-202601.pkl')
    r_inf_b = bankcho(r_inf)

    pd.to_pickle(r_syu_s,'race_card2_202601-202601.pkl')
    pd.to_pickle(r_inf_b,'race_info2_202601-202601.pkl')