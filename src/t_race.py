import pandas as pd
from pycaret.classification import load_model, predict_model

# --- 1. 学習済みモデルの読み込み ---
saved_model_top3 = load_model('keirin_prediction_model_combined') # 3着以内モデル
saved_model_1st = load_model('keirin_model_1st_place')      # 1着モデル (追加)

# --- 2. 新しいレースデータの準備 ---
#【重要】この部分は、ご自身で当日の出走表データを取得し、
#         モデル学習時と"全く同じ形式"に加工する処理を記述する必要があります。

# (例) 当日の出走表データとレース情報データを読み込む
df_new_shussou = pd.read_pickle('today_race_card3.pkl')
df_new_raceinfo = pd.read_pickle('today_race_info2.pkl')

#【加工処理の例：学習時と全く同じ処理を行う】
df_new_shussou.reset_index(inplace=True)
df_new_raceinfo.reset_index(inplace=True)
new_data = pd.merge(df_new_shussou, df_new_raceinfo, on='index', how='left')

new_data.columns = new_data.columns.str.strip()
new_data.columns = new_data.columns.str.replace(' ', '_').str.replace('　', '_')

# 2. カテゴリとして扱う列を定義 (学習時と完全に一致させる)
categorical_features = ['予想','枠_番', '車_番', '級_班', '脚_質', '期別', '競輪場', 'グレード', '天気', 'レース番号', 'レースタイトル', '開催番号', '強度', '強度２', '強度３', 'ライン構成', '1周']

# 3. 数値変換から除外する列を定義
exclude_from_numeric_conversion = categorical_features + ['予_想', '総_評', '選手名', 'レース名', '開催日', '開始時間'] 

# 4. 除外リスト以外の全ての列を一括で数値化
for col in new_data.columns:
    if col not in exclude_from_numeric_conversion:
        # 数値に変換し、'不明'などの変換できないものはNaN（欠損値）にする
        new_data[col] = pd.to_numeric(new_data[col], errors='coerce')

# 表示には残したいが、初期段階で不要な列を削除
initial_drops = ['index', '総_評', '着_順', 'レース名']

# '予 想', 
new_data = new_data.drop(columns=initial_drops, errors='ignore')
#, 'レースタイトル', '開催日', 'ライン構成'

# データ型の変換（学習時と統一）
#new_data['ギヤ_倍数'] = pd.to_numeric(new_data['ギヤ_倍数'], errors='coerce')

# --- ここからが予測データの最終準備 ---
# 表示には使うが「予測」には使わない列をリストにまとめる
pred_only_drops = ['選手名', '開催日']#, 'レースタイトル'

# new_dataから上記リストの列を削除して、予測専用のデータを作成
new_data_for_pred = new_data.drop(columns=pred_only_drops, errors='ignore')

# --- ここからが最終修正 ---
# 保存した正しい列順序を読み込む
model_columns = pd.read_pickle('model_columns.pkl')

# 予測用データの列順序を、学習時と完全に一致させる
new_data_for_pred = new_data_for_pred[model_columns]
# --- ここまで ---

# --- 3. 予測の実行 ---
print('【予測時の最終列】:', new_data_for_pred.columns)
# 【変更点①】それぞれのモデルで予測を実行
# 3着以内モデルで予測
predictions_top3 = predict_model(saved_model_top3, data=new_data_for_pred)
# 1着モデルで予測
predictions_1st = predict_model(saved_model_1st, data=new_data_for_pred)

# 【変更点②】列名を変更して結合の準備
# 3着以内モデルのスコアを 'prediction_score_top3' に変更
predictions_top3.rename(columns={'prediction_score': 'prediction_score_top3'}, inplace=True)
# 1着モデルのスコアを 'prediction_score_1st' に変更
predictions_1st.rename(columns={'prediction_score': 'prediction_score_1st'}, inplace=True)

# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
# ★  最終的な修正：スコアの意味を逆転させる  ★
# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
# 予測スコアが「3着以内に入らない確率」を示しているため、
# 1から引くことで「3着以内に入る確率」に変換する
# 1 - score の補正 (3着以内モデルのみ)
predictions_top3['prediction_score_top3'] = 1 - predictions_top3['prediction_score_top3']
predictions_1st['prediction_score_1st'] = 1 - predictions_1st['prediction_score_1st']

# 【変更点③】元のデータに両方の予測スコアを結合
# new_dataと3着スコアを結合
result_df = pd.concat([
    new_data.reset_index(drop=True),
    predictions_top3[['prediction_score_top3']].reset_index(drop=True)
], axis=1)
# さらに1着スコアを結合
result_df = pd.concat([
    result_df,
    predictions_1st[['prediction_score_1st']].reset_index(drop=True)
], axis=1)

# 【変更点④】表示する列とソート順を変更
display_columns = ['競輪場', 'レース番号', '開始時間', '開催番号', 'レースタイトル', '車_番', '選手名', '競走得点', 'prediction_score_top3', 'prediction_score_1st']

# 3着以内スコアでソート
sorted_result = result_df[display_columns].sort_values(
    by=['開始時間', '競輪場', 'レース番号', 'prediction_score_1st'], # 2026/1/1修正
    ascending=[True, True, True, False]
)

# 保存
output_filename = 'keirin_prediction_result_combined.csv'
sorted_result.to_csv(output_filename, encoding='utf-8-sig', index=False)
print(f"\n予測結果が'{output_filename}'として保存されました。")

'''
# 2. 確率(prediction_score)を元に、しきい値0.4を適用した新しい列を作成します
# 確率が0.4以上なら1、そうでなければ0をセット
predictions['predicted_label_0.4'] = (predictions['prediction_score'] >= 0.4).astype(int)

# デフォルトのprediction_labelも再計算する（任意）
predictions['prediction_label'] = (predictions['prediction_score'] >= 0.5).astype(int)

# 行ズレを防ぐためのインデックスリセット
new_data.reset_index(drop=True, inplace=True)
predictions.reset_index(drop=True, inplace=True)

# 元のデータ(new_data)と予測結果(predictions)を結合
result_df = pd.concat([new_data, predictions[['predicted_label_0.4','prediction_label', 'prediction_score']]], axis=1)

print("--- 予測結果 ---")
# 3着以内に入る確率が高い順に並べ替えて表示
#print(result_df[['車 番', '選手名', '競走得点', 'prediction_score']].sort_values(by='prediction_score', ascending=False))
#print(result_df[['車 番', '競走得点', 'prediction_score']].sort_values(by='prediction_score', ascending=False))

# 表示したい列に '競輪場' と 'レース番号'、'選手名' を追加
display_columns = ['競輪場', 'レース番号','レースタイトル', '開始時間', '車_番', '選手名', '競走得点', 'prediction_score','predicted_label_0.4','prediction_label']

# 競輪場ごと、レース番号ごとに、確率が高い順で並べ替える
sorted_result = result_df[display_columns].sort_values(
    by=['開始時間', '競輪場', 'レース番号', 'prediction_score'], 
    ascending=[True,True, True, False]
)

print(sorted_result)

# ファイル名を指定してCSVファイルとして保存
# encoding='utf-8-sig' を指定すると、Excelで開いた時の文字化けを防げます。
# index=False を指定すると、行番号（インデックス）がファイルに保存されなくなります。
output_filename = 'keirin_prediction_result.csv'
sorted_result.to_csv(output_filename, encoding='utf-8-sig', index=False)

print(f"\n予測結果が'{output_filename}'として保存されました。")
'''