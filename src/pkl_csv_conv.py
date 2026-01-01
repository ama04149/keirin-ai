import pickle
import pandas as pd

def pkl_to_csv(pkl_filepath, csv_filepath):
    """
    pklファイルをCSVファイルに変換する関数。

    Args:
        pkl_filepath (str): 変換するpklファイルのパス。
        csv_filepath (str): 保存するCSVファイルのパス。
    """
    try:
        with open(pkl_filepath, 'rb') as f:
            data = pickle.load(f)
            print(data)  # デバッグ用にデータを表示
            
    except FileNotFoundError:
        print(f"Error: File not found at {pkl_filepath}")
        return
    except Exception as e:
        print(f"Error loading pickle file: {e}")
        return

    if isinstance(data, (list, tuple)):
        df = pd.DataFrame(data)
    elif isinstance(data, dict):
        df = pd.DataFrame(data)
    else:
         df = pd.DataFrame([data])  # 単一オブジェクトの場合
    
    try:
        df.to_csv(csv_filepath, index=False)
        print(f"Successfully converted {pkl_filepath} to {csv_filepath}")
    except Exception as e:
        print(f"Error saving CSV file: {e}")


# 使用例
home_folder = r"C:\Users\wolfs\Desktop\keirin-ai"  # ホームフォルダのパス
# pklファイルとCSVファイルのパスを指定
pkl_file = home_folder + "./race_card_202505.pkl"  # 変換したいpklファイル名
csv_file = home_folder + "./race_card_202505.pkl.csv"  # 出力したいCSVファイル名
pkl_to_csv(pkl_file, csv_file)