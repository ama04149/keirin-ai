from pathlib import Path
from datetime import datetime
import shutil

# =========================
# 🔥 コピー元ファイル固定
# =========================
SOURCE_FILES = [
    "keirin_ev_tickets.csv",
    "keirin_ev_race_rank.csv",
    "keirin_kelly_bets.csv",
    "keirin_results_sanrentan.csv",
    "race_summary.csv",
    "daily_summary.csv",
]

# =========================
# 設定
# =========================
USE_TIME_SUBFOLDER = False  # Trueにすると時刻フォルダも作る


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def main():

    # 🔥 実行日を自動取得
    ymd = datetime.now().strftime("%Y%m%d")

    if USE_TIME_SUBFOLDER:
        time_str = datetime.now().strftime("%H%M%S")
        out_dir = Path("data") / "daily" / ymd / time_str
    else:
        out_dir = Path("data") / "daily" / ymd

    ensure_dir(out_dir)

    for file_path in SOURCE_FILES:
        src = Path(file_path)
        if src.exists():
            dst = out_dir / src.name
            shutil.copy2(src, dst)
            print(f"[OK] {src.name} -> {dst}")
        else:
            print(f"[WARN] 見つかりません: {src}")

    print(f"\n保存先フォルダ: {out_dir}")


if __name__ == "__main__":
    main()