import schedule
import subprocess
import time
from datetime import datetime, timedelta


def run_batch():
    # 어제 날짜 생성 (T-1)
    date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"Running batch for date: {date}")

    subprocess.run([
        "python",
        "-m",
        "app.batch.batch_main",
        "--date",
        date
    ])

# 매일 03:00 실행
schedule.every().day.at("03:00").do(run_batch)

print("Batch scheduler started...")

while True:
    schedule.run_pending()
    time.sleep(1)