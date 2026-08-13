import pandas as pd

# 1. 一度作成した CSV を読み込み
print("CSVファイルを読み込んでいます...")
df = pd.read_csv('race_card3_202106-202606.csv', low_memory=False)

# 2. 現在の .venv (PyCaret) 環境と互換性のある pickle として保存
# 元のファイル名を上書き保存するか、別名保存します
output_pkl = 'race_card3_202106-202606.pkl'

df.to_pickle(output_pkl)
print(f"完了しました！ {output_pkl} を作成しました。")