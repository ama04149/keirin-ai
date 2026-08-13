"""
daily_predict.py
-----------------
毎日のスクレイピング結果(today_race_card3.pkl / today_race_info2.pkl)から、
「高自信レースのみ・3車ボックス」戦略の買い目を出力するスクリプト。

前提:
  - build_production_models.py を事前に1回(または定期的に)実行し、
    models/ フォルダに学習済みモデル一式が保存されていること。
  - today_race_card3.pkl は 1_race_id_scrape.py -> 2_race_data_scrape.py ->
    3_back_sabun.py -> 4_def_line_kyoudo.py と同じ手順で「本日開催分のrace_id」
    だけを対象に作られたもの(t_race.py が読んでいるものと同じ形式)。
  - today_race_info2.pkl も同様に本日開催分のレース情報。

出力:
  - keirin_daily_recommend.csv : 「買い」判定になったレースの推奨3車ボックスのみ
  - keirin_daily_all_races.csv : 全レースの自信度・推奨/見送りステータス一覧(参考用)
"""
import pandas as pd
import numpy as np
import joblib
import os
from itertools import permutations

# models/ フォルダはこのスクリプト自身の場所を基準にする(どこから実行しても迷わないように)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(SCRIPT_DIR, 'models')

# 本日のレースデータは、実行時のカレントディレクトリ(スクレイピングの出力先)から読む
TODAY_CARD_PATH = 'today_race_card3.pkl'
TODAY_INFO_PATH = 'today_race_info2.pkl'

BOX_COST_PER_COMBO = 100  # 3連単1点あたりの金額


def load_today_data():
    card = pd.read_pickle(TODAY_CARD_PATH)
    info = pd.read_pickle(TODAY_INFO_PATH)

    # race_idが列にあるか、indexに入っているかのどちらにも対応する
    if 'race_id' not in card.columns:
        card = card.reset_index().rename(columns={'index': 'race_id'})
    if 'race_id' not in info.columns:
        info = info.reset_index().rename(columns={'index': 'race_id'})

    card['race_id'] = card['race_id'].astype(str)
    info['race_id'] = info['race_id'].astype(str)

    # 前回実行分の予測列などが紛れ込んでいた場合に備えて念のため削除
    drop_if_exists = ['indiv_pred_top3', 'line_power_score', 'combined_score',
                       'ライン人数', 'A率', 'B率', 'C率', 'D率', 'E率', 'F率', 'G率',
                       'H率', 'I率', 'CT値', 'スコア']
    card = card.drop(columns=[c for c in drop_if_exists if c in card.columns])

    return card, info


def build_features(card, info, cat_maps, numeric_feats, categorical_feats):
    merged = card.merge(
        info[['race_id', 'グレード', '天気', '1周', '開催番号']],
        on='race_id', how='left'
    )
    line_size = merged.groupby(['race_id', 'ライン']).size().rename('ライン人数').reset_index()
    merged = merged.merge(line_size, on=['race_id', 'ライン'], how='left')

    for c in numeric_feats:
        merged[c] = pd.to_numeric(merged[c], errors='coerce')

    for c in categorical_feats:
        m = cat_maps[c]
        merged[c + '_code'] = merged[c].astype(str).map(m).fillna(-1).astype(int)

    return merged


