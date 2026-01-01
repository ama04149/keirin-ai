# src/train.py
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import train_test_split
import joblib

def train_model(processed_data_path):
    df = pd.read_csv(processed_data_path)
    
    # 特徴量(X)と正解ラベル(y)を定義
    # 例：1着になるかどうかを予測する場合
    X = df.drop(['rank', 'race_id', 'player_id'], axis=1) 
    y = (df['rank'] == 1).astype(int) # 1着なら1, それ以外は0

    # データを学習用とテスト用に分割
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # LightGBMモデルの学習
    model = lgb.LGBMClassifier(objective='binary', random_state=42)
    model.fit(X_train, y_train,
              eval_set=[(X_test, y_test)],
              callbacks=[lgb.early_stopping(10)]) # 性能が改善しなくなったら学習を止める

    # 学習済みモデルを保存
    joblib.dump(model, 'lgbm_model.pkl')
    print("Model training finished and saved as lgbm_model.pkl")
    
    return model

if __name__ == '__main__':
    train_model('data/processed/processed_data.csv')