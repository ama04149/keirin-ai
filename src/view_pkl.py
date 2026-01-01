import pandas as pd

# ここに見たいファイル名を書く
file_path = 'race_return_202106-202509.pkl'

# pklファイルを読み込む
data = pd.read_pickle(file_path)

# ターミナルに内容を出力する
print(data)