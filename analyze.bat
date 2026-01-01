@echo off
cd /d %~dp0

powershell -Command .\merge.ps1

call .venv\Scripts\Activate

chcp 65001

set YYYYMMDD=%date:~0,4%%date:~5,2%%date:~8,2%

echo "分析スクリプトを実行します..."
python "./src/analyze_and_optimize.py" --input "C:\Users\wolfs\Desktop\MergedWithFileName.csv" --out "C:\Users\wolfs\Desktop\results"

echo "すべての処理が完了しました。"

pause