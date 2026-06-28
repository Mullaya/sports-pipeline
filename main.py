import sys
import os
from datetime import datetime, timedelta
from collectors.kbo_collector import KBOCollector
from collectors.npb_collector import NPBCollector
from collectors.mlb_collector import MLBCollector
from uploader.github_uploader import GitHubUploader

def run_daily(date: str = None):
    if not date:
        date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

    print(f"===== {date} 수집 시작 =====")

    uploader = GitHubUploader()

    collectors = {
        "KBO": KBOCollector(),
        "NPB": NPBCollector(),
        "MLB": MLBCollector(),
    }

    for league, collector in collectors.items():
        try:
            data = collector.collect_daily(date)

            if data["games"]:
                # 경기 결과 업로드
                uploader.upload_json(data, league, date, "daily")
                print(f"  [{league}] {len(data['games'])}경기 업로드 완료")

                # 선수별 데이터 분리 업로드
                player_data = extract_player_data(data, league, date)
                if player_data["players"]:
                    uploader.upload_json(player_data, league, date, "players")
                    print(f"  [{league}] 선수 데이터 업로드 완료")
            else:
                print(f"  [{league}] 경기 없음")

        except Exception as e:
            print(f"  [{league}] 실패: {e}")

    print(f"===== {date} 완료 =====")

def extract_player_data(data: dict, league: str, date: str) -> dict:
    """경기 데이터에서 선수별 데이터 추출"""
    players = {}

    for game in data["games"]:
        home = game.get("home_team", "")
        away = game.get("away_team", "")

        # 투수 데이터
        for side, team in [("home_pitchers", home), ("away_pitchers", away)]:
            for p in game.get(side, []):
                name = p.get("name", "")
                if not name:
                    continue
                key = f"{team}_{name}"
                if key not in players:
                    players[key] = {
                        "name": name,
                        "team": team,
                        "type": "pitcher",
                        "games": []
                    }
                players[key]["games"].append({
                    "date": date,
                    "opponent": away if side == "home_pitchers" else home,
                    "is_starter": p.get("is_starter", False),
                    "result": p.get("result", ""),
                    "ip": p.get("ip", "0"),
                    "h": p.get("h", 0),
                    "bb": p.get("bb", 0),
                    "k": p.get("k", 0),
                    "er": p.get("er", 0),
                    "era": p.get("era", "0.00"),
                    "pitches": p.get("pitches", 0)
                })

        # 타자 데이터
        for side, team in [("home_batters", home), ("away_batters", away)]:
            for b in game.get(side, []):
                name = b.get("name", "")
                if not name:
                    continue
                key = f"{team}_{name}"
                if key not in players:
                    players[key] = {
                        "name": name,
                        "team": team,
                        "type": "batter",
                        "games": []
                    }
                players[key]["games"].append({
                    "date": date,
                    "opponent": away if side == "home_batters" else home,
                    "order": b.get("order", 0),
                    "position": b.get("position", ""),
                    "ab": b.get("ab", 0),
                    "h": b.get("h", 0),
                    "hr": b.get("hr", 0),
                    "rbi": b.get("rbi", 0),
                    "bb": b.get("bb", 0),
                    "k": b.get("k", 0),
                    "avg": b.get("avg", ".000")
                })

    return {
        "date": date,
        "league": league,
        "players": list(players.values())
    }

if __name__ == "__main__":
    date = sys.argv[1] if len(sys.argv) > 1 else None
    run_daily(date)
