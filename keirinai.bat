@echo off
cd /d %~dp0

call .venv\Scripts\Activate

chcp 65001

echo "1つ目のスクリプトを実行します..."
python "C:\Users\wolfs\Desktop\keirin-ai\src\today_race_id_scrape.py"

echo "2つ目のスクリプトを実行します..."
python "C:\Users\wolfs\Desktop\keirin-ai\src\t_race.py"

echo "keirin_prediction_result.csv を処理するスクリプトを実行します..."
python "C:\Users\wolfs\Desktop\keirin-ai\src\analyze_prediction.py"

echo "EVランキングを作成します..."
python "C:\Users\wolfs\Desktop\keirin-ai\src\ev_ranker.py"

echo "すべての処理が完了しました。"

REM pause
REM pause