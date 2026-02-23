import pandas as pd

# 結合するファイル名のリスト
# ('既存ファイル', '追加ファイル', '結合後のファイル名')
files_to_combine = [
    ('race_info2_202106-202512.pkl', 'race_info2_202601-202601.pkl', 'race_info2_202106-202601.pkl'),
    ('race_card3_202106-202512.pkl', 'race_card3_202601-202601.pkl', 'race_card3_202106-202601.pkl'),
    ('race_return_202106-202512.pkl', 'race_return_202601-202601.pkl', 'race_return_202106-202601.pkl')
]

for existing_file, past_file, output_file in files_to_combine:
    try:
        # 既存データと追加データを読み込む
        df_existing = pd.read_pickle(existing_file)
        df_past = pd.read_pickle(past_file)
        
        # 2つのデータフレームを縦に結合
        df_combined = pd.concat([df_existing, df_past], ignore_index=True)
        
        # (念のため) 重複データを削除
        df_combined.drop_duplicates(inplace=True)
        
        # 結合したデータを新しいファイル名で保存
        pd.to_pickle(df_combined, output_file)
        
        print(f"'{existing_file}' と '{past_file}' を結合し、'{output_file}' として保存しました。")
        print(f"結合後のデータ数: {len(df_combined)} 件")
        
    except FileNotFoundError:
        print(f"エラー: ファイル '{existing_file}' または '{past_file}' が見つかりません。")
    except Exception as e:
        print(f"エラーが発生しました: {e}")