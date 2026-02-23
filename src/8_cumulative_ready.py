import pandas as pd

# 1. データの読み込み
df = pd.read_pickle('race_card3_202106-202601.pkl')

# 2. 型変換とクリーニング
# 「着 順」列を数値に変換。数値にできないものは NaN になります。
df['着 順'] = pd.to_numeric(df['着 順'], errors='coerce')

# 3. 1着・2着・3着の判定フラグ（計算用）
# NaN は比較の結果 False になるので、欠場などは自動的にカウントされません。
df['is_1st'] = (df['着 順'] == 1).astype(int)
df['is_2nd_up'] = (df['着 順'] <= 2).astype(int)
df['is_3rd_up'] = (df['着 順'] <= 3).astype(int)

# 4. 選手ごとに「その行より前」のデータを集計する
print("累積計算を開始します...")

def calc_stats_no_date(group):
    # 各行（レース）時点での「その選手にとっての通算出走数」
    # ※出走数としてカウントしたくない行（欠場など）がある場合は
    #   group['着 順'].notna().cumsum().shift(1) などにする必要がありますが、
    #   基本は行数でカウントして問題ありません。
    total_races = pd.Series(range(len(group)), index=group.index).astype(float)
    
    # shift(1) で「今回の結果」を含まないように累積
    group['累計勝率'] = (group['is_1st'].cumsum().shift(1) / total_races).fillna(0)
    group['累計2連対率'] = (group['is_2nd_up'].cumsum().shift(1) / total_races).fillna(0)
    group['累計3連対率'] = (group['is_3rd_up'].cumsum().shift(1) / total_races).fillna(0)
    group['累計出走数'] = total_races
    return group

# 選手名でまとめて計算
df = df.groupby('選手名', group_keys=False).apply(calc_stats_no_date)

# 5. 判定用フラグを削除
df = df.drop(columns=['is_1st', 'is_2nd_up', 'is_3rd_up'])

# 6. 保存
df.to_pickle('race_card3_cumulative_ready.pkl')
print("完了しました。 'race_card3_cumulative_ready.pkl' として保存されました。")