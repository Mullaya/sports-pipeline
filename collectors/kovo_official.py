"""V-리그 공식 API(user-api.kovo.co.kr) 일별 경기 수집기 — 선수·팀 상세 기록 포함

네이버 스포츠 API가 GitHub Actions 서버에서 응답하지 않게 되어(2026-10-24~) 1순위 수집원으로 사용.
출력 형식은 네이버 수집기(kovo_collector.py)와 같다. 팀 코드도 네이버와 동일(1001~1009, 2001~2008).
  game_id = 날짜 + 대회코드(gpart, 정규리그 201) + M/F + 경기번호  예) 20261101201M3
필드 메모(실데이터 확인, 2026-11-08):
  att/ats = 공격 시도/성공, bat = 후위공격 시도, bt/bs = 블로킹 시도/성공, st/ss = 서브 시도/에이스,
  rt/rs = 리시브 시도/정확, dt/ds = 디그 시도/성공, sett/sets = 세트 시도/정확, err = 범실, point = 득점
  ynS1~ynS5 = 세트별 출전 표시("-2"는 미출전·미진행 세트)
"""
import time

import requests

API = "https://user-api.kovo.co.kr"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Origin": "https://www.kovo.co.kr",
    "Referer": "https://www.kovo.co.kr/",
    "X-Service-Name": "user",
    "Accept-Language": "ko",
}
GENDER = {"KOVO": "1", "WKOVO": "2"}

# 팀 코드 → 네이버 수집 데이터와 같은 팀 이름
TEAMS = {
    "1001": "대한항공", "1002": "삼성화재", "1004": "KB손해보험", "1005": "현대캐피탈",
    "1006": "한국전력", "1008": "OK저축은행", "1009": "우리카드",
    "2001": "현대건설", "2002": "한국도로공사", "2003": "정관장", "2004": "흥국생명",
    "2005": "GS칼텍스", "2006": "IBK기업은행", "2008": "SOOP",
}


def _int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default


def _pct(a, b):
    return round(a / b * 100, 1) if b else 0.0


def _game_type(league_name: str) -> str:
    n = league_name or ""
    if "정규" in n:
        return "REG"
    if "챔피언" in n:
        return "FINAL"
    if "플레이오프" in n or "포스트" in n or "준플" in n:
        return "PO"
    if "컵" in n:
        return "CUP"
    if "올스타" in n:
        return "ALLSTAR"
    return n or "UNKNOWN"


