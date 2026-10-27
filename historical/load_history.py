import sys
import os
import time
from datetime import datetime, timedelta

# 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collectors.mlb_collector import MLBCollector
from collectors.kbo_collector import KBOCollector
from collectors.npb_collector import NPBCollector
from collectors.nhl_collector import NHLCollector
from collectors.nfl_collector import NFLCollector
from collectors.khl_collector import KHLCollector
from collectors.nba_collector import NBACollector
from collectors.kbl_collector import KBLCollector
from collectors.kovo_collector import KOVOCollector
from collectors.flashscore_hockey_collector import FlashscoreHockeyCollector
from uploader.github_uploader import GitHubUploader
from main import extract_player_data

def load_history(league: str, start: str, end: str):
    collectors = {
        "MLB": MLBCollector(),
        "KBO": KBOCollector(),
        "NPB": NPBCollector(),
        "NHL": NHLCollector(),
        "NFL": NFLCollector(),
        "KHL": KHLCollector(),
        "NBA": NBACollector(),
        "KBL": KBLCollector(),
        "KOVO": KOVOCollector("KOVO"),
        "WKOVO": KOVOCollector("WKOVO"),
        "DEL": FlashscoreHockeyCollector("DEL"),
        "CZE": FlashscoreHockeyCollector("CZE"),
        "LIIGA": FlashscoreHockeyCollector("LIIGA"),
        "SHL": FlashscoreHockeyCollector("SHL"),
        # KHL 지난 시즌 백필: KHL 모바일 API는 현재 시즌만 조회되므로 Flashscore 사용, 저장은 KHL 폴더
        "KHL_FS": FlashscoreHockeyCollector("KHL"),
    }

    collector = collectors.get(league)
    if not collector:
        print(f"❌ 알 수 없는 리그: {league}")
        return

    uploader = GitHubUploader()
    folder = "KHL" if league == "KHL_FS" else league

    current = datetime.strptime(start, "%Y%m%d")
    end_dt = datetime.strptime(end, "%Y%m%d")

    success = 0
    fail = 0
    skip = 0

    print(f"===== {league} {start}~{end} 초기적재 시작 =====")

    while current <= end_dt:
        date_str = current.strftime("%Y%m%d")

        # SKIP_EXISTING=1: 이미 적재된 날짜는 건너뛰고 누락분만 채운다
        if os.getenv("SKIP_EXISTING") == "1" and (
                uploader.file_exists(folder, date_str, "historical")
                or uploader.file_exists(folder, date_str, "daily")):
            current += timedelta(days=1)
            continue

        try:
            data = collector.collect_daily(date_str)

            if data["games"]:
                ok = uploader.upload_json(data, folder, date_str, "historical")
                if ok:
                    success += 1
                else:
                    fail += 1

                # NHL/NFL/KHL/NBA/KBL은 선수 기록이 일별 파일에 포함되어 있어 별도 추출 불필요
                player_data = extract_player_data(data, league, date_str) if league not in ("NHL", "NFL", "KHL", "NBA", "KBL", "KOVO", "WKOVO", "DEL", "CZE", "LIIGA", "SHL", "KHL_FS") else {"players": []}
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
        time.sleep(1)

    print(f"\n===== 완료 =====")
    print(f"성공: {success} | 실패: {fail} | 경기없음: {skip}")

if __name__ == "__main__":
    league = sys.argv[1]
    start = sys.argv[2]
    end = sys.argv[3]
    load_history(league, start, end)
