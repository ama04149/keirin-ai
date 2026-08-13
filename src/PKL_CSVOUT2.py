import pandas as pd

# --- 1. データの読み込みと結合 ---
df_cumulative_ready = pd.read_pickle('race_card3_cumulative_ready.pkl')

# --- 2. CSV形式での出力 ---

# df_cumulative_readyのカラム名とデータをCSV出力
df_cumulative_ready.to_csv(r'C:\Users\wolfs\Desktop\race_card3_cumulative_ready.pkl.csv', index=False, encoding='utf-8-sig')

print("CSVファイルの出力が完了しました。")