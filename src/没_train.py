# src/train.py (修正後の正しいコード)
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import train_test_split
import joblib

def train_model(processed_data_path):
    print("Loading processed data...")
    df = pd.read_csv(processed_data_path)

    # 特徴量(X)と正解ラベル(y)を定義
    # 例：1着になるかどうかを予測する場合
    # ※ご自身のコードに合わせて列名は調整してください
    X = df.drop(['rank', 'race_id', 'player_id'], axis=1, errors='ignore') 
    y = (df['rank'] == 1).astype(int) # 1着なら1, それ以外は0

    # データを学習用とテスト用に分割
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    print("Training model...")
    # LightGBMモデルの学習
    model = lgb.LGBMClassifier(objective='binary', random_state=42)
    model.fit(X_train, y_train,
              eval_set=[(X_test, y_test)],
              callbacks=[lgb.early_stopping(10, verbose=False)]) # verbose=Falseで途中経過の表示を減らす

    # 学習済みモデルを保存
    model_filename = 'lgbm_model.pkl'
    joblib.dump(model, model_filename)
    print(f"Model training finished and saved as {model_filename}")

    return model

if __name__ == '__main__':
    # このスクリプトが直接実行された時にtrain_model関数を呼び出す
    train_model('data/processed/processed_data.csv')