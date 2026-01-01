import pandas as pd
import numpy as np
import subprocess # Gitコマンド実行のために追加
import datetime # コミットメッセージのために追加

def process_race(race_group):
    """
    1つのレースグループを受け取り、集計結果を返す関数
    """
    # レースの基本情報を取得
    num_racers = len(race_group)
    # 開始時間を取得（後でソートに使うため）
    start_time = race_group.iloc[0]['開始時間']
    start_num = race_group.iloc[0]['開催番号']
    race_title = race_group.iloc[0]['レースタイトル'][:1]

    # --- 3着以内モデルの3連単 ---
    # prediction_score_top3でソート
    race_group_top3 = race_group.sort_values(by='prediction_score_top3', ascending=False)
    try:
        t1 = int(race_group_top3.iloc[0]['車_番'])
        t2 = int(race_group_top3.iloc[1]['車_番'])
        t3 = int(race_group_top3.iloc[2]['車_番'])
        t4 = int(race_group_top3.iloc[3]['車_番'])
        # ★★★ 修正点1: Excelの日付変換対策 ★★★
        # ="7-2" のように出力することで、Excelに文字列として認識させる
        nirentan = f'="{t1}-{t2}"'
        sanrentan_top3 = f'="{t1}-{t2}-{t3}"'
        top3_hoketsu = t4

    except IndexError:
        nirentan, sanrentan_top3, hoketsu = "N/A", "N/A", "N/A"
    
    # --- 1着モデルの3連単 ---
    # prediction_score_1stでソート
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
            #score = race_group_top3.iloc[i]['prediction_score_top3']
            score = race_group_1st.iloc[i]['prediction_score_1st']
            prediction_scores.append(score)

        if len(prediction_scores) > 0:
            avg = sum(prediction_scores) / len(prediction_scores)
        p1 = race_group_1st.iloc[0]['prediction_score_1st']
        p2 = race_group_1st.iloc[1]['prediction_score_1st']
        p3 = race_group_1st.iloc[2]['prediction_score_1st']
        p4 = race_group_1st.iloc[3]['prediction_score_1st']

        a_rate, b_rate, c_rate, d_rate = p1, p2, p3, p4
        ct_value = (a_rate - d_rate) / a_rate if a_rate > 0 else 0
        ct_value2 = (a_rate - avg) / a_rate if avg > 0 else 0

        # ★★★ 追加点: スコア計算 ★★★
        score_value = (a_rate * 50) + (ct_value * 25) + (ct_value2 * 25)
    except IndexError:
        a_rate, b_rate, c_rate, d_rate, ct_value, ct_value2, score_value = [np.nan] * 7

    # 1行のSeriesとして結果を返す
    return pd.Series({
        '開始時間': start_time,
        '開始日目': start_num,
        'レース区分':race_title,
        '2車単': nirentan_1st,
        '3連単_1着': sanrentan_1st,    # 新しい列を追加
        '1着_補欠' : st1_hoketsu,
        '3連単_3着以内': sanrentan_top3, # 列名を変更
        '3着以内_補欠': top3_hoketsu,
        'A率': a_rate,
        'B率': b_rate,
        'C率': c_rate,
        'D率': d_rate,
        'CT値': ct_value,
        #'CT2値': ct_value2,  # 小数点以下2桁でフォーマット
        'スコア': score_value,  # 小数点以下2桁でフォーマット
        '選手数': num_racers
    })

