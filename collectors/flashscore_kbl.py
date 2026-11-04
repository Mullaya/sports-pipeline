"""KBL 대체 수집 — Flashscore 피드 (네이버 API가 GitHub Actions IP에서 응답하지 않을 때 사용)

2026-10-26 무렵부터 api-gw.sports.naver.com 이 Actions 러너에서 읽기 시간 초과로 막혀
KBL·KOVO 일별 파일이 끊겼다. Flashscore는 Actions에서 정상 응답(유럽 하키 수집에 사용 중).

기존 네이버 기반 일별 파일과 같은 스키마로 만든다.
- 팀명·약칭·코드: 네이버 표기(예: "서울 SK" / "SK" / "55")로 변환해 기존 데이터·통계와 이어지게 함
- 날짜: 한국 시간(KST) 경기일
- 팀 스탯: 야투/2점/3점/자유투, 리바운드(공·수), 어시스트, 스틸, 블록, 턴오버, 파울
  (페인트존 득점·덩크·선수 개인 스탯은 Flashscore 피드에 없어 빈 값)
- game_id: "fs_" + Flashscore 경기 ID (네이버 ID와 겹치지 않음)
"""
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from collectors.flashscore_hockey_collector import FEED, FlashscoreHockeyCollector, LEAGUES, season_years

KST = ZoneInfo("Asia/Seoul")

LEAGUES.setdefault("KBL_FS", {"path": "basketball/south-korea/kbl", "country": "106",
                              "tournament": "QulwZyP2", "tz": "Asia/Seoul"})

# Flashscore 팀명(소문자) 키워드 → (네이버 팀명, 약칭, 팀코드). 위에서부터 먼저 맞는 것 사용
TEAMS = [
    (("kogas", "gas"), ("대구 한국가스공사", "한국가스공사", "64")),
    (("wonju", " db", "db "), ("원주 DB", "DB", "16")),
    (("knights", "seoul sk"), ("서울 SK", "SK", "55")),
    (("kcc",), ("부산 KCC", "KCC", "60")),
    (("sono",), ("고양 소노", "고양소노", "66")),
    (("sakers", "lg"), ("창원 LG", "LG", "50")),
    (("samsung", "thunders"), ("서울 삼성", "삼성", "35")),
    (("sonicboom", "suwon", "kt "), ("수원 KT", "KT", "06")),
    (("jung kwan jang", "jungkwanjang", "kgc", "anyang", "red boosters"), ("안양 정관장", "정관장", "70")),
    (("mobis", "phoebus", "ulsan"), ("울산 현대모비스", "현대모비스", "10")),
]

STAT_KEYS = {
    "Field goals attempts": "fga", "Field goals made": "fgm",
    "2-point field goals attempts": "fg2a", "2-point field goals made": "fg2m",
    "3-point field goals attempts": "fg3a", "3-point field goals made": "fg3m",
    "Free throws attempts": "fta", "Free throws made": "ftm",
    "Offensive rebounds": "oreb", "Defensive rebounds": "dreb", "Total rebounds": "reb",
    "Assists": "ast", "Blocks": "blk", "Turnovers": "tov", "Steals": "stl", "Personal fouls": "fouls",
}


def _int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default


def team_info(raw: str):
    key = f" {raw.lower()} "
    for words, info in TEAMS:
        if any(w in key for w in words):
            return info
    return None


def _game_type(za: str) -> str:
    z = (za or "").lower()
    if "final" in z and "semi" not in z and "quarter" not in z:
        return "FINAL"
    if "play off" in z or "playoff" in z or "play-off" in z:
        return "PO"
    if "cup" in z:
        return "CUP"
    if "all-star" in z or "all star" in z:
        return "ALLSTAR"
    return "REG"