def main():
    print('モデル一式を読み込んでいます...')
    stage1_model = joblib.load(f'{MODEL_DIR}/stage1_model.pkl')
    stage2_model = joblib.load(f'{MODEL_DIR}/stage2_model.pkl')
    cat_maps = joblib.load(f'{MODEL_DIR}/category_maps.pkl')
    confidence_threshold = joblib.load(f'{MODEL_DIR}/confidence_threshold.pkl')
    cfg = joblib.load(f'{MODEL_DIR}/feature_config.pkl')

    numeric_feats = cfg['numeric_feats']
    categorical_feats = cfg['categorical_feats']
    feature_cols = cfg['feature_cols']
    line_feature_cols = cfg['line_feature_cols']

    print(f'自信度しきい値(この値以上のレースだけ購入対象): {confidence_threshold:.4f}')

    print('本日のレースデータを読み込んでいます...')
    card, info = load_today_data()
    print(f'本日のレース数: {card["race_id"].nunique()}  出走選手数: {len(card)}')

    merged = build_features(card, info, cat_maps, numeric_feats, categorical_feats)

    # ---- Stage1: 個人の3着以内予測 ----
    X = merged[feature_cols].fillna(-999)
    merged['indiv_pred_top3'] = stage1_model.predict_proba(X)[:, 1]

    # ---- ライン特徴量を構築 ----
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
    ).reset_index()
    lead_pred = merged[merged['番手'] == 1][['race_id', 'ライン', 'indiv_pred_top3']]

    line_df = line_size2.merge(lead, on=['race_id', 'ライン'], how='left') \
                         .merge(followers, on=['race_id', 'ライン'], how='left') \
                         .merge(line_agg_pred, on=['race_id', 'ライン'], how='left') \
                         .merge(lead_pred, on=['race_id', 'ライン'], how='left')
    for c in ['番手以降_平均得点sa', '番手以降_平均差sa', '番手以降_平均マsa']:
        line_df[c] = line_df[c].fillna(0)
    line_df['先頭_予測top3score'] = line_df['indiv_pred_top3'].fillna(line_df['ライン内平均予測score'])

    line_max_pred = merged.groupby(['race_id', 'ライン'])['indiv_pred_top3'].max().rename('ライン内最大予測score').reset_index()
    line_df = line_df.merge(line_max_pred, on=['race_id', 'ライン'], how='left')

    # ---- Stage2: ラインの勝率予測 ----
    Xl = line_df[line_feature_cols].fillna(-999)
    line_df['line_power_score'] = stage2_model.predict_proba(Xl)[:, 1]

    # ---- 個人のcombined_scoreを付与 ----
    merged = merged.merge(line_df[['race_id', 'ライン', 'line_power_score']], on=['race_id', 'ライン'], how='left')
    merged['line_power_score'] = merged['line_power_score'].fillna(0)
    merged['combined_score'] = merged['indiv_pred_top3'] + 0.5 * merged['line_power_score']

    # ---- レースごとの自信度(1位-3位のcombined_score差)を計算 ----
    def conf_gap(g):
        s = g.sort_values('combined_score', ascending=False)['combined_score'].values
        if len(s) < 3:
            return np.nan
        return s[0] - s[2]

    conf_df = merged.groupby('race_id').apply(conf_gap).rename('confidence').reset_index()
    merged = merged.merge(conf_df, on='race_id', how='left')

    # ---- レース情報(競輪場・レース番号・開始時間など)を付与 ----
    info_cols = [c for c in ['競輪場', 'レース番号', '開始時間', 'グレード', '開催番号'] if c in info.columns]
    merged = merged.merge(info[['race_id'] + info_cols], on='race_id', how='left')

    # ---- レース単位のサマリーを作成 ----
    summary_rows = []
    for race_id, g in merged.groupby('race_id'):
        g_sorted = g.sort_values('combined_score', ascending=False)
        conf = g_sorted['confidence'].iloc[0]
        is_buy = bool(conf >= confidence_threshold) if pd.notna(conf) else False

        top3 = g_sorted.head(3)['車 番'].astype(int).tolist()
        if len(top3) < 3:
            is_buy = False
            box_str = ''
        else:
            box_str = f'="{top3[0]}-{top3[1]}-{top3[2]}"'

        row = {
            'race_id': race_id,
            '競輪場': g_sorted['競輪場'].iloc[0] if '競輪場' in g_sorted.columns else '',
            'レース番号': g_sorted['レース番号'].iloc[0] if 'レース番号' in g_sorted.columns else '',
            '開始時間': g_sorted['開始時間'].iloc[0] if '開始時間' in g_sorted.columns else '',
            '自信度': round(conf, 4) if pd.notna(conf) else None,
            '判定': '購入' if is_buy else '見送り',
            '推奨3車ボックス': box_str if is_buy else '',
            '推奨選手': '-'.join(map(str, top3)) if len(top3) >= 3 else '',
            '購入点数': 6 if is_buy else 0,
            '購入金額': 6 * BOX_COST_PER_COMBO if is_buy else 0,
        }
        summary_rows.append(row)

    summary = pd.DataFrame(summary_rows).sort_values(['開始時間', '競輪場', 'レース番号'], na_position='last')

    summary.to_csv('keirin_daily_all_races.csv', index=False, encoding='utf-8-sig')
    buy_only = summary[summary['判定'] == '購入'].copy()
    buy_only.to_csv('keirin_daily_recommend.csv', index=False, encoding='utf-8-sig')

    print('\n===== 本日の結果 =====')
    print(f'全レース数: {len(summary)}')
    print(f'購入対象(高自信)レース数: {len(buy_only)}')
    print(f'想定投資額合計: {buy_only["購入金額"].sum():,}円')
    print('\n-> keirin_daily_recommend.csv (購入対象のみ) を出力しました。')
    print('-> keirin_daily_all_races.csv (全レース・自信度付き) を出力しました。')


if __name__ == '__main__':
    main()
