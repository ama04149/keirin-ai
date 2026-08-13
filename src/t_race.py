import pandas as pd
from pycaret.classification import load_model, predict_model
import sys
import io
import os
import numpy as np

# 出力をUTF-8に強制
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ★★★ 新・運用ロジック判定関数 ★★★
def judge_operation_logic(row):
    """
    3条件の多数決（2:1 / 1:2 のみ購入、3:0 / 0:3 の満場一致は見送り）
    """
    try:
        ct_val = float(row['CT値']) if pd.notna(row['CT値']) else 0.0
        c_rate = float(row['C率']) if pd.notna(row['C率']) and row['C率'] != '' else 0.0
        d_rate = float(row['D率']) if pd.notna(row['D率']) and row['D率'] != '' else 0.0
    except (ValueError, TypeError):
        ct_val, c_rate, d_rate = 0.0, 0.0, 0.0

    rule1 = ct_val >= 0.10
    rule2 = (c_rate - d_rate) >= 0.04
    rule3 = str(row['レース区分']) in ['チ', 'Ｓ']

    ce_votes = int(rule1) + int(rule2) + int(rule3)

    if ce_votes in [0, 3]:
        return '見送り'
    elif ce_votes == 2:
        return 'A-B-C-E'
    elif ce_votes == 1:
        return 'A-B-D-E'
    return '見送り'


# --- 1. 学習済みモデルの読み込み ---
print("各クラスの学習済みモデルを読み込んでいます...")
models_top3 = {}
for k, m_name in [('girls', 'keirin_model_3rd_girls'), ('challenge', 'keirin_model_3rd_challenge'), ('a_class', 'keirin_model_3rd_a_class'), ('s_class', 'keirin_model_3rd_s_class')]:
    try:
        models_top3[k] = load_model(m_name)
        print(f"  [成功] 3着以内モデルを読み込みました: {m_name}")
    except Exception as e:
        print(f"  [⚠️失敗] 3着以内モデルの読み込みに失敗しました ({m_name}): {e}")
        models_top3[k] = None

try:
    saved_model_1st = load_model('keirin_model_1st_place_challenge') 
    print("  [成功] 1着モデルを読み込みました: keirin_model_1st_place_challenge")
except Exception as e:
    print(f"  [⚠️失敗] 1着モデルの読み込みに失敗しました: {e}")
    saved_model_1st = None


# --- 2. 新しいレースデータの準備 ---
df_new_shussou = pd.read_pickle('today_race_card3.pkl')
df_new_shussou["race_id"] = df_new_shussou["race_id"].astype("string")

df_new_raceinfo = pd.read_pickle('today_race_info2.pkl')
df_new_raceinfo["race_id"] = df_new_raceinfo["race_id"].astype("string")

# 古い集計列・確率列を一括削除して初期化
init_cols = ['A率', 'B率', 'C率', 'D率', 'E率', 'F率', 'G率', 'H率', 'I率', 'CT値', 'スコア', 'prediction_score_top3', 'prediction_score_1st', '発走時']
for old_col in init_cols:
    if old_col in df_new_shussou.columns:
        df_new_shussou = df_new_shussou.drop(columns=[old_col])
    if old_col in df_new_raceinfo.columns:
        df_new_raceinfo = df_new_raceinfo.drop(columns=[old_col])

# データの結合
df_base = pd.merge(df_new_shussou, df_new_raceinfo, on='race_id', how='left')
print(f"本日のデータ結合後のShape: {df_base.shape}")

# 「開始時間」から「時(Hour)」を抽出して数値化する
df_base['発走時'] = df_base['開始時間'].apply(lambda x: int(str(x).split(':')[0]) if pd.notna(x) and ':' in str(x) else 0)

# 列名のクリーニング
df_base.columns = df_base.columns.str.strip().str.replace(' ', '_').str.replace(' ', '_')

categorical_features = ['枠_番', '車_番', '級_班', '脚_質', '期別', '競輪場', 'グレード', '天気', 'レース番号','レースタイトル', '開催番号', '強度', '強度２', '強度３', 'ライン構成', '1周']
cumulative_features = ['累計勝率', '累計2連対率', '累計3連対率', '累計出走数']
exclude_from_numeric_conversion = categorical_features + ['index', '総_評', 'レース名', '開催日', '開始時間', '予_想', '選手名']

