import sys
import os
from datetime import datetime, timedelta
from collectors.npb_collector import NPBCollector
from collectors.mlb_collector import MLBCollector
from uploader.github_uploader import GitHubUploader

def get_dates():
    """
    KST 기준 어제 날짜 계산
    MLB는 KST -1일 추가 적용 (시차 보정)
    """
    kst_yesterday = (datetime.utcnow() + timedelta(hours=9) - timedelta(days=1))
    
    # NPB/KBO: KST 어제
    base_date = kst_yesterday.strftime("%Y%m%d")
    
    # MLB: KST 어제 = 미국 기준 그제 경기
    # KST 06:00 이후면 미국 전날 경기 종료 확인 가능
    mlb_date = (kst_yesterday - timedelta(days=1)).strftime("%Y%m%d")
    
    return base_date, mlb_date

def run_daily(date: str = None, mlb_date: str = None):
    if not date:
        date, mlb_date = get_dates()
    if not mlb_date:
        mlb_date = (datetime.strptime(date, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")

    print(f"===== 수집 시작 =====")
    print(f"NPB 날짜: {date} (KST 기준)")
    print(f"MLB 날짜: {mlb_date} (미국 현지 기준)")

    uploader = GitHubUploader()

    # NPB
    try:
        npb = NPBCollector()
        data = npb.collect_daily(date)
        if data["games"]:
            uploader.upload_json(data, "NPB", date, "daily")
            player_data = extract_player_data(data, "NPB", date)
            if player_data["players"]:
                uploader.upload_json(player_data, "NPB", date, "players")
            print(f"  [NPB] {len(data['games'])}경기 완료")
        else:
            print(f"  [NPB] 경기 없음")
    except Exception as e:
        print(f"  [NPB] 실패: {e}")

    # MLB (시차 보정 날짜)
    try:
        mlb = MLBCollector()
        data = mlb.collect_daily(mlb_date)
        if data["games"]:
            uploader.upload_json(data, "MLB", mlb_date, "daily")
            player_data = extract_player_data(data, "MLB", mlb_date)
            if player_data["players"]:
                uploader.upload_json(player_data, "MLB", mlb_date, "players")
            print(f"  [MLB] {len(data['games'])}경기 완료")
        else:
            print(f"  [MLB] 경기 없음")
    except Exception as e:
        print(f"  [MLB] 실패: {e}")

    print(f"===== 완료 =====")

def extract_player_data(data: dict, league: str, date: str) -> dict:
    players = {}

    for game in data["games"]:
        home = game.get("home_team", "")
        away = game.get("away_team", "")

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
    if len(sys.argv) == 3:
        run_daily(sys.argv[1], sys.argv[2])
    elif len(sys.argv) == 2:
        run_daily(sys.argv[1])
    else:
        run_daily()
