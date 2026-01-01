import pandas as pd
import numpy as np

# .pklファイルを読み込む
df = pd.read_pickle('your_data.pkl')
target_col = 'col_C' # 対象の列名

# --- ステップ1: NaNを削除 ---
df_cleaned = df.dropna(subset=[target_col])

# --- ステップ2: 空文字列やスペースのみの文字列を削除 ---
#   対象列が文字列型(object)であることを確認してから実行するとより安全です
if df_cleaned[target_col].dtype == 'object':
    df_cleaned = df_cleaned[df_cleaned[target_col].str.strip() != '']


print("--- 処理後のデータ ---")
print(df_cleaned.head())

# 処理後のデータを保存
df_cleaned.to_pickle('cleaned_data.pkl')