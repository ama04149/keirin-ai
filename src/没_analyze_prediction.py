import pandas as pd
import numpy as np
import subprocess # Gitコマンド実行のために追加
import datetime # コミットメッセージのために追加

def process_race(race_group):
    """
    1つのレースグループを受け取り、集計結果を返す関数 (通常版)
    """
    num_racers = len(race_group)
    start_time = race_group.iloc[0]['開始時間']
    start_num = race_group.iloc[0]['開催番号']
    race_title = race_group.iloc[0]['レースタイトル'][:1]

    # --- 3着以内モデルの3連単 ---
    race_group_top3 = race_group.sort_values(by='prediction_score_top3', ascending=False)
    try:
        t1 = int(race_group_top3.iloc[0]['車_番'])
        t2 = int(race_group_top3.iloc[1]['車_番'])
        t3 = int(race_group_top3.iloc[2]['車_番'])
        top3_hoketsu = int(race_group_top3.iloc[3]['車_番'])
        nirentan = f'="{t1}-{t2}"'
        sanrentan_top3 = f'="{t1}-{t2}-{t3}"'
    except IndexError:
        nirentan, sanrentan_top3, top3_hoketsu = "N/A", "N/A", "N/A"
    
    # --- 1着モデルの3連単 ---
    race_group_1st = race_group.sort_values(by='prediction_score_1st', ascending=False)
    try:
        w1 = int(race_group_1st.iloc[0]['車_番'])
        w2 = int(race_group_1st.iloc[1]['車_番'])
        w3 = int(race_group_1st.iloc[2]['車_番'])
        w4 = int(race_group_1st.iloc[3]['車_番'])
        nirentan_1st = f'="{w1}-{w2}"'
        sanrentan_1st = f'="{w1}-{w2}-{w3}"'
        st1_hoketsu = w4
    except IndexError:
        sanrentan_1st = "N/A"

    # --- 新しい指標の計算 ---
    prediction_scores = []
    try:
        for i in range(num_racers):
            score = race_group_1st.iloc[i]['prediction_score_1st']
            prediction_scores.append(score)
        avg = sum(prediction_scores) / len(prediction_scores) if len(prediction_scores) > 0 else 0
        p1 = race_group_1st.iloc[0]['prediction_score_1st']
        p2 = race_group_1st.iloc[1]['prediction_score_1st']
        p3 = race_group_1st.iloc[2]['prediction_score_1st']
        p4 = race_group_1st.iloc[3]['prediction_score_1st']
        a_rate, b_rate, c_rate, d_rate = p1, p2, p3, p4
        ct_value = (a_rate - d_rate) / a_rate if a_rate > 0 else 0
        ct_value2 = (a_rate - avg) / a_rate if avg > 0 else 0
        score_value = (a_rate * 50) + (ct_value * 25) + (ct_value2 * 25)
    except IndexError:
        a_rate, b_rate, c_rate, d_rate, ct_value, ct_value2, score_value = [np.nan] * 7

    return pd.Series({
        '開始時間': start_time,
        '開始日目': start_num,
        'レース区分':race_title,
        '2車単': nirentan_1st,
        '3連単_1着': sanrentan_1st,
        '1着_補欠' : st1_hoketsu,
        '3連単_3着以内': sanrentan_top3,
        '3着以内_補欠': top3_hoketsu,
        'A率': a_rate,
        'B率': b_rate,
        'C率': c_rate,
        'D率': d_rate,
        'CT値': ct_value,
        'スコア': score_value,
        '選手数': num_racers
    })

def process_race2(race_group):
    """
    1つのレースグループを受け取り、集計結果を返す関数 (大穴用)
    """
    num_racers = len(race_group)
    start_time = race_group.iloc[0]['開始時間']
    start_num = race_group.iloc[0]['開催番号']
    race_title = race_group.iloc[0]['レースタイトル'][:1]

    # --- 3着以内モデルの3連単 ---
    race_group_top3 = race_group.sort_values(by='prediction_score_top3', ascending=False)
    try:
        t1 = int(race_group_top3.iloc[0]['車_番'])
        t2 = int(race_group_top3.iloc[1]['車_番'])
        t3 = int(race_group_top3.iloc[2]['車_番'])
        t4 = int(race_group_top3.iloc[3]['車_番'])
        nirentan = f'="{t1}-{t2}"'
        # ここでは余分な二重引用符を追加しない
        sanrentan_top3 = f'{t1}-{t2}-{t3}'
        top3_hoketsu = t4
    except IndexError:
        nirentan, sanrentan_top3, top3_hoketsu = "N/A", "N/A", "N/A"
    
    # --- 新しい指標の計算 ---
    prediction_scores = []
    try:
        for i in range(num_racers):
            score = race_group_top3.iloc[i]['prediction_score_top3']
            prediction_scores.append(score)
        avg = sum(prediction_scores) / len(prediction_scores) if len(prediction_scores) > 0 else 0
        p1 = race_group_top3.iloc[0]['prediction_score_top3']
        p2 = race_group_top3.iloc[1]['prediction_score_top3']
        p3 = race_group_top3.iloc[2]['prediction_score_top3']
        p4 = race_group_top3.iloc[3]['prediction_score_top3']
        a_rate, b_rate, c_rate, d_rate = p1, p2, p3, p4
        ct_value = (a_rate - d_rate) / a_rate if a_rate > 0 else 0
        ct_value2 = (a_rate - avg) / a_rate if avg > 0 else 0
        score_value = (a_rate * 50) + (ct_value * 25) + (ct_value2 * 25)
    except IndexError:
        a_rate, b_rate, c_rate, d_rate, ct_value, ct_value2, score_value = [np.nan] * 7

    return pd.Series({
        '開始時間': start_time,
        '開始日目': start_num,
        'レース区分':race_title,
        '3着以内_大穴': sanrentan_top3,
        '3着以内_補欠_大穴': top3_hoketsu,
        '選手数_大穴': num_racers,
        '2車単_大穴': nirentan,
        'A率_大穴': a_rate,
        'B率_大穴': b_rate,
        'C率_大穴': c_rate,
        'D率_大穴': d_rate,
        'CT値_大穴': ct_value,
        'スコア_大穴': score_value
    })

