"""V-리그(KOVO 남자부·WKOVO 여자부) 대체 수집 — Flashscore 피드
(네이버 API가 GitHub Actions IP에서 응답하지 않을 때 사용, KBL 대체 수집과 같은 방식)

2026-10-24 무렵부터 api-gw.sports.naver.com 이 Actions 러너에서 읽기 시간 초과로 막혀
V-리그 일별 파일이 끊겼다. Flashscore는 Actions에서 정상 응답한다 (2026-11-05 진단).

기존 네이버 기반 일별 파일과 같은 스키마로 만든다.
- 팀명·팀코드: 네이버 표기(예: "대한항공" / "1001")로 변환해 기존 데이터·통계와 이어지게 함
- 날짜: 한국 시간(KST) 경기일
- 세트 스코어, 세트별 점수, 총 득점, 세트 수 → 점수 핸디·총점 언오버·세트 수 판정에 충분
- 팀 스탯(공격·블로킹·리시브 등)·선수 스탯은 Flashscore 배구 피드에 없어 빈 값
- 정규리그·포스트시즌(volleyball-league[-women])과 컵대회(kovo-cup[-women])를 함께 조회
  (컵대회 페이지는 시즌 URL이 없어 최신 대회만 조회됨)
- game_id: "fs_" + Flashscore 경기 ID (네이버 ID와 겹치지 않음)
"""
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from collectors.flashscore_hockey_collector import FlashscoreHockeyCollector, LEAGUES, season_years

KST = ZoneInfo("Asia/Seoul")

LEAGUES.setdefault("KOVO_FS", {"path": "volleyball/south-korea/volleyball-league", "country": "106",
                               "tournament": "p2SkCHXs", "tz": "Asia/Seoul"})
LEAGUES.setdefault("WKOVO_FS", {"path": "volleyball/south-korea/volleyball-league-women", "country": "106",
                                "tournament": "SAk2Byml", "tz": "Asia/Seoul"})
LEAGUES.setdefault("KOVO_CUP_FS", {"path": "volleyball/south-korea/kovo-cup", "country": "106",
                                   "tournament": "vVd2RMKO", "tz": "Asia/Seoul", "season_in_url": False})
LEAGUES.setdefault("WKOVO_CUP_FS", {"path": "volleyball/south-korea/kovo-cup-women", "country": "106",
                                    "tournament": "phagj6cP", "tz": "Asia/Seoul", "season_in_url": False})

SOURCES = {"KOVO": ("KOVO_FS", "KOVO_CUP_FS"), "WKOVO": ("WKOVO_FS", "WKOVO_CUP_FS")}

# Flashscore 팀명(소문자) 키워드 → (네이버 팀명, 팀코드). 위에서부터 먼저 맞는 것 사용
TEAMS = {
    "KOVO": [
        (("kal", "jumbos", "korean air"), ("대한항공", "1001")),
        (("samsung", "blue fangs", "bluefangs"), ("삼성화재", "1002")),
        (("kb ", "kb stars", "insurance"), ("KB손해보험", "1004")),
        (("hyundai", "skywalkers"), ("현대캐피탈", "1005")),
        (("kepco", "vixtorm"), ("한국전력", "1006")),
        ((" ok ", "okman", "ok savings"), ("OK저축은행", "1008")),
        (("woori", "wibee"), ("우리카드", "1009")),
    ],
    "WKOVO": [
        (("hillstate", "e&c"), ("현대건설", "2001")),
        (("expressway", "hi-pass"), ("한국도로공사", "2002")),
        (("jkj", "jung kwan jang", "red sparks", "kgc"), ("정관장", "2003")),
        (("hungkuk", "heungkuk", "pink spiders"), ("흥국생명", "2004")),
        (("gs caltex", "kixx"), ("GS칼텍스", "2005")),
        (("ibk", "altos"), ("IBK기업은행", "2006")),
        (("soop", "pepper"), ("SOOP", "2008")),
    ],
}

# 세트별 점수 필드 (홈, 원정)
SET_KEYS = (("BA", "BB"), ("BC", "BD"), ("BE", "BF"), ("BG", "BH"), ("BI", "BJ"))


def _int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default


def team_info(league: str, raw: str):
    key = f" {raw.lower()} "
    for words, info in TEAMS[league]:
        if any(w in key for w in words):
            return info
    return None


