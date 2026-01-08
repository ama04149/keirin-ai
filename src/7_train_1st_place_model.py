import pandas as pd
from pycaret.classification import *
from sklearn.metrics import confusion_matrix
import seaborn as sns
from sklearn.metrics import roc_auc_score
from pycaret.classification import plot_model
import matplotlib.pyplot as plt
import japanize_matplotlib

# --- 1. データの読み込みと結合 ---
df_shussou = pd.read_pickle('race_card3_202106-202512.pkl')
df_raceinfo = pd.read_pickle('race_info2_202106-202512.pkl')

df_shussou.reset_index(inplace=True)
df_raceinfo.reset_index(inplace=True)

df = pd.merge(df_shussou, df_raceinfo, on='index', how='left')
print(f"データ結合後のShape: {df.shape}")


# --- 2. データの前処理と特徴量生成 ---

# 【修正箇所①】列名のクリーニングを最初に行う
df.columns = df.columns.str.strip()
df.columns = df.columns.str.replace(' ', '_').str.replace('　', '_')

# 【修正箇所②】数値変換処理をここに集約
# カテゴリとして扱う列を先に定義
categorical_features = ['枠_番', '車_番', '級_班', '脚_質', '期別', '競輪場', 'グレード', '天気', 'レース番号','レースタイトル', '開催番号', '強度', '強度２', '強度３', 'ライン構成', '1周'] #'予_想', 

# カテゴリ変数と、手動で処理/削除する列を定義
exclude_from_numeric_conversion = categorical_features + ['index', '総_評', 'レース名', '開催日', '開始時間', '予_想']# 'レースタイトル','選手名', 

# 【修正箇所④】除外リスト以外の全ての列を一括で数値化 ('着_順'もここで処理される)
for col in df.columns:
    if col not in exclude_from_numeric_conversion:
        df[col] = pd.to_numeric(df[col], errors='coerce')

# 【修正箇所③】目的変数(target)の作成
df['着_順'].fillna(99, inplace=True)
df['着_順'] = df['着_順'].astype(int)
df['target'] = df['着_順'].apply(lambda x: 1 if x == 1 else 0)
df['target'] = df['target'].astype(int)

# 【変更点②】(重要) スコアが逆転しないため、targetの反転処理は削除
#df['target'] = 1 - df['target'] # ← この行を削除またはコメントアウト

# 【修正箇所④】学習に不要な列を最後にまとめて削除
columns_to_drop = [
    'index' , '予_想', '総_評', '着_順', 
    'レース名', '開催日'
    # ★★★ ここから下の特徴量を追加で削除 ★★★ 2026/01/01予想を除外
    # 'レースタイトル', '予_想', '得点順位', '競走得点_sa', 'B_sa', 'B_sa2', 'B_suu', '逃_sa', 
    #'逃_sa2', '逃_suu', '捲_sa', '差_sa', 'マ_sa', '選手名', 
]
df = df.drop(columns=columns_to_drop, errors='ignore')

# --- 3. PyCaretのセットアップ ---

# データを学習用(90%)と評価用(10%)に分割
data_train = df.sample(frac=0.9, random_state=123)
data_unseen = df.drop(data_train.index)
data_train.reset_index(drop=True, inplace=True)
data_unseen.reset_index(drop=True, inplace=True)

#print('学習用データ数:', data_train.shape)
#print('評価用データ数:', data_unseen.shape)

#print('【学習時の最終列】:', data_train.drop('target', axis=1).columns)
#print('【学習時のデータ型】\n', data_train.dtypes) 

# PyCaretの環境をセットアップ
s = setup(data=data_train,
        target='target',
        session_id=123,
        n_jobs=4,
        categorical_features=categorical_features,
        ignore_features=['開始時間'], # 時間データは今回は無視
        fix_imbalance=True, # 1着予測は不均衡データなのでTrueを推奨
        feature_selection=True,
        verbose=False)
'''
# --- 4. モデルの学習と評価 2025/11/27修正---
best_model = compare_models(
    sort='AUC',
    verbose=False,
    #include=['lr', 'dt', 'rf', 'xgboost', 'catboost', 'lightgbm', 'knn', 'svm', 'gbc', 'et', 'ada'])
    include=['lightgbm'])
'''
top3_models = compare_models(
    sort='AUC',
    verbose=False,
    n_select=3,   # 上位3つのモデルを選択
    include=['lightgbm', 'xgboost', 'catboost'])


# 直前に生成された比較結果の表をDataFrameとして取得
results_grid = pull()

# 取得した表をコンソールに表示
print("--- モデル比較結果 ---")
print(results_grid)

# monotone_constraints={'予_想': 0, '競走得点': 1, '年齢': -1, 'ライン数': -1}
# create_model を使って、制約付きのモデルを作成
# best_model = create_model(best_model, monotone_constraints=monotone_constraints)

# --- スタッキングモデルの構築 2025/11/27追加---
stacked_model = stack_models(
    estimator_list=top3_models, 
    meta_model=create_model('lr')  # メタモデルはロジスティック回帰でOK
)

# 最適モデルのハイパーパラメータをチューニング
#tuned_model = tune_model(best_model) 2025/11/27修正

# --- スタッキングモデルをチューニング 2025/11/27追加---
tuned_model = tune_model(stacked_model)
# --- 最終モデルを生成 ---
final_model = finalize_model(tuned_model)


#tuned_model = tune_model(best_model, n_iter=50)
#tuned_model = blend_models(estimator_list=best_model)
# チューニング済みモデルを最終化（全学習データで再学習）
#final_model = finalize_model(tuned_model)

# 【変更点④】保存するモデル名を変更
save_model(final_model, 'keirin_model_1st_place') # ← 新しい名前を指定
print(f"\n1着予測モデルが 'keirin_model_1st_place.pkl' として保存されました。")

# --- 5. 評価と診断 ---
# 正しい列の順序を保存
correct_columns = data_train.drop('target', axis=1).columns.tolist()
# 【変更点⑤】列順序ファイルも別名で保存
pd.to_pickle(correct_columns, 'model_columns_1st.pkl')
print("1着予測モデルの列順序を 'model_columns_1st.pkl' に保存しました。")

# 混同行列の計算
holdout_predictions = predict_model(tuned_model)
cm = confusion_matrix(holdout_predictions['target'], holdout_predictions['prediction_label'])
print("\n混同行列 (Numpy配列):\n", cm)

# モデルの基本性能診断
train_preds = predict_model(final_model, data=data_train)
# スコアが逆転している可能性があるため、1から引いて補正
train_preds['prediction_score'] = 1 - train_preds['prediction_score'] 
correlation = train_preds[['競走得点', 'prediction_score']].corr()
print("\n「競走得点」と「補正後予測スコア」の相関行列:\n", correlation)

#print(train_preds[['target', 'prediction_label', 'prediction_score']].head(10))
#print(df['競走得点'].describe())

#plot_model(final_model, plot='feature')

# どのしきい値が最適かを探るためのプロット
#plot_model(final_model, plot='threshold')

#print(train_preds.groupby('target')['prediction_score'].describe())
