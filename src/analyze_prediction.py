import pandas as pd
import numpy as np
import subprocess # Gitコマンド実行のために追加
import datetime # コミットメッセージのために追加

def process_race(race_group):
    """
    1つのレースグループを受け取り、集計結果を返す関数
    """
    num_racers = len(race_group)
    start_time = race_group.iloc[0]['開始時間']
    start_num = race_group.iloc[0]['開催番号']
    race_title = str(race_group.iloc[0]['レースタイトル'])[:1]

    # --- 3着以内モデルの3連単 ---
    race_group_top3 = race_group.sort_values(by='prediction_score_top3', ascending=False)
    try:
        t1 = int(race_group_top3.iloc[0]['車_番'])
        t2 = int(race_group_top3.iloc[1]['車_番'])
        t3 = int(race_group_top3.iloc[2]['車_番'])
        sanrentan_top3 = f'="{t1}-{t2}-{t3}"'
        
        remaining_cars_top3 = [str(int(x)) for x in race_group_top3['車_番'].iloc[3:].tolist()]
        if remaining_cars_top3:
            top3_hoketsu = f'="{ "-".join(remaining_cars_top3) }"'
        else:
            top3_hoketsu = ""
    except Exception:
        sanrentan_top3, top3_hoketsu = "N/A", "N/A"
    
    # --- 1着モデルの3連単 ---
    race_group_1st = race_group.sort_values(by='prediction_score_1st', ascending=False)
    try:
        w1 = int(race_group_1st.iloc[0]['車_番'])
        w2 = int(race_group_1st.iloc[1]['車_番'])
        w3 = int(race_group_1st.iloc[2]['車_番'])
        nirentan_1st = f'="{w1}-{w2}"'
        sanrentan_1st = f'="{w1}-{w2}-{w3}"'
        
        remaining_cars_1st = [str(int(x)) for x in race_group_1st['車_番'].iloc[3:].tolist()]
        if remaining_cars_1st:
            st1_hoketsu = f'="{ "-".join(remaining_cars_1st) }"'
        else:
            st1_hoketsu = ""
    except Exception:
        nirentan_1st, sanrentan_1st, st1_hoketsu = "N/A", "N/A", "N/A"

    # --- 新しい指標・各率（A率〜I率）の計算 ---
    scores_sorted = race_group_1st['prediction_score_1st'].tolist()
    
    rate_labels = ['A率', 'B率', 'C率', 'D率', 'E率', 'F率', 'G率', 'H率', 'I率']
    rates_dict = {}
    for i, label in enumerate(rate_labels):
        if i < len(scores_sorted):
            rates_dict[label] = round(scores_sorted[i], 2)
        else:
            rates_dict[label] = ""

    try:
        a_rate = scores_sorted[0] if len(scores_sorted) > 0 else 0
        b_rate = scores_sorted[1] if len(scores_sorted) > 1 else 0
        c_rate = scores_sorted[2] if len(scores_sorted) > 2 else 0
        d_rate = scores_sorted[3] if len(scores_sorted) > 3 else (scores_sorted[-1] if len(scores_sorted) > 0 else 0)
        avg = sum(scores_sorted) / len(scores_sorted) if len(scores_sorted) > 0 else 0

        ct_value = (a_rate - d_rate) / a_rate if a_rate > 0 else 0
        ct_value2 = (a_rate - avg) / a_rate if avg > 0 else 0
        score_value = (a_rate * 50) + (ct_value * 25) + (ct_value2 * 25)
    except Exception:
        ct_value, score_value = 0, 0

    res_dict = {
        '開始時間': start_time,
        '開始日目': start_num,
        'レース区分': race_title,
        '2車単': nirentan_1st,
        '3連単_1着': sanrentan_1st,
        '1着_補欠': st1_hoketsu,
        '3連単_3着以内': sanrentan_top3,
        '3着以内_補欠': top3_hoketsu,
    }
    
    # A率〜I率の格納
    res_dict.update(rates_dict)
    
    res_dict.update({
        'CT値': round(ct_value, 2),
        'スコア': round(score_value, 2),
        '選手数': num_racers
    })

    return pd.Series(res_dict)


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


# --- GitHubへアップロードする関数 ---
def upload_to_github(file_list, commit_message, repo_path):
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
    if pd.isna(triplet_string):
        return None
    return '-'.join(sorted(triplet_string.split('-'), key=int))


