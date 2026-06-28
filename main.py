import sys
from datetime import datetime, timedelta
from collectors.kbo_collector import KBOCollector
from collectors.npb_collector import NPBCollector
from collectors.mlb_collector import MLBCollector
from uploader.drive_uploader import DriveUploader

def run_daily(date: str = None):
    if not date:
        date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

    print(f"===== {date} 수집 시작 =====")

    uploader = DriveUploader()

    collectors = {
        "KBO": KBOCollector(),
        "NPB": NPBCollector(),
        "MLB": MLBCollector(),
    }

    for league, collector in collectors.items():
        try:
            data = collector.collect_daily(date)
            if data["games"]:
                uploader.upload_json(data, league, date, "daily")
                print(f"  [{league}] {len(data['games'])}경기 업로드 완료")
            else:
                print(f"  [{league}] 경기 없음")
        except Exception as e:
            print(f"  [{league}] 실패: {e}")

    print(f"===== {date} 완료 =====")

if __name__ == "__main__":
    date = sys.argv[1] if len(sys.argv) > 1 else None
    run_daily(date)
