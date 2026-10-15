"""KBL 일별 경기 수집기 (네이버 스포츠 공개 API: api-gw.sports.naver.com, 키 불필요)

수집 단위: 한국 날짜(YYYYMMDD) 하루치 완료 경기 (KST 기준, NPB/KHL과 같은 날짜 기준)
- 경기 결과: 스코어, 쿼터별 득점, 연장 여부, 정규시간(4쿼터) 스코어
- 팀 경기 스탯: 2점/3점/자유투, 리바운드(공·수), 어시스트, 스틸, 블록, 턴오버, 파울, 페인트존 득점
- 선수 스탯: 출전 시간, 득점, 리바운드, 어시스트, 슈팅, 선발 여부
- 배당 정보는 소스에 없음 (국내 배당은 앱 스크린샷으로 별도 비교)

주의: 네이버 API는 upperCategoryId를 함께 보내면 빈 결과를 돌려준다 → categoryId만 사용.
"""
import time
import requests

API = "https://api-gw.sports.naver.com/schedule/games"

# 네이버 roundCode → 경기 구분 (2025-26 시즌 실데이터로 확인)
#   kbl_r 정규리그 / kbl_e 컵대회(시즌 전) / kbl_ps_* 포스트시즌, kbl_ps_cp 챔피언결정전
def _game_type(round_code: str) -> str:
    if round_code == "kbl_r":
        return "REG"
    if round_code == "kbl_e":
        return "CUP"
    if round_code == "kbl_as":
        return "ALLSTAR"
    if round_code == "kbl_ps_cp":
        return "FINAL"
    if round_code.startswith("kbl_ps"):
        return "PO"
    return round_code or "UNKNOWN"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
    "Referer": "https://m.sports.naver.com/basketball/schedule/index",
    "Origin": "https://m.sports.naver.com",
}


def _int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default


