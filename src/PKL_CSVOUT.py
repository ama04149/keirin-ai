import pandas as pd

# --- 1. データの読み込みと結合 ---
df_shussou = pd.read_pickle('race_card3_202106-202512.pkl')
df_raceinfo = pd.read_pickle('race_info2_202106-202512.pkl')

# --- 2. CSV形式での出力 ---

# df_shussouのカラム名とデータをCSV出力
df_shussou.to_csv(r'C:\Users\wolfs\Desktop\shussou_output.csv', index=False, encoding='utf-8-sig')

# df_raceinfoのカラム名とデータをCSV出力
df_raceinfo.to_csv(r'C:\Users\wolfs\Desktop\raceinfo_output.csv', index=False, encoding='utf-8-sig')

print("CSVファイルの出力が完了しました。")