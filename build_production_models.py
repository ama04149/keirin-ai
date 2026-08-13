"""
build_production_models.py
---------------------------
これまでの検証で確定した「高自信レースのみ・3車ボックス」戦略を実運用するための
本番用モデル一式を、全期間の履歴データから作成して保存するスクリプト。

作られるファイル(models/ フォルダに保存):
  - stage1_model.pkl        : 個人(3着以内)予測モデル
  - stage2_model.pkl        : ライン力(win_line)予測モデル
  - category_maps.pkl       : カテゴリ特徴量の 文字列 -> コード 変換辞書(学習時と同じ変換をするため必須)
  - confidence_threshold.pkl: 「高自信」判定のしきい値(過去データの上位1/3分位点)
  - feature_config.pkl      : 特徴量リストなどの設定一式

日次予測は daily_predict.py 側でこれらを読み込んで使用する。
"""
import pandas as pd
import numpy as np
import joblib
import os
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import GroupKFold

# スクリプト自身の場所を基準にパスを組み立てる(どのフォルダから実行しても動くようにするため)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SCRIPT_DIR, 'models')
os.makedirs(OUT_DIR, exist_ok=True)

# このスクリプトと同じフォルダに、前回お渡しした修正版(race_id保持版・CSV形式)を置いてください
# ※pickle形式はpandasのバージョン間で互換性が壊れることがあるため、CSV(gzip圧縮)形式に変更しました
CARD_PATH = os.path.join(SCRIPT_DIR, 'race_card3_202106-202606_FIXED.csv.gz')
INFO_PATH = os.path.join(SCRIPT_DIR, 'race_info2_202106-202606_FIXED.csv.gz')

NUMERIC_FEATS = ['競走得点', '年齢', '期別', '得点順位', '競走得点_sa',
                 'S', 'B', 'B_sa', 'B_sa2', 'B_suu',
                 '逃', '逃_sa', '逃_sa2', '逃_suu',
                 '捲', '捲_sa', '差', '差_sa', 'マ', 'マ_sa',
                 '勝 率', '2連 対率', '3連 対率', '番手', 'ライン人数']
CATEGORICAL_FEATS = ['脚 質', '級 班', '強度', 'グレード', '天気', '1周', '開催番号']
LINE_FEATURE_COLS = ['人数', '先頭_得点順位', '先頭_競走得点sa', '先頭_逃sa', '先頭_逃suu',
                     '番手以降_平均得点sa', '番手以降_平均差sa', '番手以降_平均マsa',
                     '先頭_予測top3score', 'ライン内平均予測score', 'ライン内最大予測score']


def build_category_maps(df, cat_cols):
    """学習データから 文字列 -> コード の対応表を作る。予測時は同じ表を使い、
    未知のカテゴリ値は -1(unknown)扱いにする。"""
    maps = {}
    for c in cat_cols:
        uniques = pd.unique(df[c].astype(str))
        maps[c] = {v: i for i, v in enumerate(uniques)}
    return maps


def apply_category_maps(df, cat_cols, maps):
    out = df.copy()
    for c in cat_cols:
        m = maps[c]
        out[c + '_code'] = out[c].astype(str).map(m).fillna(-1).astype(int)
    return out


