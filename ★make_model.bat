@echo off
cd /d %~dp0

call .venv\Scripts\Activate

chcp 65001

echo "1つ目のスクリプトを実行します..."
python "C:\Users\wolfs\Desktop\keirin-ai\src\train_by_class_model.py"

echo "2つ目のスクリプトを実行します..."
python "C:\Users\wolfs\Desktop\keirin-ai\src\7_train_1st_place_challenge_model.py"

echo "すべての処理が完了しました。"

pause