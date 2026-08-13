@echo off
cd /d %~dp0

call .venv\Scripts\Activate

chcp 65001

set YYYYMMDD=%date:~0,4%%date:~5,2%%date:~8,2%

echo "結果出力スクリプトを実行します..."
python "C:\Users\wolfs\Desktop\keirin-ai\src\kekka.py"

DEL /F %YYYYMMDD%_updated_keirin_race_summary.csv
DEL /F %YYYYMMDD%_keirin_daily_all_races.csv
DEL /F %YYYYMMDD%_keirin_daily_recommend.csv

COPY /Y updated_keirin_race_summary.csv %YYYYMMDD%_updated_keirin_race_summary.csv
COPY /Y updated_keirin_race_summary.csv bkup_updated_keirin_race_summary.csv

REN keirin_daily_all_races.csv %YYYYMMDD%_keirin_daily_all_races.csv
REN keirin_daily_recommend.csv %YYYYMMDD%_keirin_daily_recommend.csv


REM 3連単結果
python "C:\Users\wolfs\Desktop\keirin-ai\src\export_results_sanrentan.py"

REM 2連複式結果
python "C:\Users\wolfs\Desktop\keirin-ai\src\utils\export_results_nirenpuku_from_daily_pkls.py"

REM 的中判定
python "C:\Users\wolfs\Desktop\keirin-ai\src\eval_hit.py"

REM サマリー作成
python "C:\Users\wolfs\Desktop\keirin-ai\src\analyze_daily.py" --eval_csv keirin_eval_hit.csv --bets_csv keirin_kelly_bets.csv --out_dir .

REM サマリーを日付フォルダに保存
python "C:\Users\wolfs\Desktop\keirin-ai\src\run_pipeline.py"

REM ROIが維持できているか確認
python "C:\Users\wolfs\Desktop\keirin-ai\src\backtest_2shahuku_fixed_rule.py"

echo "すべての処理が完了しました。60秒後シャットダウンします"

REM shutdown /s /t 60
REM pause
pause