def process_race2(race_group):
    """
    1つのレースグループを受け取り、集計結果を返す関数
    """
    # レースの基本情報を取得
    num_racers = len(race_group)
    # 開始時間を取得（後でソートに使うため）
    start_time = race_group.iloc[0]['開始時間']
    start_num = race_group.iloc[0]['開催番号']
    race_title = race_group.iloc[0]['レースタイトル'][:1]

    # --- 3着以内モデルの3連単 ---
    # prediction_score_top3でソート
    race_group_top3 = race_group.sort_values(by='prediction_score_top3', ascending=False)
    try:
        t1 = int(race_group_top3.iloc[0]['車_番'])
        t2 = int(race_group_top3.iloc[1]['車_番'])
        t3 = int(race_group_top3.iloc[2]['車_番'])
        t4 = int(race_group_top3.iloc[3]['車_番'])
        # ★★★ 修正点1: Excelの日付変換対策 ★★★
        # ="7-2" のように出力することで、Excelに文字列として認識させる
        nirentan = f'="{t1}-{t2}"'
        sanrentan_top3 = f'="{t1}-{t2}-{t3}"'
        top3_hoketsu = t4

    except IndexError:
        nirentan, sanrentan_top3, hoketsu = "N/A", "N/A", "N/A"
    
    prediction_scores = []
    
    try:
        for i in range(num_racers):
            score = race_group_top3.iloc[i]['prediction_score_top3']
            #score = race_group_1st.iloc[i]['prediction_score_1st']
            prediction_scores.append(score)

        if len(prediction_scores) > 0:
            avg = sum(prediction_scores) / len(prediction_scores)
        p1 = race_group_top3.iloc[0]['prediction_score_top3']
        p2 = race_group_top3.iloc[1]['prediction_score_top3']
        p3 = race_group_top3.iloc[2]['prediction_score_top3']
        p4 = race_group_top3.iloc[3]['prediction_score_top3']

        a_rate, b_rate, c_rate, d_rate = p1, p2, p3, p4
        ct_value = (a_rate - d_rate) / a_rate if a_rate > 0 else 0
        ct_value2 = (a_rate - avg) / a_rate if avg > 0 else 0

        # ★★★ 追加点: スコア計算 ★★★
        score_value = (a_rate * 50) + (ct_value * 25) + (ct_value2 * 25)
    except IndexError:
        a_rate, b_rate, c_rate, d_rate, ct_value, ct_value2, score_value = [np.nan] * 7

    # 1行のSeriesとして結果を返す
    return pd.Series({
        '開始時間': start_time,
        '開始日目': start_num,
        'レース区分':race_title,
        '2車単': nirentan,
        '3着以内_大穴': sanrentan_top3, # 列名を変更
        '3着以内_補欠': top3_hoketsu,
        'A率': a_rate,
        'B率': b_rate,
        'C率': c_rate,
        'D率': d_rate,
        'CT値': ct_value,
        #'CT2値': ct_value2,  # 小数点以下2桁でフォーマット
        'スコア': score_value,  # 小数点以下2桁でフォーマット
        '選手数': num_racers
    })


# --- GitHubへアップロードする関数 ---
def upload_to_github(file_list, commit_message, repo_path):
    """
    指定されたファイルをGitリポジトリに追加、コミット、プッシュする。
    :param file_list: アップロードするファイルのリスト (例: ['file1.csv', 'file2.csv'])
    :param commit_message: コミットメッセージ
    :param repo_path: ローカルのGitリポジトリのパス
    """
    try:
        # ファイルを追加
        for file_path in file_list:
            subprocess.run(['git', 'add', file_path], check=True, cwd=repo_path)
            print(f"'{file_path}' をステージングしました。")

        # コミット
        subprocess.run(['git', 'commit', '-m', commit_message], check=True, cwd=repo_path)
        print(f"コミットしました: '{commit_message}'")

        # プッシュ
        subprocess.run(['git', 'push'], check=True, cwd=repo_path)
        print("GitHubへのプッシュが成功しました。")

    except subprocess.CalledProcessError as e:
        print(f"Gitコマンドの実行中にエラーが発生しました: {e}")
    except FileNotFoundError:
        print("エラー: 'git'コマンドが見つかりません。Gitがインストールされ、PATHが通っているか確認してください。")


# '3連単_1着'と'3連単_3着以内'の各列の値をソートする関数
def sort_triplet(triplet_string):
    """
    ハイフンで区切られた数字の文字列を受け取り、昇順にソートしてハイフンで結合する。
    """

    if pd.isna(triplet_string):
        return None

    return '-'.join(sorted(triplet_string.split('-'), key=int))

