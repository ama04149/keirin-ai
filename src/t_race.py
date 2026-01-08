import pandas as pd
from pycaret.classification import load_model, predict_model

# --- 1. 学習済みモデルの読み込み ---
saved_model_top3 = load_model('keirin_prediction_model_combined') 
saved_model_1st = load_model('keirin_model_1st_place') 

# --- 2. 新しいレースデータの準備 ---
df_new_shussou = pd.read_pickle('today_race_card3.pkl')
df_new_raceinfo = pd.read_pickle('today_race_info2.pkl')

# 加工処理
df_new_shussou.reset_index(inplace=True)
df_new_raceinfo.reset_index(inplace=True)
new_data = pd.merge(df_new_shussou, df_new_raceinfo, on='index', how='left')

new_data.columns = new_data.columns.str.strip()
new_data.columns = new_data.columns.str.replace(' ', '_').str.replace('　', '_')

# カテゴリ列・数値化の定義
categorical_features = ['予_想','枠_番', '車_番', '級_班', '脚_質', '期別', '競輪場', 'グレード', '天気', 'レース番号', 'レースタイトル', '開催番号', '強度', '強度２', '強度３', 'ライン構成', '1周']
exclude_from_numeric_conversion = categorical_features + ['予_想', '総_評', '選手名', 'レース名', '開催日', '開始時間'] 

for col in new_data.columns:
    if col not in exclude_from_numeric_conversion:
        new_data[col] = pd.to_numeric(new_data[col], errors='coerce')

# 不要な列を削除
initial_drops = ['index', '総_評', '着_順', 'レース名']
new_data = new_data.drop(columns=initial_drops, errors='ignore')

# 予測専用データの作成
pred_only_drops = ['予_想', '開催日'] # '選手名',2026/01/01修正
new_data_for_pred = new_data.drop(columns=pred_only_drops, errors='ignore')

# 列順序の統一
model_columns = pd.read_pickle('model_columns.pkl')
new_data_for_pred = new_data_for_pred[model_columns]

# --- 3. 予測の実行 ---

# インデックスをリセットしてズレを完全に防止
new_data_for_pred = new_data_for_pred.reset_index(drop=True)
df_base = new_data.reset_index(drop=True)

# 予測を実行
preds_3 = predict_model(saved_model_top3, data=new_data_for_pred)
preds_1 = predict_model(saved_model_1st, data=new_data_for_pred)

# インデックスを再リセットして物理的な並び順を保証
preds_3 = preds_3.reset_index(drop=True)
preds_1 = preds_1.reset_index(drop=True)

# スコアの代入（.valuesを使って物理的な順序で結合）
# 「3着以内に入らない確率」を「入る確率」に変換（1 - score）
df_base['prediction_score_top3'] = 1 - preds_3['prediction_score'].values
df_base['prediction_score_1st'] = 1 - preds_1['prediction_score'].values

# --- 4. 表示と保存 ---
display_columns = [
    '競輪場', 'レース番号', '開始時間', '開催番号', 'レースタイトル', 
    '車_番', '選手名', '競走得点', 'prediction_score_top3', 'prediction_score_1st'
]

# ソート：開始時間 > 競輪場 > レース番号 > 1着確率が高い順
sorted_result = df_base[display_columns].sort_values(
    by=['開始時間', '競輪場', 'レース番号', 'prediction_score_1st'],
    ascending=[True, True, True, False]
)

# 保存
output_filename = 'keirin_prediction_result_combined.csv'
sorted_result.to_csv(output_filename, encoding='utf-8-sig', index=False)

print(f"DEBUG: 最終行数 = {len(sorted_result)}")
print(f"予測結果が'{output_filename}'として保存されました。")