def parse_stats(text: str) -> tuple:
    """df_st 피드 → (home, away). 'Match'(경기 전체) 구간만 사용."""
    home, away, section = {}, {}, None
    for blk in (text or "").split("~"):
        d = {}
        for kv in blk.split("¬"):
            if "÷" in kv:
                k, v = kv.split("÷", 1)
                d[k] = v
        if "SE" in d:
            section = d["SE"]
            continue
        if section != "Match" or "SG" not in d:
            continue
        key = STAT_KEYS.get(d["SG"])
        if key:
            home[key] = _int(d.get("SH"))
            away[key] = _int(d.get("SI"))
    return home, away


def build_game(rec: dict, stats_text: str) -> dict:
    hi, ai = team_info(rec.get("AE", "")), team_info(rec.get("AF", ""))
    hs, as_ = _int(rec.get("AG")), _int(rec.get("AH"))
    hq = [_int(rec.get(k)) for k in ("BA", "BC", "BE", "BG")]
    aq = [_int(rec.get(k)) for k in ("BB", "BD", "BF", "BH")]
    reg_home = _int(rec.get("AT"), sum(hq))
    reg_away = _int(rec.get("AU"), sum(aq))
    quarters = [{"q": f"Q{i + 1}", "home": hq[i], "away": aq[i]} for i in range(4)]
    ot_h, ot_a = hs - reg_home, as_ - reg_away
    overtime = ot_h > 0 or ot_a > 0
    if overtime:
        quarters.append({"q": "OT", "home": ot_h, "away": ot_a})
    start = datetime.fromtimestamp(_int(rec.get("AD")), timezone.utc).astimezone(KST)
    hst, ast = parse_stats(stats_text)
    return {
        "game_id": "fs_" + rec["AA"],
        "game_type": _game_type(rec.get("ZA")),
        "round_code": "flashscore",
        "season": season_years(start.strftime("%Y%m%d"))[0],
        "start_kst": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "venue": "",
        "home_team": hi[0] if hi else rec.get("AE", ""),
        "away_team": ai[0] if ai else rec.get("AF", ""),
        "home_short": hi[1] if hi else rec.get("AE", ""),
        "away_short": ai[1] if ai else rec.get("AF", ""),
        "home_code": hi[2] if hi else "",
        "away_code": ai[2] if ai else "",
        "neutral": False,
        "series_game_no": None,
        "home_score": hs,
        "away_score": as_,
        "total_points": hs + as_,
        "margin_home": hs - as_,
        "overtime": overtime,
        "reg_home_score": reg_home,
        "reg_away_score": reg_away,
        "reg_total_points": reg_home + reg_away,
        "winner": "HOME" if hs > as_ else "AWAY",
        "quarter_scores": quarters,
        "home_stats": hst,
        "away_stats": ast,
        "home_players": [],
        "away_players": [],
    }


class FlashscoreKBL:
    """Flashscore 시즌 결과 목록에서 KST 날짜 하루치 종료 경기를 KBL 스키마로 만든다."""

    def __init__(self, sleep: float = 0.4):
        self.fs = FlashscoreHockeyCollector("KBL_FS", sleep=sleep)
        self.sleep = sleep

    def collect_daily(self, date: str) -> dict:
        y1, y2 = season_years(date)
        games, unmapped = [], set()
        recs = sorted(self.fs.season_matches(y1, y2).values(), key=lambda r: _int(r.get("AD")))
        for rec in recs:
            if rec.get("AB") != "3" or not _int(rec.get("AD")):
                continue
            local = datetime.fromtimestamp(_int(rec.get("AD")), timezone.utc).astimezone(KST)
            if local.strftime("%Y%m%d") != date:
                continue
            for side in ("AE", "AF"):
                if not team_info(rec.get(side, "")):
                    unmapped.add(rec.get(side, ""))
            try:
                stats = self.fs._get(f"{FEED}df_st_1_{rec['AA']}", feed=True)
            except Exception as e:
                print(f"  [KBL] Flashscore 스탯 실패 {rec['AA']}: {e}")
                stats = ""
            games.append(build_game(rec, stats))
            time.sleep(self.sleep)
        if unmapped:
            print(f"  [KBL] ⚠️ Flashscore 팀명 매핑 없음(원문 유지): {sorted(unmapped)}")
        return {"date": date, "league": "KBL", "source": "flashscore", "games": games}
