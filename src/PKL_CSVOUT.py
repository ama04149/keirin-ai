import pandas as pd
import pickle

# --- 1. データの読み込みと結合 ---
df_shussou = pd.read_pickle('race_card3_202106-202512.pkl')
df_raceinfo = pd.read_pickle('race_info2_202106-202512.pkl')

# --- 2. CSV形式での出力 ---

# df_shussouのカラム名とデータをCSV出力
df_shussou.to_csv(r'C:\Users\wolfs\Desktop\shussou_output.csv', index=False, encoding='utf-8-sig')

# df_raceinfoのカラム名とデータをCSV出力
df_raceinfo.to_csv(r'C:\Users\wolfs\Desktop\raceinfo_output.csv', index=False, encoding='utf-8-sig')



input_file = 'race_info2_202106-202512.pkl'  # 読み込むPKLファイル
#output_file = 'race_info2_girls_202106-202512.pkl' # 出力するPKLファイル
#output_file = 'race_info2_challenge_202106-202512.pkl' # 出力するPKLファイル
#output_file = 'race_info2_Aclass_202106-202512.pkl' # 出力するPKLファイル
output_file = 'race_info2_Sclass_202106-202512.pkl' # 出力するPKLファイル

# 1. PKLファイルを読み込む
df = pd.read_pickle(input_file)

# 2. 条件に合致するレコードを抽出 (例: 'status' が 'active' のものを抽出)
filtered_df = df[df['レースタイトル'].str.startswith('Ｓ級', na=False)]


# 3. 抽出したレコードを新しいPKLファイルに出力する
filtered_df.to_pickle(output_file)

# df_raceinfo_filteredのカラム名とデータをCSV出力
filtered_df.to_csv(r'C:\Users\wolfs\Desktop\raceinfo_filtered_output.csv', index=False, encoding='utf-8-sig')

print("CSVファイルの出力が完了しました。")