for col in df_base.columns:
    if col not in exclude_from_numeric_conversion:
        df_base[col] = pd.to_numeric(df_base[col], errors='coerce')

numeric_cols = df_base.select_dtypes(include=['number']).columns
df_base[numeric_cols] = df_base[numeric_cols].fillna(0)

object_cols = df_base.select_dtypes(include=['object']).columns
df_base[object_cols] = df_base[object_cols].fillna('unknown')

print(f"本番データのクレンジングが完了しました（「発走時」列を追加）。Shape: {df_base.shape}")


# --- PyCaretの学習時特徴量と完全一致させる厳密関数 ---
def align_features_strictly(df, model):
    df_clean = df.copy()
    if model is None:
        return df_clean
    try:
        if hasattr(model, 'feature_names_in_'):
            required_features = list(model.feature_names_in_)
        else:
            required_features = list(model.steps[0][1].feature_names_in_)
    except:
        required_features = [c for c in df_clean.columns if df_clean[c].dtype in [np.int64, np.float64, int, float]]

    for col in required_features:
        if col not in df_clean.columns:
            df_clean[col] = 0.0
        df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0.0).astype(float)
            
    return df_clean[required_features].reset_index(drop=True)


# --- 3. クラス判定関数 ---
def detect_race_class(row):
    kyu_han = str(row['級_班']).strip().upper()
    race_title = str(row['レースタイトル']) if 'レースタイトル' in row else ''
    
    if 'L' in kyu_han or 'ガールズ' in race_title:
        return 'girls'
    elif 'チャレンジ' in race_title or 'チ' in race_title or 'A3' in kyu_han:
        return 'challenge'
    elif 'A' in kyu_han:
        return 'a_class'
    elif 'S' in kyu_han:
        return 's_class'
    else:
        return 'other'

df_base['race_class'] = df_base.apply(detect_race_class, axis=1)


# --- 4. クラス別モデルによる3着以内スコア予測 ---
print("\n===== クラス別予測のデータ分配を完全に追跡します =====")
print("【集計前チェック】df_base 内の race_class の内訳:")
print(df_base['race_class'].value_counts())
print("-" * 50)

predicted_chunks = []

for r_class, model in models_top3.items():
    df_chunk = df_base[df_base['race_class'] == r_class].copy()
    print(f"▶ クラス [{r_class}] の処理を開始します。対象行数: {len(df_chunk)}")
    
    if df_chunk.empty:
        print(f"  -> データが0行のため、[{r_class}] の予測処理をスキップします。")
        continue
    
    if model is not None:
        try:
            df_chunk_input = align_features_strictly(df_chunk, model)
            preds_chunk = predict_model(model, data=df_chunk_input, verbose=False)
            score_col = 'prediction_score' if 'prediction_score' in preds_chunk.columns else preds_chunk.columns[-1]
            df_chunk['prediction_score_top3'] = preds_chunk[score_col].values
            print(f"  [成功] 予測完了。スコア分布 -> MAX: {df_chunk['prediction_score_top3'].max():.4f} / MIN: {df_chunk['prediction_score_top3'].min():.4f} / AVG: {df_chunk['prediction_score_top3'].mean():.4f}")
        except Exception as e:
            print(f"  [⚠️エラー] 予測中にエラーが発生したため、0.5を適用します: {e}")
            df_chunk['prediction_score_top3'] = 0.5
    else:
        print(f"  [⚠️警告] モデルがNoneのため、一律0.5を割り当てます。")
        df_chunk['prediction_score_top3'] = 0.5
        
    predicted_chunks.append(df_chunk)

df_other = df_base[~df_base['race_class'].isin(models_top3.keys())].copy()
print(f"\n▶ クラス [other (その他)] の処理を開始します。対象行数: {len(df_other)}")

if not df_other.empty:
    df_other['prediction_score_top3'] = 0.5
    predicted_chunks.append(df_other)
else:
    print("  -> otherに分類されたデータは0件です。")

