import pandas as pd

def create_features(raw_data_path):
    print("Loading raw data...")
    df = pd.read_csv(raw_data_path)

    # --- ここから特徴量作成 ---
    
    # 例1: 選手の出場回数を計算
    player_race_count = df.groupby('player_id')['race_id'].transform('count')
    df['player_race_count'] = player_race_count
    
    # 例2: 選手の1着回数を計算し、勝率を算出
    # df.sort_values('race_date', inplace=True) # 日付順に並べ替えが必要な場合
    df['is_win'] = (df['rank'] == 1).astype(int)
    player_win_count = df.groupby('player_id')['is_win'].transform('sum')
    # ゼロ除算を避けるため、出場回数が0の場合は勝率も0にする
    df['player_win_rate'] = (player_win_count / df['player_race_count']).fillna(0)
    
    # is_win列はもう不要なので削除
    df = df.drop('is_win', axis=1)

    # --- 特徴量作成ここまで ---
    print("Feature engineering finished.")
    print("New columns:", df.columns) # 追加後の列名を確認
    
    return df

if __name__ == '__main__':
    processed_data = create_features('data/raw/race_results.csv')
    processed_data.to_csv('data/processed/processed_data.csv', index=False)
    print("Processed data saved.")