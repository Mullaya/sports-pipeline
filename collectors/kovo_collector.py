"""V-리그 남자부(KOVO)·여자부(WKOVO) 일별 경기 수집기
(네이버 스포츠 공개 API: api-gw.sports.naver.com, 키 불필요 — KBL 수집기와 같은 소스)

수집 단위: 한국 날짜(YYYYMMDD) 하루치 완료 경기 (KST 기준, KBL/NPB와 같은 날짜 기준)
- 경기 결과: 세트 스코어, 세트별 점수, 총 득점, 세트 수(3·4·5), 점수 핸디 판정용 득실차
- 팀 경기 스탯: 공격(시도/성공/성공률), 블로킹, 서브, 리시브(정확/효율), 디그, 세트(토스), 범실
- 선수 스탯: 포지션, 출전 세트, 득점, 공격·블로킹·서브·리시브·디그 기록
- 컵대회도 같은 카테고리로 내려온다 (남자 kovo / 여자 wkovo, roundCode kovo_cup_*)
- 배당 정보는 소스에 없음

game_type: REG 정규리그 / CUP 컵대회 / PO 포스트시즌 / FINAL 챔피언결정전
"""
import time
import requests

API = "https://api-gw.sports.naver.com/schedule/games"

CATEGORY = {"KOVO": "kovo", "WKOVO": "wkovo"}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
    "Referer": "https://m.sports.naver.com/volleyball/schedule/index",
    "Origin": "https://m.sports.naver.com",
}


def _int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default


def _float(x, default=None):
    try:
        return round(float(x), 1)
    except Exception:
        return default


def _game_type(round_code: str, round_info: str) -> str:
    rc = (round_code or "").lower()
    ri = round_info or ""
    if "cup" in rc or "컵" in ri or "조별" in ri:
        return "CUP"
    if "챔피언" in ri or rc.endswith("_cp") or rc.endswith("_f"):
        return "FINAL"
    if rc.startswith("kovo_ps") or rc.startswith("kovo_po") or "플레이오프" in ri or "포스트" in ri:
        return "PO"
    if rc == "kovo_r" or "Round" in ri:
        return "REG"
    if "올스타" in ri or "allstar" in rc:
        return "ALLSTAR"
    return rc.upper() or "UNKNOWN"


