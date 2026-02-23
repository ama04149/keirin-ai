import pandas as pd

# 累積計算済みの全データを読み込む
df_all = pd.read_pickle('race_card3_cumulative_ready.pkl')

# 各選手の「最新（最後）の1行」だけを抽出してマスターにする
# ※日付がないため、データの末尾が最新とみなします
player_master = df_all.groupby('選手名').tail(1).copy()

# 必要な列だけを保持（選手名と累計項目）
cumulative_features = ['選手名', '累計勝率', '累計2連対率', '累計3連対率', '累計出走数']
player_master = player_master[cumulative_features]

# 保存
player_master.to_pickle('player_cumulative_master.pkl')
print("最新の選手マスターを作成しました。")