# 新しい条件で抽出するための関数を定義
def check_match(row):
    try:
        # '3連単_1着'の文字列をハイフンで分割し、数値のリストに変換
        # NaN値の場合は空のリストを返す
        triplet_1st = [int(x) for x in str(row['3連単_1着']).split('-')] if pd.notna(row['3連単_1着']) else []
        # '1着_補欠'の値をリストに追加
        hoketsu_1st = [int(row['1着_補欠'])] if pd.notna(row['1着_補欠']) else []
        set_1st = set(triplet_1st + hoketsu_1st)

        # '3連単_3着以内'の文字列をハイフンで分割し、数値のリストに変換
        triplet_top3 = [int(x) for x in str(row['3連単_3着以内']).split('-')] if pd.notna(row['3連単_3着以内']) else []
        # '3着以内_補欠'の値をリストに追加
        hoketsu_top3 = [int(row['3着以内_補欠'])] if pd.notna(row['3着以内_補欠']) else []
        set_top3 = set(triplet_top3 + hoketsu_top3)

        # 共通の要素の数を計算
        common_count = len(set_1st.intersection(set_top3))

        # 共通の要素数が3つであることを確認
        if not (common_count == 3):
            return False
        
    except (ValueError, IndexError):
        # 変換エラーやデータが不完全な場合はFalseを返す
        return False
    
    # 次に、新しいA率、C率、D率の条件をチェック
    # NaN値が含まれている場合はFalseを返す
    if pd.isna(row['A率']) or pd.isna(row['C率']) or pd.isna(row['D率']):
        return False
        
    return (row['A率'] >= 0.3) and (row['C率'] >= 0.1) and (row['D率'] <= 0.08)

