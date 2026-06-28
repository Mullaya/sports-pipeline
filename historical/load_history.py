import sys
import time
from datetime import datetime, timedelta

sys.path.append("..")

from collectors.mlb_collector import MLBCollector
from collectors.kbo_collector import KBOCollector
from collectors.npb_collector import NPBCollector
from uploader.github_uploader import GitHubUploader

def load_history(league: str, start: str, end: str):
    """
    league: 'MLB' / 'KBO' / 'NPB'
    start/end: 'YYYYMMDD'
    """
    collectors = {
        "MLB": MLBCollector(),
        "KBO": KBOCollector(),
        "NPB": NPBCollector(),
    }

    collector = collectors.get(league)
    if not collector:
        print(f"❌ 알 수 없는 리그: {league}")
        return

    uploader = GitHubUploader()

    current = datetime.strptime(start, "%Y%m%d")
    end_dt = datetime.strptime(end, "%Y%m%d")

    success = 0
    fail = 0
    skip = 0

    print(f"===== {league} {start}~{end} 초기적재 시작 =====")

    while current <= end_dt:
        date_str = current.strftime("%Y%m%d")

        try:
            data = collector.collect_daily(date_str)

            if data["games"]:
                # 경기 결과
                ok = uploader.upload_json(data, league, date_str, "historical")
                if ok:
                    success += 1
                else:
                    fail += 1

                # 선수 데이터
                from main import extract_player_data
                player_data = extract_player_data(data, league, date_str)
                if player_data["players"]:
                    uploader.upload_json(
                        player_data, league, date_str, "historical_players"
                    )
            else:
                skip += 1

        except Exception as e:
            print(f"  ❌ {date_str} 실패: {e}")
            fail += 1

        current += timedelta(days=1)
        time.sleep(1)  # API 부하 방지

    print(f"\n===== 완료 =====")
    print(f"성공: {success} | 실패: {fail} | 경기없음: {skip}")

if __name__ == "__main__":
    # 사용법: python load_history.py MLB 20240301 20260626
    league = sys.argv[1]
    start = sys.argv[2]
    end = sys.argv[3]
    load_history(league, start, end)
