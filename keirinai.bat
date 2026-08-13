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

REM echo "EVランキングを作成します..."
REM python "C:\Users\wolfs\Desktop\keirin-ai\src\ev_ranker.py"

REM echo "EVランキング（２車複）を作成します..."
REM python "C:\Users\wolfs\Desktop\keirin-ai\src\ev_ranker_2shahuku.py"

echo "すべての処理が完了しました。"

pause