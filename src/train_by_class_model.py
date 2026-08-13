import pandas as pd
from pycaret.classification import *
from sklearn.metrics import confusion_matrix
import sys
import io
import numpy as np

# --- 【新規追加】出力を画面とファイルの両方に同時に書き出すクラス ---
class Logger(object):
    def __init__(self, filename="model_training_debug.log"):
        self.terminal = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        self.log = open(filename, "w", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.terminal.flush()
        self.log.flush()

    def flush(self):
        self.terminal.flush()
        self.log.flush()

# 出力先をLoggerクラスに切り替え
sys.stdout = Logger()
sys.stderr = sys.stdout  # エラーログも同じファイルにまとめる

# =====================================================================
# ここから下のロジックはそのままファイルと画面に同時出力されます
# =====================================================================

# --- 1. データの読み込みと結合 ---
print("データを読み込んでいます...")
df_shussou = pd.read_pickle('race_card3_cumulative_ready.pkl')
df_raceinfo = pd.read_pickle('race_info2_202106-202606.pkl') 

df_shussou.reset_index(inplace=True)
df_raceinfo.reset_index(inplace=True)

df_all = pd.merge(df_shussou, df_raceinfo, on='index', how='left')
print(f"全データ結合後のShape: {df_all.shape}")

# --- 2. 共通データの前処理 ---

# ★追加: 「開始時間」から「時(Hour)」を抽出して新しい列「発走時」を作成 (例: "15:40" -> 15)
df_all['発走時'] = df_all['開始時間'].apply(lambda x: int(str(x).split(':')[0]) if pd.notna(x) and ':' in str(x) else 0)

df_all.columns = df_all.columns.str.strip().str.replace(' ', '_').str.replace(' ', '_')

categorical_features = ['枠_番', '車_番', '級_班', '脚_質', '期別', '競輪場', 'グレード', '天気', 'レース番号','レースタイトル', '開催番号', '強度', '強度２', '強度３', 'ライン構成', '1周']

# ★【追加】累積特徴量の定義
cumulative_features = ['累計勝率', '累計2連対率', '累計3連対率', '累計出走数']

# ★【変更】累積特徴量も数値変換させたいので、除外リスト（exclude_from_numeric_conversion）に「絶対に含めない」ようにします
# （categorical_features等に累積特徴量は入っていないため、これで自動的に数値変換処理が実行されます）
exclude_from_numeric_conversion = categorical_features + ['index', '総_評', 'レース名', '開催日', '開始時間', '予_想', '選手名']

# 数値化 (これにより「発走時」や「各種累積特徴量」も正常に数値化されます)
for col in df_all.columns:
    if col not in exclude_from_numeric_conversion:
        df_all[col] = pd.to_numeric(df_all[col], errors='coerce')
        
# 欠損値補正
numeric_cols = df_all.select_dtypes(include=['number']).columns
df_all[numeric_cols] = df_all[numeric_cols].fillna(0)

object_cols = df_all.select_dtypes(include=['object']).columns
df_all[object_cols] = df_all[object_cols].fillna('unknown')

# ★【追加】PyCaretのsetupに渡す数値特徴量のリストを定義（発走時 ＋ 累積特徴量）
numeric_features_for_pycaret = cumulative_features + ['発走時']

# 目的変数の作成
df_all['着_順'] = pd.to_numeric(df_all['着_順'], errors='coerce').fillna(99)
df_all['target'] = df_all['着_順'].apply(lambda x: 1 if x <= 3 else 0).astype(int)

# 不要列の削除
columns_to_drop = ['index' , '予_想', '総_評', '着_順', '選手名', 'レース名', '開催日']
df_all = df_all.drop(columns=columns_to_drop, errors='ignore')


# --- 3. レース種別（クラス）の判定関数と分割 【判定漏れ対策・強化版】 ---
def detect_race_class(row):
    kyu_han = str(row['級_班']).strip().upper()
    race_title = str(row['レースタイトル']) if 'レースタイトル' in row else ''
    
    # ガールズ判定
    if 'L' in kyu_han or 'ガールズ' in race_title:
        return 'girls'
    # チャレンジ判定（A3班、またはタイトルに「チャレンジ」「チ」が含まれる）
    elif 'チャレンジ' in race_title or 'チ' in race_title or 'A3' in kyu_han:
        return 'challenge'
    # A級判定（1班・2班）
    elif 'A' in kyu_han:
        return 'a_class'
    # S級判定
    elif 'S' in kyu_han:
        return 's_class'
    else:
        return 'other'

# クラス列を追加
df_all['race_class'] = df_all.apply(detect_race_class, axis=1)
print("\n--- 【調査ログ】レース種別ごとのデータ件数 ---")
print(df_all['race_class'].value_counts())


# --- 4. ループ処理による各モデルの学習と保存 ---
target_classes = ['girls', 'challenge', 'a_class', 's_class']

for r_class in target_classes:
    print(f"\n==================================================")
    print(f" ロジック開始: {r_class.upper()} モデルの学習")
    print(f"==================================================")
    
    # 該当クラスのデータのみ抽出
    df_class = df_all[df_all['race_class'] == r_class].copy()
    print(f"[{r_class}] 抽出されたデータ件数: {len(df_class)}件 (うち target=1 は {df_class['target'].sum()}件)")
    
    if len(df_class) < 100:
        print(f"【スキップ】{r_class} のデータ数が少なすぎます ({len(df_class)}件)")
        continue
        
    df_class = df_class.drop(columns=['race_class'])
    
    # データを学習用(90%)と評価用(10%)に分割
    data_train = df_class.sample(frac=0.9, random_state=123)
    data_unseen = df_class.drop(data_train.index)
    data_train.reset_index(drop=True, inplace=True)
    data_unseen.reset_index(drop=True, inplace=True)
    
    # PyCaretのセットアップ
    s = setup(data=data_train,
            target='target',
            session_id=123,
            n_jobs=4,
            categorical_features=categorical_features,
            numeric_features=numeric_features_for_pycaret, # ★【変更】「発走時」に加え「累積特徴量」も数値特徴量として明示的に指定
            ignore_features=['開始時間'],
            fix_imbalance=True,
            feature_selection=True,
            verbose=False)
    
    # 【調査ログ】最終的にPyCaretがモデルに入力することを選択した特徴量の一覧
    print(f"[{r_class}] 【重要】モデル学習に使用される特徴量の数: {len(s.X_train.columns)}個")
    if '発走時' in s.X_train.columns:
        print(f"  -> 発走時（時間帯）列は正常に維持され、学習に組み込まれました。")
    
    # ★【追加】累積特徴量のログ確認
    for feat in cumulative_features:
        if feat in s.X_train.columns:
            print(f"  -> {feat} 列は正常に維持され、学習に組み込まれました。")
        else:
            print(f"  -> ⚠️警告: 『{feat}』が特徴量選択(feature_selection)によって消去されました！")

    if '競走得点' in s.X_train.columns:
        print(f"  -> 競走得点列は正常に維持されています。")
    else:
        print(f"  -> ⚠️警告: 『競走得点』が特徴量選択(feature_selection)によって消去されました！")

    # LightGBMモデルを直接生成
    lgbm_model = create_model('lightgbm', verbose=False)
    
    # チューニングと最終化
    tuned_model = tune_model(lgbm_model, verbose=False)
    final_model = finalize_model(tuned_model)
    
    # モデルと列順序の保存
    model_name = f'keirin_model_3rd_{r_class}'
    save_model(final_model, model_name)
    
    correct_columns = data_train.drop('target', axis=1).columns.tolist()
    pd.to_pickle(correct_columns, f'model_columns_3rd_{r_class}.pkl')
    
    # 【最重要調査ログ】ホールドアウトデータでの確率予測の分布チェック
    holdout_predictions = predict_model(tuned_model, verbose=False)
    
    # 予測ラベル列と予測確率列の特定
    score_col = 'prediction_score' if 'prediction_score' in holdout_predictions.columns else holdout_predictions.columns[-1]
    
    print(f"[{r_class}] 【検証】テストデータに対する予測確率の分布:")
    print(f"  -> MAX（最高確率）: {holdout_predictions[score_col].max():.4f}")
    print(f"  -> MIN（最低確率）: {holdout_predictions[score_col].min():.4f}")
    print(f"  -> AVG（平均確率）: {holdout_predictions[score_col].mean():.4f}")
    
    cm = confusion_matrix(holdout_predictions['target'], holdout_predictions['prediction_label'])
    print(f"[{r_class}] 混同行列:\n", cm)

print("\n 全てのレース種別のモデル構築・調査ロギングが完了しました！")