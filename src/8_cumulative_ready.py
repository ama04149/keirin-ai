import pandas as pd

# 1. データの読み込み
df = pd.read_pickle('race_card3_202106-202606.pkl')

# 2. 型変換とクリーニング
df['着 順'] = pd.to_numeric(df['着 順'], errors='coerce')

# 3. 1着・2着・3着の判定フラグ（計算用）
df['is_1st'] = (df['着 順'] == 1).astype(int)
df['is_2nd_up'] = (df['着 順'] <= 2).astype(int)
df['is_3rd_up'] = (df['着 順'] <= 3).astype(int)

print("累積計算を開始します...")

# 4. groupby と transform / cumsum を組み合わせたベクトル演算 (apply非使用)
# 各選手の通算出走数（行インデックス）: 0, 1, 2, ...
df['累計出走数'] = df.groupby('選手名').cumcount().astype(float)

# 0割りを回避するため、0をNaNに置換
denom = df['累計出走数'].replace(0, pd.NA)

# shift(1) で「今回のレース」を含めずに累積
df['累計勝率'] = (df.groupby('選手名')['is_1st'].cumsum().shift(1) / denom).fillna(0.0)
df['累計2連対率'] = (df.groupby('選手名')['is_2nd_up'].cumsum().shift(1) / denom).fillna(0.0)
df['累計3連対率'] = (df.groupby('選手名')['is_3rd_up'].cumsum().shift(1) / denom).fillna(0.0)

# 選手ごとの最初の行（shiftによって前選手のデータが入ってしまう箇所）を 0.0 に補正
first_race_mask = (df['累計出走数'] == 0)
df.loc[first_race_mask, ['累計勝率', '累計2連対率', '累計3連対率']] = 0.0

# 5. 判定用フラグを削除
df = df.drop(columns=['is_1st', 'is_2nd_up', 'is_3rd_up'])

# 6. 保存
df.to_pickle('race_card3_cumulative_ready.pkl')
print("完了しました。 'race_card3_cumulative_ready.pkl' として保存されました。")