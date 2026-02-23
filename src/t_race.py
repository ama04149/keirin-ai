import pandas as pd
from pycaret.classification import load_model, predict_model
import sys
import io

# 出力をUTF-8に強制（Windows環境で有効な場合が多い）
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


# --- 1. 学習済みモデルの読み込み ---
saved_model_top3 = load_model('keirin_prediction_model_combined') 
saved_model_1st = load_model('keirin_model_1st_place') 

# --- 2. 新しいレースデータの準備 ---
df_new_shussou = pd.read_pickle('today_race_card3.pkl')
df_new_shussou["race_id"] = df_new_shussou["race_id"].astype("string")

df_new_raceinfo = pd.read_pickle('today_race_info2.pkl')
df_new_raceinfo["race_id"] = df_new_raceinfo["race_id"].astype("string")

# 加工処理
#df_new_shussou.reset_index(inplace=True)
#df_new_raceinfo.reset_index(inplace=True)
#new_data = pd.merge(df_new_shussou, df_new_raceinfo, on='index', how='left')

new_data = pd.merge(df_new_shussou, df_new_raceinfo, on="race_id", how="left")

# 重複列を落とす（左側を優先）
new_data = new_data.loc[:, ~new_data.columns.duplicated()]
new_data.columns = new_data.columns.str.strip()
new_data.columns = new_data.columns.str.replace(' ', '_').str.replace('　', '_')

# カテゴリ列・数値化の定義
categorical_features = ['予_想','枠_番', '車_番', '級_班', '脚_質', '期別', '競輪場', 'グレード', '天気', 'レース番号', 'レースタイトル', '開催番号', '強度', '強度２', '強度３', 'ライン構成', '1周']
exclude_from_numeric_conversion = categorical_features + ['予_想', '総_評', '選手名', 'レース名', '開催日', '開始時間'] 

# ★★★ ここで「累計成績」をマージする ★★★
player_master = pd.read_pickle('player_cumulative_master.pkl')
new_data = pd.merge(new_data, player_master, on='選手名', how='left')

# デバッグ
print("=== DEBUG after merge (new_data) ===")
print("new_data.columns has key fields:",
      [c for c in ["race_id","競輪場","レース番号","開始時間","開催番号","レースタイトル","車_番","車_番"] if c in new_data.columns])

print("race_id head:", new_data["race_id"].head().tolist())

for c in ["race_id","競輪場","レース番号","開始時間","開催番号","レースタイトル"]:
    if c in new_data.columns:
        print(c, "NA=", int(new_data[c].isna().sum()), "sample=", new_data[c].head().tolist())


# 初出場の選手などで累計データがない場合は 0 で埋める
cumulative_cols = ['累計勝率', '累計2連対率', '累計3連対率', '累計出走数']
new_data[cumulative_cols] = new_data[cumulative_cols].fillna(0)

for col in new_data.columns:
    if col not in exclude_from_numeric_conversion:
        new_data[col] = pd.to_numeric(new_data[col], errors='coerce')

# 不要な列を削除
initial_drops = ['index', '総_評', '着_順', 'レース名']
new_data = new_data.drop(columns=initial_drops, errors='ignore')

# 予測専用データの作成
pred_only_drops = ['予_想', '開催日', '選手名',]
new_data_for_pred = new_data.drop(columns=pred_only_drops, errors='ignore')

# 列順序の統一
#model_columns = pd.read_pickle('model_columns.pkl')
model_columns = pd.read_pickle('model_columns_1st.pkl')
new_data_for_pred = new_data_for_pred[model_columns]

# --- 3. 予測の実行 ---

# インデックスをリセットしてズレを完全に防止
new_data_for_pred = new_data_for_pred.reset_index(drop=True)
df_base = new_data.reset_index(drop=True)

# 予測を実行
preds_3 = predict_model(saved_model_top3, data=new_data_for_pred, raw_score=True)
preds_1 = predict_model(saved_model_1st, data=new_data_for_pred, raw_score=True)

# インデックスを再リセットして物理的な並び順を保証
preds_3 = preds_3.reset_index(drop=True)
preds_1 = preds_1.reset_index(drop=True)

# スコアの代入（.valuesを使って物理的な順序で結合）
# 「3着以内に入らない確率」を「入る確率」に変換（1 - score）
#df_base['prediction_score_top3'] = 1 - preds_3['prediction_score'].values
#df_base['prediction_score_1st'] = 1 - preds_1['prediction_score'].values

df_base['prediction_score_top3'] = preds_3['prediction_score_1'].values
df_base['prediction_score_1st']  = preds_1['prediction_score_1'].values

# --- 4. 表示と保存 ---
display_columns = [
    "race_id",          # 主キー（レース単位ID）
    "競輪場", "レース番号", "開始時間", "開催番号", "レースタイトル",
    "車_番", "選手名", "競走得点", "S", "B",
    "prediction_score_top3", "prediction_score_1st"
] # 2026/02/01 'race_id'を追加

# ソート：開始時間 > 競輪場 > レース番号 > 1着確率が高い順
sorted_result = df_base[display_columns].sort_values(
    by=['開始時間', '競輪場', 'レース番号', 'prediction_score_1st'],
    ascending=[True, True, True, False]
)

# デバッグ
print("=== DEBUG before CSV (sorted_result) ===")
print("sorted_result race_id head:", sorted_result["race_id"].head().tolist())
print("sorted_result empty counts:",
      {c: int(sorted_result[c].isna().sum()) for c in ["race_id_kdreams","競輪場","レース番号","開始時間","開催番号","レースタイトル"] if c in sorted_result.columns})
print(sorted_result.head(5))

df_base["race_id"] = df_base["race_id"].astype("string")

# 保存
output_filename = 'keirin_prediction_result_combined.csv'
sorted_result.to_csv(output_filename, encoding='utf-8-sig', index=False)

print(f"DEBUG: 最終行数 = {len(sorted_result)}")
print(f"予測結果が'{output_filename}'として保存されました。")