# --- GitHubへアップロードする関数 ---
def upload_to_github(file_list, commit_message, repo_path):
    # (この関数は変更なし)
    try:
        for file_path in file_list:
            subprocess.run(['git', 'add', file_path], check=True, cwd=repo_path)
            print(f"'{file_path}' をステージングしました。")
        subprocess.run(['git', 'commit', '-m', commit_message], check=True, cwd=repo_path)
        print(f"コミットしました: '{commit_message}'")
        subprocess.run(['git', 'push'], check=True, cwd=repo_path)
        print("GitHubへのプッシュが成功しました。")
    except subprocess.CalledProcessError as e:
        print(f"Gitコマンドの実行中にエラーが発生しました: {e}")
    except FileNotFoundError:
        print("エラー: 'git'コマンドが見つかりません。Gitがインストールされ、PATHが通っているか確認してください。")

# '3連単_1着'と'3連単_3着以内'の各列の値をソートする関数
def sort_triplet(triplet_string):
    # (この関数は変更なし)
    if pd.isna(triplet_string):
        return None
    return '-'.join(sorted(triplet_string.split('-'), key=int))

# 新しい条件で抽出するための関数を定義
def check_match(row):
    # (この関数は変更なし)
    try:
        triplet_1st = [int(x) for x in str(row['3連単_1着']).split('-')] if pd.notna(row['3連単_1着']) else []
        hoketsu_1st = [int(row['1着_補欠'])] if pd.notna(row['1着_補欠']) else []
        set_1st = set(triplet_1st + hoketsu_1st)
        triplet_top3 = [int(x) for x in str(row['3連単_3着以内']).split('-')] if pd.notna(row['3連単_3着以内']) else []
        hoketsu_top3 = [int(row['3着以内_補欠'])] if pd.notna(row['3着以内_補欠']) else []
        set_top3 = set(triplet_top3 + hoketsu_top3)
        common_count = len(set_1st.intersection(set_top3))
        if not (common_count == 3):
            return False
    except (ValueError, IndexError):
        return False
    if pd.isna(row['A率']) or pd.isna(row['C率']) or pd.isna(row['D率']):
        return False
    return (row['A率'] >= 0.3) and (row['C率'] >= 0.1) and (row['D率'] <= 0.08)

