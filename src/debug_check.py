import pandas as pd
import os

print("--- デバッグ調査を開始します ---")

file_name = 'updated_keirin_race_summary.csv'

if not os.path.exists(file_name):
    print(f"⚠️ エラー: {file_name} が見つかりません。予測を一度実行してから試してください。")
else:
    try:
        # CSVを読み込む
        df = pd.read_csv(file_name)
        print(f"ファイル読み込み成功。総行数: {len(df)}")
        print(f"存在する列名の一覧: {df.columns.tolist()}\n")
        
        # 1. 最初のレースをピックアップして生スコアをそのまま表示
        first_race_id = df['race_id'].iloc[0]
        sample_race = df[df['race_id'] == first_race_id]
        
        print(f"【チェック1】サンプルレース (ID: {first_race_id}) の生スコア:")
        for idx, row in sample_race.iterrows():
            print(f"  車番:{row['車_番']} | 選手名:{row['選手名']} | 得点:{row['競走得点']} | top3スコア:{row.get('prediction_score_top3', '無し')} | 1stスコア:{row.get('prediction_score_1st', '無し')}")
        
        # 2. 全体でのスコア分布を確認
        print("\n【チェック2】データ全体での予測値の分布統計:")
        if 'prediction_score_top3' in df.columns:
            print(f"--- prediction_score_top3 (3着以内モデル) ---")
            print(f"  最大値 (MAX): {df['prediction_score_top3'].max()}")
            print(f"  最小値 (MIN): {df['prediction_score_top3'].min()}")
            print(f"  平均値 (AVG): {df['prediction_score_top3'].mean()}")
        else:
            print("  ⚠️ prediction_score_top3 列がCSVにありません。")
            
        if 'prediction_score_1st' in df.columns:
            print(f"\n--- prediction_score_1st (1着モデル) ---")
            print(f"  最大値 (MAX): {df['prediction_score_1st'].max()}")
            print(f"  最小値 (MIN): {df['prediction_score_1st'].min()}")
            print(f"  平均値 (AVG): {df['prediction_score_1st'].mean()}")
            
    except Exception as e:
        print(f"⚠️ 読み込み中にエラーが発生しました: {e}")

print("\n--- デバッグ調査終了 ---")