class KOVOCollector:
    """league: "KOVO"(남자부) 또는 "WKOVO"(여자부)"""

    def __init__(self, league: str = "KOVO", sleep: float = 0.4):
        self.league = league
        self.category = CATEGORY[league]
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
        raise RuntimeError(f"{self.league} API 실패 {url}: {last}")

    # ------------------------------------------------------------------
    def collect_daily(self, date: str) -> dict:
        """date: YYYYMMDD (한국 날짜)"""
        iso = f"{date[:4]}-{date[4:6]}-{date[6:]}"
        # upperCategoryId를 같이 보내면 빈 결과 → categoryId만 사용 (KBL과 동일)
        res = self._get(API, {"fields": "basic", "categoryId": self.category,
                              "fromDate": iso, "toDate": iso, "size": 100}) or {}

        games = []
        for g in res.get("games", []):
            if g.get("statusCode") != "RESULT" or g.get("cancel") or g.get("suspended"):
                continue
            for attempt in range(2):
                try:
                    games.append(self._build_game(g["gameId"]))
                    break
                except Exception as e:
                    if attempt:
                        print(f"  [{self.league}] 경기 {g.get('gameId')} 파싱 실패: {e}")
                    time.sleep(5)
            time.sleep(self.sleep)

        return {"date": date, "league": self.league, "games": games}

    # ------------------------------------------------------------------
    def _build_game(self, gid: str) -> dict:
        info = (self._get(f"{API}/{gid}") or {}).get("game") or {}
        time.sleep(self.sleep)
        rec = (self._get(f"{API}/{gid}/record") or {}).get("recordData") or {}

        hs = _int(info.get("homeTeamScore"))   # 세트 스코어
        as_ = _int(info.get("awayTeamScore"))

        sets = []
        for s in info.get("currentScoreBySet") or []:
            h, a = _int(s.get("homeScore")), _int(s.get("awayScore"))
            if h == 0 and a == 0:
                continue
            sets.append({"set": _int(s.get("set")), "home": h, "away": a})
        home_pts = sum(s["home"] for s in sets)
        away_pts = sum(s["away"] for s in sets)

        round_code = info.get("roundCode") or ""
        round_info = info.get("roundInfo") or ""
        gtype = _game_type(round_code, round_info)
        gr = rec.get("gameRecord") or {}
        ps = rec.get("playerStatOfGame") or {}

        return {
            "game_id": gid,
            "game_type": gtype,
            "round_code": round_code,
            "round_info": round_info,
            "round": info.get("round"),
            "group": info.get("groupName") or None,      # 컵대회 조
            "season": info.get("seasonYear") or None,     # 컵대회는 0 → None
            "league_code": info.get("leagueCode") or info.get("seasonCode"),
            "start_kst": info.get("gameDateTime", ""),
            "venue": info.get("stadium", ""),
            "home_team": info.get("homeTeamName", ""),
            "away_team": info.get("awayTeamName", ""),
            "home_code": info.get("homeTeamCode", ""),
            "away_code": info.get("awayTeamCode", ""),
            "neutral": bool(info.get("neutralGround")),
            "series_game_no": info.get("seriesGameNo") or None,
            "home_sets": hs,
            "away_sets": as_,
            "set_score": f"{hs}-{as_}",
            "set_count": len(sets) or (hs + as_),
            "full_set": len(sets) == 5,
            "winner": "HOME" if hs > as_ else "AWAY",
            "home_points": home_pts,             # 총 득점 (점수 핸디·총점 언오버 판정용)
            "away_points": away_pts,
            "total_points": home_pts + away_pts,
            "margin_points_home": home_pts - away_pts,
            "set_scores": sets,
            "home_stats": self._team_stats(gr.get("home") or {}),
            "away_stats": self._team_stats(gr.get("away") or {}),
            "home_players": self._players(ps.get("home") or []),
            "away_players": self._players(ps.get("away") or []),
        }

    # ------------------------------------------------------------------
    @staticmethod
    def _team_stats(t: dict) -> dict:
        if not t:
            return {}
        return {
            "att": _int(t.get("attackCount")), "att_kill": _int(t.get("attackSuccessCount")),
            "att_pct": _float(t.get("attackSuccessRate")),
            "blk_att": _int(t.get("blockCount")), "blk_pts": _int(t.get("blockSuccessCount")),
            "srv": _int(t.get("serveCount")), "aces": _int(t.get("serveSuccessCount")),
            "rcv": _int(t.get("receiveCount")), "rcv_exact": _int(t.get("exactReceiveCount")),
            "rcv_pct": _float(t.get("receiveSuccessRate")),
            "dig": _int(t.get("digCount")), "dig_ok": _int(t.get("digSuccessCount")),
            "set_att": _int(t.get("tossCount")), "set_exact": _int(t.get("exactTossCount")),
            "errors": _int(t.get("totalErrorCount")),          # 자팀 범실
            "opp_errors": _int(t.get("opponentErrorCount")),   # 상대 범실로 얻은 점수
            "points": _int(t.get("totalPoint")),
        }

    @staticmethod
    def _players(rows: list) -> list:
        res = []
        for p in rows:
            res.append({
                "player_id": p.get("playerId"),
                "name": p.get("playerName", ""),
                "pos": p.get("position", ""),        # OH/OP/MB/S/L
                "sets": _int(p.get("cset")),
                "pts": _int(p.get("point")),
                "att": _int(p.get("attack")), "att_kill": _int(p.get("attackSuccess")),
                "att_pct": _float(p.get("attackSuccessRate")),
                "back_att": _int(p.get("backAttack")),
                "att_share": _float(p.get("attackPossession")),   # 팀 공격 점유율(%)
                "blk_pts": _int(p.get("blockingSuccess")),
                "aces": _int(p.get("serveSuccess")), "srv": _int(p.get("serve")),
                "rcv": _int(p.get("receive")), "rcv_exact": _int(p.get("receiveSuccess")),
                "rcv_pct": _float(p.get("receiveSuccessRate")),
                "dig": _int(p.get("dig")), "dig_ok": _int(p.get("digSuccess")),
                "set_att": _int(p.get("toss")), "set_exact": _int(p.get("tossSuccess")),
                "errors": _int(p.get("error")),
            })
        return res