df_base = pd.concat(predicted_chunks, axis=0).sort_index()
print("===== クラス別予測データの追跡終了 =====\n")


# --- 5. 1着予測モデルの予測実行 ---
print("1着予測モデルの予測を実行中...")
if saved_model_1st is not None:
    try:
        df_input_1st = align_features_strictly(df_base, saved_model_1st)
        preds_1 = predict_model(saved_model_1st, data=df_input_1st, verbose=False)
        score_col_1st = 'prediction_score' if 'prediction_score' in preds_1.columns else preds_1.columns[-1]
        df_base['prediction_score_1st'] = preds_1[score_col_1st].values
        print("  -> 1着予測スコアを正常に算出しました。")
    except Exception as e:
        print(f"  -> ⚠️1着予測中にエラーが発生したため、デフォルト値(0.14)を適用します: {e}")
        df_base['prediction_score_1st'] = 0.14
else:
    print("  -> ⚠️1着モデルが存在しないため、一律0.14を割り当てます。")
    df_base['prediction_score_1st'] = 0.14

df_base = df_base.drop_duplicates(subset=['race_id', '車_番']).reset_index(drop=True)


# --- 6. 選手単位データ：keirin_prediction_result.csv の保存 ---
display_columns = [
    "race_id", "競輪場", "レース番号", "開始時間", "開催番号", "レースタイトル",
    "車_番", "選手名", "競走得点", "S", "B",
    "prediction_score_top3", "prediction_score_1st"
]
display_columns = [c for c in display_columns if c in df_base.columns]

sorted_result = df_base[display_columns].sort_values(
    by=['開始時間', '競輪場', 'レース番号', 'prediction_score_top3'],
    ascending=[True, True, True, False]
).copy()

sorted_result = sorted_result.drop_duplicates(subset=['race_id', '車_番'])
sorted_result.to_csv('keirin_prediction_result.csv', index=False, encoding='utf-8-sig')
sorted_result.to_csv('keirin_prediction_result_combined.csv', index=False, encoding='utf-8-sig')
print("-> 'keirin_prediction_result.csv' を出力しました。")


# --- 7. レース単位データ：updated_keirin_race_summary.csv の算定・作成ロジック ---
print("レース単位の集計ロジック（A率〜I率、スコア、買い目）を個別に計算中...")