def _game_type(src: str, za: str, er: str) -> str:
    if "CUP" in src:
        return "CUP"
    z, r = (za or "").lower(), (er or "").lower()
    if "all-star" in z or "all star" in z:
        return "ALLSTAR"
    if "play off" in z or "playoff" in z or "play-off" in z:
        if r == "final" or r.startswith("final"):
            return "FINAL"
        return "PO"
    return "REG"


def build_game(league: str, src: str, rec: dict) -> dict:
    hi, ai = team_info(league, rec.get("AE", "")), team_info(league, rec.get("AF", ""))
    hs, as_ = _int(rec.get("AG")), _int(rec.get("AH"))
    sets = []
    for i, (hk, ak) in enumerate(SET_KEYS, 1):
        if hk not in rec and ak not in rec:
            continue
        h, a = _int(rec.get(hk)), _int(rec.get(ak))
        if h == 0 and a == 0:
            continue
        sets.append({"set": i, "home": h, "away": a})
    home_pts = sum(s["home"] for s in sets)
    away_pts = sum(s["away"] for s in sets)
    start = datetime.fromtimestamp(_int(rec.get("AD")), timezone.utc).astimezone(KST)
    gtype = _game_type(src, rec.get("ZA"), rec.get("ER"))
    return {
        "game_id": "fs_" + rec["AA"],
        "game_type": gtype,
        "round_code": "flashscore",
        "round_info": rec.get("ER") or rec.get("ZA", ""),
        "round": None,
        "group": None,
        "season": None if gtype == "CUP" else season_years(start.strftime("%Y%m%d"))[0],
        "league_code": None,
        "start_kst": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "venue": "",
        "home_team": hi[0] if hi else rec.get("AE", ""),
        "away_team": ai[0] if ai else rec.get("AF", ""),
        "home_code": hi[1] if hi else "",
        "away_code": ai[1] if ai else "",
        "neutral": gtype == "CUP",
        "series_game_no": None,
        "home_sets": hs,
        "away_sets": as_,
        "set_score": f"{hs}-{as_}",
        "set_count": len(sets) or (hs + as_),
        "full_set": len(sets) == 5,
        "winner": "HOME" if hs > as_ else "AWAY",
        "home_points": home_pts,
        "away_points": away_pts,
        "total_points": home_pts + away_pts,
        "margin_points_home": home_pts - away_pts,
        "set_scores": sets,
        "home_stats": {},
        "away_stats": {},
        "home_players": [],
        "away_players": [],
    }


class FlashscoreKOVO:
    """Flashscore 결과 목록에서 KST 날짜 하루치 종료 경기를 V-리그 스키마로 만든다."""

    def __init__(self, league: str = "KOVO", sleep: float = 0.4):
        self.league = league
        self.sleep = sleep
        self.cols = {src: FlashscoreHockeyCollector(src, sleep=sleep) for src in SOURCES[league]}

    def collect_daily(self, date: str) -> dict:
        y1, y2 = season_years(date)
        games, unmapped = [], set()
        for src, col in self.cols.items():
            try:
                recs = col.season_matches(y1, y2)
            except Exception as e:
                # 컵대회 페이지는 비시즌에 비어 있을 수 있음 → 정규리그만이라도 수집
                print(f"  [{self.league}] Flashscore {src} 목록 실패: {e}")
                if "CUP" not in src:
                    raise
                continue
            for rec in sorted(recs.values(), key=lambda r: _int(r.get("AD"))):
                if rec.get("AB") != "3" or not _int(rec.get("AD")):
                    continue
                local = datetime.fromtimestamp(_int(rec.get("AD")), timezone.utc).astimezone(KST)
                if local.strftime("%Y%m%d") != date:
                    continue
                for side in ("AE", "AF"):
                    if not team_info(self.league, rec.get(side, "")):
                        unmapped.add(rec.get(side, ""))
                games.append(build_game(self.league, src, rec))
            time.sleep(self.sleep)
        if unmapped:
            print(f"  [{self.league}] ⚠️ Flashscore 팀명 매핑 없음(원문 유지): {sorted(unmapped)}")
        games.sort(key=lambda g: g["start_kst"])
        return {"date": date, "league": self.league, "source": "flashscore", "games": games}
