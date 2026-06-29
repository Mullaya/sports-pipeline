import sys
import os
from datetime import datetime, timedelta
from collectors.mlb_collector import MLBCollector
from uploader.github_uploader import GitHubUploader

def get_dates(manual_date: str = None, manual_mlb_date: str = None):
    kst_now = datetime.utcnow() + timedelta(hours=9)

    if manual_date and manual_mlb_date:
        return manual_date, manual_mlb_date

    if manual_date:
        # 수동 날짜 입력 시 MLB는 같은 날짜
        return manual_date, manual_date

    # 자동 실행 시
    # NPB: KST 어제
    npb_date = (kst_now - timedelta(days=1)).strftime("%Y%m%d")
    # MLB: KST 오늘 -1일 (미국 어제 경기)
    mlb_date = (kst_now - timedelta(days=1)).strftime("%Y%m%d")

    return npb_date, mlb_date

def run_daily(date: str = None, mlb_date: str = None):
    npb_date, mlb_date = get_dates(date, mlb_date)

    print(f"===== 수집 시작 =====")
    print(f"NPB/KBO 날짜: {npb_date} (KST 기준)")
    print(f"MLB 날짜: {mlb_date} (미국 현지 기준)")

    uploader = GitHubUploader()

    # MLB 수집
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

    # NPB/KBO는 별도 스크래퍼 구성 예정
    print(f"  [NPB] 별도 스크래퍼 구성 예정")
    print(f"  [KBO] Playwright 기반 별도 구성 예정")

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