def generate_race_summary(df_all):
    summary_rows = []
    grouped = df_all.groupby('race_id')
    
    class_mapping = {
        'girls': 'ガ',
        'challenge': 'チ',
        'a_class': 'Ａ',
        's_class': 'Ｓ',
        'other': 'Ａ'
    }
    
    rate_labels = ['A率', 'B率', 'C率', 'D率', 'E率', 'F率', 'G率', 'H率', 'I率']
    
    for race_id, group in grouped:
        group = group.drop_duplicates(subset=['車_番'])
        num_racers = len(group)
        if num_racers == 0:
            continue
            
        競輪場 = group.iloc[0]['競輪場']
        レース番号 = group.iloc[0]['レース番号']
        開始時間 = group.iloc[0]['開始時間']
        開催番号 = group.iloc[0]['開催番号']
        
        r_class = group.iloc[0]['race_class']
        レース区分 = class_mapping.get(r_class, 'Ａ')
        
        # --- 【買い目選定用ソート: 3着以内モデル基準】 ---
        group_top3 = group.sort_values(by='prediction_score_top3', ascending=False)
        try:
            t1 = int(group_top3.iloc[0]['車_番'])
            t2 = int(group_top3.iloc[1]['車_番'])
            t3 = int(group_top3.iloc[2]['車_番'])
            sanrentan_top3 = f'="{t1}-{t2}-{t3}"'
            
            remaining_cars_top3 = [str(int(x)) for x in group_top3['車_番'].iloc[3:].tolist()]
            if remaining_cars_top3:
                top3_hoketsu = f'="{ "-".join(remaining_cars_top3) }"'
            else:
                top3_hoketsu = ""
        except:
            sanrentan_top3, top3_hoketsu = "N/A", "N/A"
            
        # --- 【買い目選定用ソート: 1着モデル基準】 ---
        group_1st = group.sort_values(by='prediction_score_1st', ascending=False)
        try:
            w1 = int(group_1st.iloc[0]['車_番'])
            w2 = int(group_1st.iloc[1]['車_番'])
            w3 = int(group_1st.iloc[2]['車_番'])
            nirentan_1st = f'="{w1}-{w2}"'
            sanrentan_1st = f'="{w1}-{w2}-{w3}"'
            
            remaining_cars_1st = [str(int(x)) for x in group_1st['車_番'].iloc[3:].tolist()]
            if remaining_cars_1st:
                st1_hoketsu = f'="{ "-".join(remaining_cars_1st) }"'
            else:
                st1_hoketsu = ""
        except:
            nirentan_1st, sanrentan_1st, st1_hoketsu = "N/A", "N/A", "N/A"

        # --- 【全車（A率〜I率）スコア算出用の動的集計ロジック】 ---
        scores_sorted = group_top3['prediction_score_top3'].tolist()
        
        race_dict = {
            'race_id': race_id,  # ★ 追加: race_id を格納
            '競輪場': 競輪場,
            'レース番号': レース番号,
            '開始時間': 開始時間,
            '開始日目': 開催番号,
            'レース区分': レース区分,
            '2車単': nirentan_1st,
            '3連単_1着': sanrentan_1st,
            '1着_補欠': st1_hoketsu,
            '3連単_3着以内': sanrentan_top3,
            '3着以内_補欠': top3_hoketsu 
        }
        
        for i, label in enumerate(rate_labels):
            if i < len(scores_sorted):
                race_dict[label] = round(scores_sorted[i], 2)
            else:
                race_dict[label] = ""  
        
        try:
            a_rate = scores_sorted[0] if len(scores_sorted) > 0 else 0
            d_rate = scores_sorted[3] if len(scores_sorted) > 3 else (scores_sorted[-1] if len(scores_sorted) > 0 else 0)
            avg = sum(scores_sorted) / len(scores_sorted) if len(scores_sorted) > 0 else 0
            
            ct_value = (a_rate - d_rate) / a_rate if a_rate > 0 else 0
            ct_value2 = (a_rate - avg) / a_rate if avg > 0 else 0
            score_value = (a_rate * 50) + (ct_value * 25) + (ct_value2 * 25)
        except:
            ct_value, score_value = 0, 0
            
        race_dict['CT値'] = round(ct_value, 2)
        race_dict['スコア'] = round(score_value, 2)
        race_dict['選手数'] = num_racers
        
        summary_rows.append(race_dict)
        
    return pd.DataFrame(summary_rows)

# レース単位集計の実行
df_summary = generate_race_summary(df_base)
df_summary_sorted = df_summary.sort_values(by='開始時間', ascending=True)

# ★ 新・運用ロジックの判定結果を適用
df_summary_sorted['運用判定'] = df_summary_sorted.apply(judge_operation_logic, axis=1)

# 指定の列順序に並び替え（先頭に 'race_id' を追加）
ordered_cols = [
    'race_id', '競輪場', 'レース番号', '開始時間', '開始日目', 'レース区分', 
    '2車単', '3連単_1着', '1着_補欠', '3連単_3着以内', '3着以内_補欠',
    'A率', 'B率', 'C率', 'D率', 'E率', 'F率', 'G率', 'H率', 'I率', 
    'CT値', 'スコア', '運用判定', '選手数'
]
df_summary_sorted = df_summary_sorted[ordered_cols]

# 成果物出力
df_summary_sorted.to_csv('updated_keirin_race_summary.csv', index=False, encoding='utf-8-sig')
df_summary_sorted.to_csv('keirin_race_summary.csv', index=False, encoding='utf-8-sig')
print("-> 'updated_keirin_race_summary.csv' および 'keirin_race_summary.csv' を出力しました！")

# ★ 運用判定で「買い目あり（見送り以外）」のレースのみを抽出して出力
df_summary4 = df_summary_sorted[df_summary_sorted['運用判定'] != '見送り'].copy()
df_summary4.to_csv('keirin_race_summary4.csv', index=False, encoding='utf-8-sig')
print("-> 'keirin_race_summary4.csv' (買い目抽出版) を出力しました！")

print("\n【完了】すべての修正が完了しました。")