def main():
    print('データ読み込み中...')
    card = pd.read_csv(CARD_PATH, encoding='utf-8-sig', compression='gzip', dtype={'race_id': str})
    info = pd.read_csv(INFO_PATH, encoding='utf-8-sig', compression='gzip', dtype={'race_id': str})

    info_reset = info.copy()
    info_reset['開催日'] = pd.to_datetime(info_reset['開催日'], errors='coerce')

    card['着 順'] = pd.to_numeric(card['着 順'], errors='coerce')

    merged = card.merge(
        info_reset[['race_id', 'グレード', '天気', '1周', '開催番号', '開催日']],
        on='race_id', how='left'
    )
    line_size = merged.groupby(['race_id', 'ライン']).size().rename('ライン人数').reset_index()
    merged = merged.merge(line_size, on=['race_id', 'ライン'], how='left')
    merged = merged.dropna(subset=['着 順']).copy()
    merged['target_top3'] = (merged['着 順'] <= 3).astype(int)

    for c in NUMERIC_FEATS:
        merged[c] = pd.to_numeric(merged[c], errors='coerce')

    # ---- カテゴリ変換マップを作成・保存 ----
    cat_maps = build_category_maps(merged, CATEGORICAL_FEATS)
    merged = apply_category_maps(merged, CATEGORICAL_FEATS, cat_maps)

    feature_cols = NUMERIC_FEATS + [c + '_code' for c in CATEGORICAL_FEATS]
    cat_indices = [feature_cols.index(c + '_code') for c in CATEGORICAL_FEATS]

    X = merged[feature_cols].fillna(-999)
    y = merged['target_top3'].values
    groups = merged['race_id'].values

    # ---- Stage1: 個人モデル(全データで最終学習) ----
    print('Stage1(個人モデル)を全データで学習中...')
    stage1_model = HistGradientBoostingClassifier(
        max_iter=150, learning_rate=0.08, max_depth=6,
        categorical_features=cat_indices, random_state=42
    )
    stage1_model.fit(X, y)

    # ここで即保存(この後の処理が時間切れになっても、本番用モデル自体は失われないように)
    joblib.dump(stage1_model, f'{OUT_DIR}/stage1_model.pkl')
    joblib.dump(cat_maps, f'{OUT_DIR}/category_maps.pkl')
    joblib.dump({
        'numeric_feats': NUMERIC_FEATS,
        'categorical_feats': CATEGORICAL_FEATS,
        'feature_cols': feature_cols,
        'cat_indices': cat_indices,
        'line_feature_cols': LINE_FEATURE_COLS,
    }, f'{OUT_DIR}/feature_config.pkl')
    print('Stage1モデルを保存しました。')

    # Stage2用の特徴量はリーク防止のためGroupKFoldでOOF予測を作る
    print('Stage2用にOOF予測を作成中(GroupKFold)...')
    oof_pred = np.zeros(len(merged))
    gkf = GroupKFold(n_splits=5)
    for tr_idx, va_idx in gkf.split(X, y, groups):
        m = HistGradientBoostingClassifier(
            max_iter=150, learning_rate=0.08, max_depth=6,
            categorical_features=cat_indices, random_state=42
        )
        m.fit(X.iloc[tr_idx], y[tr_idx])
        oof_pred[va_idx] = m.predict_proba(X.iloc[va_idx])[:, 1]
    merged['indiv_pred_top3'] = oof_pred

    # ---- ライン特徴量を構築 ----
    print('ライン特徴量を構築中...')
    lead = merged[merged['番手'] == 1].copy().rename(columns={
        '得点順位': '先頭_得点順位', '競走得点_sa': '先頭_競走得点sa',
        '逃_sa': '先頭_逃sa', '逃_suu': '先頭_逃suu',
    })[['race_id', 'ライン', '先頭_得点順位', '先頭_競走得点sa', '先頭_逃sa', '先頭_逃suu']]

    followers = merged[merged['番手'] > 1].groupby(['race_id', 'ライン']).agg(
        番手以降_平均得点sa=('競走得点_sa', 'mean'),
        番手以降_平均差sa=('差_sa', 'mean'),
        番手以降_平均マsa=('マ_sa', 'mean'),
    ).reset_index()

    line_size2 = merged.groupby(['race_id', 'ライン']).size().reset_index(name='人数')
    line_agg_pred = merged.groupby(['race_id', 'ライン']).agg(
        ライン内平均予測score=('indiv_pred_top3', 'mean'),
        ライン内最大予測score=('indiv_pred_top3', 'max'),
    ).reset_index()

    line_features = line_size2.merge(lead, on=['race_id', 'ライン'], how='left') \
                               .merge(followers, on=['race_id', 'ライン'], how='left') \
                               .merge(line_agg_pred, on=['race_id', 'ライン'], how='left')
    for c in ['番手以降_平均得点sa', '番手以降_平均差sa', '番手以降_平均マsa']:
        line_features[c] = line_features[c].fillna(0)
    line_features['先頭_予測top3score'] = line_features['ライン内平均予測score']
    lead_pred = merged[merged['番手'] == 1][['race_id', 'ライン', 'indiv_pred_top3']]
    line_features = line_features.merge(lead_pred, on=['race_id', 'ライン'], how='left', suffixes=('', '_lead'))
    line_features['先頭_予測top3score'] = line_features['indiv_pred_top3'].fillna(line_features['ライン内平均予測score'])
    line_features = line_features.drop(columns=['indiv_pred_top3'])

    outcome = merged.groupby(['race_id', 'ライン']).agg(
        win_line=('着 順', lambda x: int((x == 1).any())),
    ).reset_index()
    line_df = line_features.merge(outcome, on=['race_id', 'ライン'], how='inner')

    # ---- Stage2: ラインモデル(全データで最終学習) ----
    print('Stage2(ラインモデル)を全データで学習中...')
    Xl = line_df[LINE_FEATURE_COLS].fillna(-999)
    yl = line_df['win_line'].values
    stage2_model = HistGradientBoostingClassifier(max_iter=150, learning_rate=0.08, max_depth=5, random_state=42)
    stage2_model.fit(Xl, yl)
    joblib.dump(stage2_model, f'{OUT_DIR}/stage2_model.pkl')
    print('Stage2モデルを保存しました。')

    # Stage2のOOF(ラインもGroupKFoldでOOF化してcombined_scoreの自信度分布を作る)
    print('自信度しきい値を計算するためのOOF予測を作成中...')
    line_groups = line_df['race_id'].values
    oof_line_pred = np.zeros(len(line_df))
    for tr_idx, va_idx in gkf.split(Xl, yl, line_groups):
        m2 = HistGradientBoostingClassifier(max_iter=150, learning_rate=0.08, max_depth=5, random_state=42)
        m2.fit(Xl.iloc[tr_idx], yl[tr_idx])
        oof_line_pred[va_idx] = m2.predict_proba(Xl.iloc[va_idx])[:, 1]
    line_df['line_power_score'] = oof_line_pred

    # ---- 個人のcombined_scoreを再構築し、レースごとの自信度(1位-3位差)を計算 ----
    rider_line = merged[['race_id', 'ライン', '車 番', 'indiv_pred_top3']].merge(
        line_df[['race_id', 'ライン', 'line_power_score']], on=['race_id', 'ライン'], how='left')
    rider_line['line_power_score'] = rider_line['line_power_score'].fillna(0)
    rider_line['combined_score'] = rider_line['indiv_pred_top3'] + 0.5 * rider_line['line_power_score']

    def conf_gap(g):
        s = g.sort_values('combined_score', ascending=False)['combined_score'].values
        if len(s) < 3:
            return np.nan
        return s[0] - s[2]

    conf_series = rider_line.groupby('race_id').apply(conf_gap)
    conf_series = conf_series.dropna()
    # 上位1/3を「高自信」とするしきい値(2/3分位点)
    confidence_threshold = float(np.quantile(conf_series.values, 2 / 3))
    print(f'自信度しきい値(上位1/3の境界値): {confidence_threshold:.4f}')

    # ---- 保存 ----
    joblib.dump(stage1_model, f'{OUT_DIR}/stage1_model.pkl')
    joblib.dump(stage2_model, f'{OUT_DIR}/stage2_model.pkl')
    joblib.dump(cat_maps, f'{OUT_DIR}/category_maps.pkl')
    joblib.dump(confidence_threshold, f'{OUT_DIR}/confidence_threshold.pkl')
    joblib.dump({
        'numeric_feats': NUMERIC_FEATS,
        'categorical_feats': CATEGORICAL_FEATS,
        'feature_cols': feature_cols,
        'cat_indices': cat_indices,
        'line_feature_cols': LINE_FEATURE_COLS,
    }, f'{OUT_DIR}/feature_config.pkl')

    print('\n=== 保存完了 ===')
    for f in os.listdir(OUT_DIR):
        print(' -', f)


if __name__ == '__main__':
    main()
