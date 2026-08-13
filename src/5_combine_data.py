import pandas as pd

# 結合するファイル名のリスト
# ('既存ファイル', '追加ファイル', '結合後のファイル名')
files_to_combine = [
    ('race_info2_202106-202601.pkl', 'race_info2_202604-202606.pkl', 'race_info2_202106-202606.pkl'),
    ('race_card3_202106-202601.pkl', 'race_card3_202604-202606.pkl', 'race_card3_202106-202606.pkl'),
    ('race_return_202106-202601.pkl', 'race_return_202604-202606.pkl', 'race_return_202106-202606.pkl')
]

for existing_file, past_file, output_file in files_to_combine:
    try:
        df_existing = pd.read_pickle(existing_file)
        df_past = pd.read_pickle(past_file)

        # ignore_index=True を外し、race_idインデックスを保持したまま結合
        df_combined = pd.concat([df_existing, df_past])

        # 念のため：内容が完全一致する重複行だけを除去（インデックスは巻き込まない）
        df_combined = df_combined[~df_combined.duplicated(keep='first')]

        pd.to_pickle(df_combined, output_file)
        print(f"'{existing_file}' と '{past_file}' を結合し、'{output_file}' として保存しました。")
        print(f"結合後のデータ数: {len(df_combined)} 件（インデックス保持済み）")

    except FileNotFoundError:
        print(f"エラー: ファイル '{existing_file}' または '{past_file}' が見つかりません。")
    except Exception as e:
        print(f"エラーが発生しました: {e}")