# --- Main処理 ---
if __name__ == '__main__':
    # --- この部分を設定してください ---
    REPO_PATH = r'C:\Users\wolfs\Desktop\keirin-ai' # ローカルリポジトリの絶対パス
    INPUT_CSV = 'keirin_prediction_result_combined.csv'
    OUTPUT_CSV = 'keirin_race_summary.csv'
    # --------------------------------

    try:
        df = pd.read_csv(INPUT_CSV)
    except FileNotFoundError:
        print(f"エラー: '{INPUT_CSV}' が見つかりません。")
        exit()

    # レース番号を正しくソートするための準備
    df['レース番号_数値'] = df['レース番号'].str.extract(r'(\d+)').astype(int)

    # 予測スコアが高い順にソート
    df_sorted = df.sort_values(
        by=['競輪場', 'レース番号_数値', 'prediction_score_1st'], 
        ascending=[True, True, False]
    )
    
    # レースごとに集計処理を実行
    race_summary = df_sorted.groupby(['競輪場', 'レース番号', 'レース番号_数値']).apply(process_race).reset_index()

    # 最終的な出力順を開始時間でソート
    final_result = race_summary.sort_values(by='開始時間', ascending=True)
    final_result = final_result.drop(columns=['レース番号_数値'])

    # ★★★ ① 新・運用ロジックの判定結果を追加 ★★★
    final_result['運用判定'] = final_result.apply(judge_operation_logic, axis=1)

    # 列順序を明確に整理
    ordered_cols = [
        '競輪場', 'レース番号', '開始時間', '開始日目', 'レース区分', 
        '2車単', '3連単_1着', '1着_補欠', '3連単_3着以内', '3着以内_補欠',
        'A率', 'B率', 'C率', 'D率', 'E率', 'F率', 'G率', 'H率', 'I率', 
        'CT値', 'スコア', '運用判定', '選手数'
    ]
    # 存在する列のみ取得しソート
    ordered_cols = [c for c in ordered_cols if c in final_result.columns]
    final_result = final_result[ordered_cols]

    # 結果を表示
    print("--- レース毎の集計結果 (開始時間順) ---")
    print(final_result)

    # 新しいCSVファイルとして保存
    output_filename = 'keirin_race_summary.csv'
    final_result.to_csv(output_filename, encoding='utf-8-sig', index=False)
    print(f"\n集計結果を'{output_filename}'として保存しました。")

    # --- 条件抽出処理 ---
    # 1. CT値の上位20件を抽出
    top20_ct = final_result.sort_values(by='CT値', ascending=False).head(20)

    # 2. その中からB率の上位10件を抽出（B率が数値化可能な場合の考慮）
    top20_ct['B率_num'] = pd.to_numeric(top20_ct['B率'], errors='coerce').fillna(0)
    top10_b = top20_ct.sort_values(by='B率_num', ascending=False).head(10).drop(columns=['B率_num'])

    # 3. 開始時間順に昇順ソート
    top10_b_sorted = top10_b.sort_values(by='開始時間', ascending=True)

    # 4. 新しいCSVファイルとして保存
    output_filename2 = 'keirin_race_summary2.csv'
    top10_b_sorted.to_csv(output_filename2, encoding='utf-8-sig', index=False)
    print(f"\n抽出結果を'{output_filename2}'として保存しました。")

   
    # keirin_race_summary3.csv の抽出（ソート後一致レコード）
    df_summary3 = final_result.copy()
    
    # 文字列クレンジング（＝や"の除去）
    temp_1st = df_summary3['3連単_1着'].astype(str).str.replace('="', '').str.replace('"', '')
    temp_top3 = df_summary3['3連単_3着以内'].astype(str).str.replace('="', '').str.replace('"', '')

    df_summary3['3連単_1着_ソート済'] = temp_1st.apply(sort_triplet)
    df_summary3['3連単_3着以内_ソート済'] = temp_top3.apply(sort_triplet)

    matched_df = df_summary3[df_summary3['3連単_1着_ソート済'] == df_summary3['3連単_3着以内_ソート済']].copy()
    matched_df = matched_df.drop(columns=['3連単_1着_ソート済', '3連単_3着以内_ソート済'])

    output_filename3 = 'keirin_race_summary3.csv'
    matched_df.to_csv(output_filename3, encoding='utf-8-sig', index=False)
    print(f"\n抽出結果を'{output_filename3}'として保存しました。")


    # ★★★ ② 買い目あり（見送り以外）のレコードのみを抽出して keirin_race_summary4.csv 出力 ★★★
    filtered_df = final_result[final_result['運用判定'] != '見送り'].copy()

    print("--- 運用判定で買い目と判定されたレコード (見送り除外) ---")
    print(filtered_df)

    output_filename4 = 'keirin_race_summary4.csv'
    filtered_df.to_csv(output_filename4, encoding='utf-8-sig', index=False)
    print(f"\n買い目抽出結果を'{output_filename4}'として保存しました。")

    output_filename5 = 'updated_keirin_race_summary.csv'

    # --- GitHubへのアップロード処理 ---
    print("\n--- GitHubへのアップロードを開始します ---")
    today_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    commit_msg = f"Data update: {today_str}"
    files_to_upload = [INPUT_CSV, OUTPUT_CSV, output_filename2, output_filename3, output_filename4, output_filename5, "index.html"] 
    
    upload_to_github(files_to_upload, commit_msg, REPO_PATH)