class KBLCollector:

    def __init__(self, sleep: float = 0.4):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.sleep = sleep

    def _get(self, url: str, params: dict = None, retries: int = 3):
        last = None
        for i in range(retries):
            try:
                r = self.session.get(url, params=params, timeout=20)
                if r.status_code == 200:
                    j = r.json()
                    if j.get("success") is False:
                        last = j.get("message")
                    else:
                        return j.get("result") or {}
                elif r.status_code == 404:
                    return None
                else:
                    last = f"HTTP {r.status_code}"
            except Exception as e:
                last = str(e)
            time.sleep(2 * (i + 1))
        raise RuntimeError(f"KBL API 실패 {url}: {last}")

    # ------------------------------------------------------------------
    def collect_daily(self, date: str) -> dict:
        """date: YYYYMMDD (한국 날짜)"""
        iso = f"{date[:4]}-{date[4:6]}-{date[6:]}"
        res = self._get(API, {"fields": "basic", "categoryId": "kbl",
                              "fromDate": iso, "toDate": iso, "size": 100}) or {}

        games = []
        for g in res.get("games", []):
            if g.get("statusCode") != "RESULT" or g.get("cancel") or g.get("suspended"):
                continue
            # 일시 오류로 경기 하나가 조용히 빠지는 일이 있어 경기 단위로 한 번 더 시도
            for attempt in range(2):
                try:
                    games.append(self._build_game(g["gameId"]))
                    break
                except Exception as e:
                    if attempt:
                        print(f"  [KBL] 경기 {g.get('gameId')} 파싱 실패: {e}")
                    time.sleep(5)
            time.sleep(self.sleep)

        return {"date": date, "league": "KBL", "games": games}

    # ------------------------------------------------------------------
    def _build_game(self, gid: str) -> dict:
        info = (self._get(f"{API}/{gid}") or {}).get("game") or {}
        time.sleep(self.sleep)
        rec = (self._get(f"{API}/{gid}/record") or {}).get("recordData") or {}

        hs = _int(info.get("homeTeamScore", rec.get("homeScore")))
        as_ = _int(info.get("awayTeamScore", rec.get("awayScore")))

        hq = [_int(x) for x in info.get("homeTeamScoreByQuarter") or []]
        aq = [_int(x) for x in info.get("awayTeamScoreByQuarter") or []]
        if not hq and rec:
            hq = [_int(rec.get(f"homeQ{i}Score")) for i in range(1, 5)]
            aq = [_int(rec.get(f"awayQ{i}Score")) for i in range(1, 5)]
        # 네이버 쿼터 배열은 Q1~Q4 + 연장 합계 자리(5번째)를 가진다
        reg_home, reg_away = sum(hq[:4]), sum(aq[:4])
        overtime = (hs - reg_home) > 0 or (as_ - reg_away) > 0
        quarters = []
        for i in range(max(len(hq), len(aq))):
            h = hq[i] if i < len(hq) else 0
            a = aq[i] if i < len(aq) else 0
            if i >= 4 and h == 0 and a == 0:
                continue
            quarters.append({"q": f"Q{i+1}" if i < 4 else "OT", "home": h, "away": a})

        round_code = info.get("roundCode", "")
        home_name = info.get("homeTeamName", "")
        away_name = info.get("awayTeamName", "")

        return {
            "game_id": gid,
            "game_type": _game_type(round_code),   # REG / CUP / PO / FINAL
            "round_code": round_code,
            "season": info.get("seasonYear"),
            "start_kst": info.get("gameDateTime", ""),
            "venue": info.get("stadium", ""),
            "home_team": home_name,
            "away_team": away_name,
            "home_short": info.get("homeTeamShortName", ""),
            "away_short": info.get("awayTeamShortName", ""),
            "home_code": info.get("homeTeamCode", ""),
            "away_code": info.get("awayTeamCode", ""),
            "neutral": bool(info.get("neutralGround")),
            "series_game_no": info.get("seriesGameNo") or None,
            "home_score": hs,
            "away_score": as_,
            "total_points": hs + as_,
            "margin_home": hs - as_,
            "overtime": overtime,
            "reg_home_score": reg_home,     # 4쿼터까지 (연장 제외 마켓 판정용)
            "reg_away_score": reg_away,
            "reg_total_points": reg_home + reg_away,
            "winner": "HOME" if hs > as_ else "AWAY",
            "quarter_scores": quarters,
            "home_stats": self._team_stats(rec.get("home") or {}),
            "away_stats": self._team_stats(rec.get("away") or {}),
            "home_players": self._players(rec.get("homePlayerStats") or []),
            "away_players": self._players(rec.get("awayPlayerStats") or []),
        }

    # ------------------------------------------------------------------
    @staticmethod
    def _team_stats(t: dict) -> dict:
        if not t:
            return {}
        # 네이버 필드: fg/fgA = 2점슛, threep/threepA = 3점슛, normalFg/normalFgA = 야투 전체
        return {
            "fgm": _int(t.get("normalFg")), "fga": _int(t.get("normalFgA")),
            "fg2m": _int(t.get("fg")), "fg2a": _int(t.get("fgA")),
            "fg3m": _int(t.get("threep")), "fg3a": _int(t.get("threepA")),
            "ftm": _int(t.get("ft")), "fta": _int(t.get("ftA")),
            "reb": _int(t.get("rebound")), "oreb": _int(t.get("oR")), "dreb": _int(t.get("dR")),
            "ast": _int(t.get("aS")), "stl": _int(t.get("sT")), "blk": _int(t.get("bS")),
            "tov": _int(t.get("to")), "fouls": _int(t.get("foulTot")),
            "paint_pts": _int(t.get("pScore")), "dunks": _int(t.get("dk")),
        }

    @staticmethod
    def _players(rows: list) -> list:
        res = []
        for p in rows:
            sec = _int(p.get("playTimeSec"))
            res.append({
                "player_id": p.get("playerId"),
                "name": p.get("playerName", ""),
                "pos": p.get("position", ""),
                "starter": bool(p.get("startFlag")),
                "dnp": sec == 0,
                "min": round(sec / 60, 1),
                "pts": _int(p.get("scoreTot")),
                "reb": _int(p.get("reboundTot")), "oreb": _int(p.get("or")), "dreb": _int(p.get("dr")),
                "ast": _int(p.get("as")), "stl": _int(p.get("st")), "blk": _int(p.get("bs")),
                "tov": _int(p.get("to")), "fouls": _int(p.get("foulTot")),
                "fg2m": _int(p.get("twoP")), "fg2a": _int(p.get("twoPA")),
                "fg3m": _int(p.get("threeP")), "fg3a": _int(p.get("threePA")),
                "ftm": _int(p.get("ft")), "fta": _int(p.get("ftA")),
            })
        return res
