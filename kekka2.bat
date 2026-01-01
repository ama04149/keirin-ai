@echo off
cd /d %~dp0

call .venv\Scripts\Activate

chcp 65001

set YYYYMMDD=%date:~0,4%%date:~5,2%%date:~8,2%

echo "結果出力スクリプトを実行します..."
python "C:\Users\wolfs\Desktop\keirin-ai\src\kekka.py"

DEL /F %YYYYMMDD%_updated_keirin_race_summary.csv

REN updated_keirin_race_summary.csv %YYYYMMDD%_updated_keirin_race_summary.csv

echo "すべての処理が完了しました。60秒後シャットダウンします"

REM shutdown /s /t 60