# --- Main処理 ---
if __name__ == '__main__':

    # --- 大穴CSV出力のセクション ---
    REPO_PATH = r'C:\Users\wolfs\Desktop\keirin-ai'
    INPUT_OANA_CSV = 'keirin_prediction_result_oana.csv'
    OUTPUT_OANA_CSV = 'keirin_oana_summary.csv'

    try:
        df_oana = pd.read_csv(INPUT_OANA_CSV)
    except FileNotFoundError:
        print(f"エラー: '{INPUT_OANA_CSV}' が見つかりません。")
        exit()

    df_oana['レース番号_数値'] = df_oana['レース番号'].str.extract(r'(\d+)').astype(int)
    df_oana_sorted = df_oana.sort_values(
        by=['競輪場', 'レース番号_数値', 'prediction_score_top3'], 
        ascending=[True, True, False]
    )
    race_summary_oana = df_oana_sorted.groupby(['競輪場', 'レース番号', 'レース番号_数値']).apply(process_race2).reset_index()
    final_result_oana = race_summary_oana.sort_values(by='開始時間', ascending=True).drop(columns=['レース番号_数値'])
    final_result_oana.to_csv(OUTPUT_OANA_CSV, encoding='utf-8-sig', index=False)
    print(f"\n集計結果を'{OUTPUT_OANA_CSV}'として保存しました。")
    
    # --- 通常CSV出力のセクション ---
    INPUT_COMBINED_CSV = 'keirin_prediction_result_combined.csv'
    OUTPUT_RACE_CSV = 'keirin_race_summary.csv'

    try:
        df_combined = pd.read_csv(INPUT_COMBINED_CSV)
    except FileNotFoundError:
        print(f"エラー: '{INPUT_COMBINED_CSV}' が見つかりません。")
        exit()
    
    df_combined['レース番号_数値'] = df_combined['レース番号'].str.extract(r'(\d+)').astype(int)
    df_combined_sorted = df_combined.sort_values(
        by=['競輪場', 'レース番号_数値', 'prediction_score_top3'], 
        ascending=[True, True, False]
    )
    race_summary_combined = df_combined_sorted.groupby(['競輪場', 'レース番号', 'レース番号_数値']).apply(process_race).reset_index()
    cols_to_round_combined = ['A率', 'B率', 'C率', 'D率', 'CT値', 'スコア']
    race_summary_combined[cols_to_round_combined] = race_summary_combined[cols_to_round_combined].round(2)
    final_result_combined = race_summary_combined.sort_values(by='開始時間', ascending=True).drop(columns=['レース番号_数値'])

    # 2つのデータフレームを結合
    merge_cols = ['競輪場', 'レース番号']
    
    # マージ前に、Excelの書式用文字列を削除しておく
    final_result_combined['3連単_1着'] = final_result_combined['3連単_1着'].str.replace('="', '').str.replace('"', '')
    final_result_combined['3連単_3着以内'] = final_result_combined['3連単_3着以内'].str.replace('="', '').str.replace('"', '')
    final_result_oana['3着以内_大穴'] = final_result_oana['3着以内_大穴'].str.replace('="', '').str.replace('"', '')

    # 通常版のデータフレームに大穴版のデータを結合
    final_result = pd.merge(final_result_combined, final_result_oana[['競輪場', 'レース番号', '3着以内_大穴', '3着以内_補欠_大穴']], on=merge_cols, how='left')

    # Excelで文字列として認識させるため、再度ダブルクォーテーションを付加
    final_result['3連単_1着'] = '="' + final_result['3連単_1着'].astype(str) + '"'
    final_result['3連単_3着以内'] = '="' + final_result['3連単_3着以内'].astype(str) + '"'
    final_result['3着以内_大穴'] = '="' + final_result['3着以内_大穴'].astype(str) + '"'

    # 結合後の結果を表示
    print("\n--- 結合後の最終結果 ---")
    print(final_result)

    final_result.to_csv(OUTPUT_RACE_CSV, encoding='utf-8-sig', index=False)
    print(f"\n結合結果を'{OUTPUT_RACE_CSV}'として保存しました。")

    # --- 条件抽出処理 ---
    top20_ct = final_result.sort_values(by='CT値', ascending=False).head(20)
    top10_b = top20_ct.sort_values(by='B率', ascending=False).head(10)
    top10_b_sorted = top10_b.sort_values(by='開始時間', ascending=True)
    output_filename2 = 'keirin_race_summary2.csv'
    top10_b_sorted.to_csv(output_filename2, encoding='utf-8-sig', index=False)
    print(f"\n抽出結果を'{output_filename2}'として保存しました。")

    df_for_match = final_result.copy()
    df_for_match['3連単_1着'] = df_for_match['3連単_1着'].str.replace('="', '').str.replace('"', '')
    df_for_match['3連単_3着以内'] = df_for_match['3連単_3着以内'].str.replace('="', '').str.replace('"', '')
    df_for_match['3連単_1着_ソート済'] = df_for_match['3連単_1着'].apply(sort_triplet)
    df_for_match['3連単_3着以内_ソート済'] = df_for_match['3連単_3着以内'].apply(sort_triplet)
    matched_df1 = df_for_match[df_for_match['3連単_1着_ソート済'] == df_for_match['3連単_3着以内_ソート済']].copy()
    matched_df1 = matched_df1.drop(columns=['3連単_1着_ソート済', '3連単_3着以内_ソート済'])
    output_filename3 = 'keirin_race_summary3.csv'
    matched_df1['3連単_1着'] = '="' + matched_df1['3連単_1着'].astype(str) + '"'
    matched_df1['3連単_3着以内'] = '="' + matched_df1['3連単_3着以内'].astype(str) + '"'
    matched_df1.to_csv(output_filename3, encoding='utf-8-sig', index=False)
    print(f"\n抽出結果を'{output_filename3}'として保存しました。")

    matched_df2 = df_for_match[df_for_match.apply(check_match, axis=1)].copy()
    output_filename4 = 'keirin_race_summary4.csv'
    matched_df2['3連単_1着'] = '="' + matched_df2['3連単_1着'].astype(str) + '"'
    matched_df2['3連単_3着以内'] = '="' + matched_df2['3連単_3着以内'].astype(str) + '"'
    matched_df2.to_csv(output_filename4, encoding='utf-8-sig', index=False)
    print(f"\n抽出結果を'{output_filename4}'として保存しました。")
    
    # --- GitHubへのアップロード処理 ---
    print("\n--- GitHubへのアップロードを開始します ---")
    today_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    commit_msg = f"Data update: {today_str}"
    files_to_upload = [OUTPUT_OANA_CSV, OUTPUT_RACE_CSV, output_filename2, output_filename3, output_filename4, "index.html"]
    
    upload_to_github(files_to_upload, commit_msg, REPO_PATH)