class KOVOOfficialCollector:
    """league: "KOVO"(남자부) 또는 "WKOVO"(여자부)"""

    def __init__(self, league: str = "KOVO", sleep: float = 0.3):
        self.league = league
        self.gender = GENDER[league]
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.sleep = sleep

    def _get(self, path: str, params: dict = None, retries: int = 3):
        last = None
        for i in range(retries):
            try:
                r = self.session.get(API + path, params=params, timeout=20)
                if r.status_code == 200:
                    j = r.json()
                    res = j.get("result") or {}
                    if res.get("status") == 200:
                        return j.get("payload")
                    last = f"result {res}"
                else:
                    last = f"HTTP {r.status_code}"
            except Exception as e:
                last = str(e)
            time.sleep(2 * (i + 1))
        raise RuntimeError(f"KOVO 공식 API 실패 {path}: {last}")

    def collect_daily(self, date: str) -> dict:
        """date: YYYYMMDD (한국 날짜)"""
        # 시즌 전체 일정은 한 번만 받아 둔다 (누락분 재수집·초기적재 때 날짜마다 다시 받지 않도록)
        if not hasattr(self, "_season_list"):
            season = self._get("/main/game/season") or {}
            self._gcode = season.get("gcode", "001")
            self._season_list = (self._get("/stat/game-schedule",
                                           {"seasonCode": season.get("seasonCode"), "gcode": self._gcode})
                                 or {}).get("content") or []
        gc, lst = self._gcode, self._season_list
        iso = f"{date[:4]}-{date[4:6]}-{date[6:]}"
        games = []
        for m in lst:
            if m.get("gdate") != iso or str(m.get("gender")) != self.gender:
                continue
            if _int(m.get("hspoint")) + _int(m.get("aspoint")) == 0:   # 미종료·취소
                continue
            for attempt in range(2):
                try:
                    games.append(self._build_game(m, gc))
                    break
                except Exception as e:
                    if attempt:
                        print(f"  [{self.league}] 경기 {m.get('gnum')} 파싱 실패: {e}")
                    time.sleep(3)
            time.sleep(self.sleep)
        return {"date": date, "league": self.league, "source": "kovo.co.kr", "games": games}

    # ------------------------------------------------------------------
    def _build_game(self, m: dict, gcode: str) -> dict:
        d = self._get(f"/stat/game-schedule/{m['gnum']}",
                      {"gcode": gcode, "seasonCode": m["seasonCode"],
                       "leagueCode": m.get("leagueCode"), "gender": m.get("gender")}) or {}
        g = d.get("game") or m
        hc, ac = str(g.get("hcode")), str(g.get("acode"))
        hs, as_ = _int(g.get("hspoint")), _int(g.get("aspoint"))

        sets = []
        for i in range(1, 6):
            h, a = _int(g.get(f"hs{i}point")), _int(g.get(f"as{i}point"))
            if h == 0 and a == 0:
                continue
            sets.append({"set": i, "home": h, "away": a})
        home_pts = sum(s["home"] for s in sets)
        away_pts = sum(s["away"] for s in sets)

        team = {str(t.get("tcode")): t for t in d.get("team") or []}
        players = d.get("player") or []
        th, ta = team.get(hc, {}), team.get(ac, {})

        gid = f"{g['gdate'].replace('-', '')}{g.get('gpart') or g.get('leagueCode')}{'M' if self.gender == '1' else 'F'}{g['gnum']}"
        return {
            "game_id": gid,
            "game_type": _game_type(g.get("leagueName")),
            "round_code": "kovo_official",
            "round_info": g.get("roundName") or "",
            "round": g.get("round"),
            "group": None,
            "season": _int(str(g.get("seasonName", "")).split("~")[0][-4:]) or None,
            "league_code": g.get("leagueCode"),
            "start_kst": f"{g['gdate']}T{g.get('gstime') or '00:00'}:00",
            "venue": g.get("place", ""),
            "home_team": TEAMS.get(hc, g.get("hsname", "")),
            "away_team": TEAMS.get(ac, g.get("asname", "")),
            "home_code": hc,
            "away_code": ac,
            "neutral": False,
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
            "home_stats": self._team_stats(th, ta),
            "away_stats": self._team_stats(ta, th),
            "home_players": self._players([p for p in players if str(p.get("tcode")) == hc], th, len(sets)),
            "away_players": self._players([p for p in players if str(p.get("tcode")) == ac], ta, len(sets)),
        }

    @staticmethod
    def _team_stats(t: dict, opp: dict) -> dict:
        if not t:
            return {}
        att, ats, rt, rs = _int(t.get("att")), _int(t.get("ats")), _int(t.get("rt")), _int(t.get("rs"))
        return {
            "att": att, "att_kill": ats, "att_pct": _pct(ats, att),
            "blk_att": _int(t.get("bt")), "blk_pts": _int(t.get("bs")),
            "srv": _int(t.get("st")), "aces": _int(t.get("ss")),
            "rcv": rt, "rcv_exact": rs, "rcv_pct": _pct(rs, rt),
            "dig": _int(t.get("dt")), "dig_ok": _int(t.get("ds")),
            "set_att": _int(t.get("sett")), "set_exact": _int(t.get("sets")),
            "errors": _int(t.get("err")),                 # 자팀 범실
            "opp_errors": _int((opp or {}).get("err")),   # 상대 범실(상대 범실로 얻은 점수)
            "points": _int(t.get("point")),
        }

    @staticmethod
    def _players(rows: list, team: dict, set_count: int) -> list:
        team_att = _int((team or {}).get("att"))
        res = []
        for p in rows:
            att, ats, rt, rs = _int(p.get("att")), _int(p.get("ats")), _int(p.get("rt")), _int(p.get("rs"))
            played = sum(1 for i in range(1, set_count + 1) if str(p.get(f"ynS{i}")) not in ("-2", "None", ""))
            res.append({
                "player_id": p.get("pcode"),
                "name": p.get("pname", ""),
                "pos": p.get("position", ""),
                "sets": played,
                "pts": _int(p.get("point")),
                "att": att, "att_kill": ats, "att_pct": _pct(ats, att),
                "back_att": _int(p.get("bat")),
                "att_share": _pct(att, team_att),
                "blk_pts": _int(p.get("bs")),
                "aces": _int(p.get("ss")), "srv": _int(p.get("st")),
                "rcv": rt, "rcv_exact": rs, "rcv_pct": _pct(rs, rt),
                "dig": _int(p.get("dt")), "dig_ok": _int(p.get("ds")),
                "set_att": _int(p.get("sett")), "set_exact": _int(p.get("sets")),
                "errors": _int(p.get("err")),
            })
        return res
