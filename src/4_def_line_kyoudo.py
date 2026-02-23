import pandas as pd
import re
from time import sleep
from bs4 import BeautifulSoup
import requests
from tqdm import tqdm
from datetime import datetime, timedelta
import calendar
import sys

def line_kyoudo(race_card):
    card = race_card.copy()
    id_lists = card.index.unique()
    dic = {}
    error_id = []
    
    for id in tqdm(id_lists):
        df = card[card.index == id]
        df1 = df[['車 番', 'ライン', '番手', '得点順位']].copy()
        df2 = df[['車 番', 'B', 'ライン', '番手', '得点順位']].copy()
        df3 = df[['車 番', '捲', 'ライン', '番手', '得点順位']].copy()

        # 番手が0のものを1に置換
        df1['番手'].replace(0, 1, inplace=True)
        df2['番手'].replace(0, 1, inplace=True)
        df3['番手'].replace(0, 1, inplace=True)

        df1.sort_values(['番手', '得点順位'], inplace=True)
        df2.sort_values(['番手', 'B', '得点順位'], ascending=[True, False, True], inplace=True)
        df3.sort_values(['番手', '捲', '得点順位'], ascending=[True, False, True], inplace=True)
        
        l = len(df1[df1['番手'] == 1])
        l2 = len(df1)
        
        line_list = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I']
        line_list2 = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i']
        line_list3 = ['AA', 'BB', 'CC', 'DD', 'EE', 'FF', 'GG', 'HH', 'II']

        # forループの前にこのチェックを追加
        #if len(df1) != len(line_list):
        #    print("--- データ不整合を検知 ---")
        #    print(f"DFの長さ: {len(df1)}, line_listの長さ: {len(line_list)}")
        #    print("▼該当レースのデータフレーム▼")
        #    print(df1)
        #    print("--------------------------")

        # 安全な範囲でループするために、短い方のリストの長さを採用
        loop_range = min(len(df1), len(line_list))
        loop_range2 = min(len(df2), len(line_list2))
        loop_range3 = min(len(df3), len(line_list3))
        line_st = {df1['ライン'].iloc[i]: line_list[i] for i in range(loop_range)}
        line_st2 = {df2['ライン'].iloc[i]: line_list2[i] for i in range(loop_range2)}
        line_st3 = {df3['ライン'].iloc[i]: line_list3[i] for i in range(loop_range3)}

        #line_st = {df1['ライン'].iloc[i]: line_list[i] for i in range(l)}
        #line_st2 = {df2['ライン'].iloc[i]: line_list2[i] for i in range(l)}
        #line_st3 = {df3['ライン'].iloc[i]: line_list3[i] for i in range(l)}

        try:
            line_no = [line_st.get(df1['ライン'].iloc[k], '') + str(df1['番手'].iloc[k]) for k in range(l2)]
            line_no2 = [line_st2.get(df2['ライン'].iloc[k], '') + str(df2['番手'].iloc[k]) for k in range(l2)]
            line_no3 = [line_st3.get(df3['ライン'].iloc[k], '') + str(df3['番手'].iloc[k]) for k in range(l2)]
        except IndexError:
            error_id.append(id)
            continue
        
        try:
            df1['強度'] = line_no
            df1.sort_values(['車 番'], inplace=True)
            df1.drop(['ライン', '番手', '得点順位'], axis=1, inplace=True)
            
            df2['強度２'] = line_no2
            df2.sort_values(['車 番'], inplace=True)
            df2.drop(['B', 'ライン', '番手', '得点順位'], axis=1, inplace=True)

            df3['強度３'] = line_no3
            df3.sort_values(['車 番'], inplace=True)
            df3.drop(['捲', 'ライン', '番手', '得点順位'], axis=1, inplace=True)
            
            df = df.merge(df1, on='車 番').merge(df2, on='車 番').merge(df3, on='車 番')
            df.index = [id] * len(df)
            dic[id] = df
        except Exception as e:
            error_id.append(id)
            continue
 
    dic = pd.concat([dic[key] for key in dic])
    return dic

# main関数
if __name__ == '__main__':
    r_syu= pd.read_pickle('race_card2_202601-202601.pkl')
    r_syu_s = line_kyoudo(r_syu)
    #r_syu2= pd.read_pickle('race_card2_20250712.pkl')
    #r_syu_s2 = line_kyoudo(r_syu2)


    pd.to_pickle(r_syu_s,'race_card3_202601-202601.pkl')
    #pd.to_pickle(r_syu_s2,'today_race_card3.pkl')