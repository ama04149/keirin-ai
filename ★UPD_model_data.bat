@echo off
cd /d %~dp0

call .venv\Scripts\Activate

chcp 65001

REM ********************************************************************
REM 1_race_id_scrape.pyの月数を変更した後に実行すること！
REM 5_combine_data.pyのマージファイル名を修正した後に実行すること！
REM 8_cumulative_ready.pyのマージファイル名を修正した後に実行すること！
REM ********************************************************************


echo "1つ目のスクリプトを実行します..."
python "C:\Users\wolfs\Desktop\keirin-ai\src\1_race_id_scrape.py"

echo "2つ目のスクリプトを実行します..."
python "C:\Users\wolfs\Desktop\keirin-ai\src\2_race_data_scrape.py"

echo "3つ目のスクリプトを実行します..."
python "C:\Users\wolfs\Desktop\keirin-ai\src\3_back_sabun.py"

echo "4つ目のスクリプトを実行します..."
python "C:\Users\wolfs\Desktop\keirin-ai\src\4_def_line_kyoudo.py"

echo "5_combine_data.pyのマージ対象ファイル名称を確認してください..."
REM pause

echo "5つ目のスクリプトを実行します..."
python "C:\Users\wolfs\Desktop\keirin-ai\src\5_combine_data.py"

echo "8_cumulative_ready.pyの入力ファイル名称を確認してください..."
REM pause

echo "6つ目のスクリプトを実行します..."
python "C:\Users\wolfs\Desktop\keirin-ai\src\8_cumulative_ready.py"

echo "7つ目のスクリプトを実行します..."
python "C:\Users\wolfs\Desktop\keirin-ai\src\9_new_player.py"

echo "8つ目のスクリプトを実行します..."
REM python "C:\Users\wolfs\Desktop\keirin-ai\src\6_pycaret_keirin.py"

echo "9つ目のスクリプトを実行します..."
python "C:\Users\wolfs\Desktop\keirin-ai\src\train_by_class_model.py"

echo "10つ目のスクリプトを実行します..."
python "C:\Users\wolfs\Desktop\keirin-ai\src\7_train_1st_place_challenge_model.py"

echo "すべての処理が完了しました。"

pause