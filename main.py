import sys
import os
from datetime import datetime, timedelta
from collectors.mlb_collector import MLBCollector
from collectors.nhl_collector import NHLCollector
from collectors.nfl_collector import NFLCollector
from collectors.khl_collector import KHLCollector
from collectors.nba_collector import NBACollector
from collectors.kbl_collector import KBLCollector
from collectors.kovo_collector import KOVOCollector
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

    # NHL 수집 (북미 현지 날짜 = MLB와 동일 기준)
    try:
        nhl = NHLCollector()
        nhl_data = nhl.collect_daily(mlb_date)
        if nhl_data["games"]:
            uploader.upload_json(nhl_data, "NHL", mlb_date, "daily")
            print(f"  [NHL] {len(nhl_data['games'])}경기 완료")
        else:
            print(f"  [NHL] 경기 없음")
    except Exception as e:
        print(f"  [NHL] 실패: {e}")

    # 자동 실행일 때만: 최근 며칠 중 파일이 없는 날짜를 재수집 (크론 지연·스킵 대비)
    if not date:
        catch_up(uploader, mlb_date, {"NHL": NHLCollector, "NBA": NBACollector})

    # NFL 수집 (미국 현지 날짜 = MLB와 동일 기준, 경기 있는 날만 파일 생성)
    try:
        nfl = NFLCollector()
        nfl_data = nfl.collect_daily(mlb_date)
        if nfl_data["games"]:
            uploader.upload_json(nfl_data, "NFL", mlb_date, "daily")
            print(f"  [NFL] {len(nfl_data['games'])}경기 완료")
        else:
            print(f"  [NFL] 경기 없음")
    except Exception as e:
        print(f"  [NFL] 실패: {e}")

    # NBA 수집 (미국 현지 날짜 = MLB와 동일 기준)
    try:
        nba = NBACollector()
        nba_data = nba.collect_daily(mlb_date)
        if nba_data["games"]:
            uploader.upload_json(nba_data, "NBA", mlb_date, "daily")
            print(f"  [NBA] {len(nba_data['games'])}경기 완료")
        else:
            print(f"  [NBA] 경기 없음")
    except Exception as e:
        print(f"  [NBA] 실패: {e}")

    # KHL 수집 (모스크바 날짜 = KST 어제, NPB와 동일 기준)
    try:
        khl = KHLCollector()
        khl_data = khl.collect_daily(npb_date)
        if khl_data["games"]:
            uploader.upload_json(khl_data, "KHL", npb_date, "daily")
            print(f"  [KHL] {len(khl_data['games'])}경기 완료")
        else:
            print(f"  [KHL] 경기 없음")
    except Exception as e:
        print(f"  [KHL] 실패: {e}")

    # KBL 수집 (한국 날짜 = KST 어제, NPB와 동일 기준)
    try:
        kbl = KBLCollector()
        kbl_data = kbl.collect_daily(npb_date)
        if kbl_data["games"]:
            uploader.upload_json(kbl_data, "KBL", npb_date, "daily")
            print(f"  [KBL] {len(kbl_data['games'])}경기 완료")
        else:
            print(f"  [KBL] 경기 없음")
    except Exception as e:
        print(f"  [KBL] 실패: {e}")

    # V-리그 남자부(KOVO)·여자부(WKOVO) 수집 (한국 날짜 = KST 어제, 컵대회 포함)
    for league in ("KOVO", "WKOVO"):
        try:
            v_data = KOVOCollector(league).collect_daily(npb_date)
            if v_data["games"]:
                uploader.upload_json(v_data, league, npb_date, "daily")
                print(f"  [{league}] {len(v_data['games'])}경기 완료")
            else:
                print(f"  [{league}] 경기 없음")
        except Exception as e:
            print(f"  [{league}] 실패: {e}")

    if not date:
        catch_up(uploader, npb_date, {"KBL": KBLCollector,
                                      "KOVO": lambda: KOVOCollector("KOVO"),
                                      "WKOVO": lambda: KOVOCollector("WKOVO")})

    # NPB/KBO는 별도 스크래퍼 구성 예정
    print(f"  [NPB] 별도 스크래퍼 구성 예정")
    print(f"  [KBO] Playwright 기반 별도 구성 예정")

    print(f"===== 완료 =====")

CATCH_UP_DAYS = 3


def catch_up(uploader, base_date: str, collectors: dict, days: int = CATCH_UP_DAYS):
    """base_date 이전 N일 중 daily 파일이 없는 날짜를 다시 수집.

    GitHub Actions 크론은 수 시간씩 밀리거나 건너뛰는 일이 있고,
    실행이 KST 자정을 넘기면 대상 날짜가 하루 밀려 그 날짜가 영구 누락된다.
    경기 없는 날은 파일이 안 생기므로 매번 API 1회만 조회하고 넘어간다.
    """
    base = datetime.strptime(base_date, "%Y%m%d")
    for league, cls in collectors.items():
        for i in range(1, days + 1):
            d = (base - timedelta(days=i)).strftime("%Y%m%d")
            if uploader.file_exists(league, d, "daily"):
                continue
            try:
                data = cls().collect_daily(d)
                if data["games"]:
                    uploader.upload_json(data, league, d, "daily")
                    print(f"  [{league}] 누락분 {d} 재수집 {len(data['games'])}경기")
            except Exception as e:
                print(f"  [{league}] 누락분 {d} 재수집 실패: {e}")


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