# 共通の数字が2つだけかどうかをチェックする関数
def check_one_match(row):
    try:
        # '3連単_1着'の数字と'1着_補欠'の数字を結合
        set_1st = set(map(int, row['3連単_1着'].split('-'))).union({int(row['1着_補欠'])})

        # '3連単_3着以内'の数字と'3着以内_補欠'の数字を結合
        set_top3 = set(map(int, row['3連単_3着以内'].split('-'))).union({int(row['3着以内_補欠'])})

        # 共通の要素の数を計算し、2つだけか確認
        common_count = len(set_1st.intersection(set_top3))
        return common_count == 2
    except (ValueError, IndexError):
        # データが不完全な場合はFalse
        return False

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

    # ★★★ 修正点2: レース番号を正しくソートするための準備 ★★★
    # '10R'を10として扱えるように、数値の列を一時的に作成
    df['レース番号_数値'] = df['レース番号'].str.extract(r'(\d+)').astype(int)

    # まず、各レース内で予測スコアが高い順にソートする
    df_sorted = df.sort_values(
        # by=['競輪場', 'レース番号_数値', 'prediction_score_top3'],   # 2026/1/1修正      
        by=['競輪場', 'レース番号_数値', 'prediction_score_1st'], 
        ascending=[True, True, False]
    )
    
    # レースごとに集計処理を実行
    # groupbyのキーから元の'レース番号'（文字列）も残す
    race_summary = df_sorted.groupby(['競輪場', 'レース番号', 'レース番号_数値']).apply(process_race).reset_index()

    cols_to_round = ['A率', 'B率', 'C率', 'D率', 'CT値', 'スコア']# ,'CT2値'
    race_summary[cols_to_round] = race_summary[cols_to_round].round(2)

    # ★★★ 修正点3: 最終的な出力順を開始時間でソート ★★★
    final_result = race_summary.sort_values(by='開始時間', ascending=True)
    
    # 並べ替えに使った一時的な列を削除
    final_result = final_result.drop(columns=['レース番号_数値'])

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

    # 2. その中からB率の上位10件を抽出
    top10_b = top20_ct.sort_values(by='B率', ascending=False).head(10)

    # 3. 開始時間順に昇順ソート
    top10_b_sorted = top10_b.sort_values(by='開始時間', ascending=True)

    # 4. 新しいCSVファイルとして保存
    output_filename2 = 'keirin_race_summary2.csv'
    top10_b_sorted.to_csv(output_filename2, encoding='utf-8-sig', index=False)
    print(f"\n抽出結果を'{output_filename2}'として保存しました。")

   
    # CSVファイルを読み込む
    df = pd.read_csv('keirin_race_summary.csv')

    # Excelで文字列として扱われるように入っている余分な文字を削除する
    df['3連単_1着'] = df['3連単_1着'].str.replace('="', '').str.replace('"', '')
    df['3連単_3着以内'] = df['3連単_3着以内'].str.replace('="', '').str.replace('"', '')

    # 新しいソート済みの列を作成
    df['3連単_1着_ソート済'] = df['3連単_1着'].apply(sort_triplet)
    df['3連単_3着以内_ソート済'] = df['3連単_3着以内'].apply(sort_triplet)

    # ソート済みの両方の列が一致するレコードを抽出
    matched_df = df[df['3連単_1着_ソート済'] == df['3連単_3着以内_ソート済']].copy()
    
    # 余分な列を削除
    matched_df = matched_df.drop(columns=['3連単_1着_ソート済', '3連単_3着以内_ソート済'])

    # 結果を表示
    print("--- 3連単_1着と3連単_3着以内のソート後が一致したレコード ---")
    print(matched_df) 
    # 新しいCSVファイルとして保存

    output_filename3 = 'keirin_race_summary3.csv'

    # Excelで文字列として認識させるため、再度ダブルクォーテーションを付加
    matched_df['3連単_1着'] = '="' + matched_df['3連単_1着'].astype(str) + '"'
    matched_df['3連単_3着以内'] = '="' + matched_df['3連単_3着以内'].astype(str) + '"'
    matched_df.to_csv(output_filename3, encoding='utf-8-sig', index=False)
    print(f"\n抽出結果を'{output_filename3}'として保存しました。")

        # CSVファイルを読み込む
    df = pd.read_csv('keirin_race_summary.csv')

    # Excelで文字列として扱われるように入っている余分な文字を削除する
    df['3連単_1着'] = df['3連単_1着'].str.replace('="', '').str.replace('"', '')
    df['3連単_3着以内'] = df['3連単_3着以内'].str.replace('="', '').str.replace('"', '')

    # --- 新しい抽出条件 ---
    # 1. レース区分が "チ" と "ガ" を除く
    # 2. スコアが 57.5 ～ 62.5
    filtered_df = df[
        (~df['レース区分'].isin(['チ', 'ガ'])) &
        (df['スコア'] >= 57.5) &
        (df['スコア'] <= 62.5)
    ].copy()

    print("--- 条件に一致したレコード（レース区分=チ & スコア範囲） ---")
    print(filtered_df)

    # 新しいCSVファイルとして保存
    output_filename4 = 'keirin_race_summary4.csv'

    # Excelで文字列として認識させるため、再度ダブルクォーテーションを付加
    filtered_df['3連単_1着'] = '="' + filtered_df['3連単_1着'].astype(str) + '"'
    filtered_df['3連単_3着以内'] = '="' + filtered_df['3連単_3着以内'].astype(str) + '"'

    filtered_df.to_csv(output_filename4, encoding='utf-8-sig', index=False)
    print(f"\n抽出結果を'{output_filename4}'として保存しました。")


    # --- GitHubへのアップロード処理 ---
    print("\n--- GitHubへのアップロードを開始します ---")
    today_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    commit_msg = f"Data update: {today_str}"
    files_to_upload = [OUTPUT_CSV, output_filename2, output_filename3, output_filename4, "index.html"] 
    
    upload_to_github(files_to_upload, commit_msg, REPO_PATH)