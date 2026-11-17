"""하키 골리 보조 소스 — Flashscore 라인업 피드(df_li)가 2026-11 초부터 빈 응답이라 공식 API로 보완

  LIIGA : liiga.fi 공식 API (키 불필요)
          - 시즌 경기 목록: /api/v2/games?tournament=<runkosarja|playoffs>&season=<끝 연도>
          - 경기 상세: /api/v2/games/<season>/<id> → homeTeamPlayers/awayTeamPlayers 중 role=GOALIE, line=1 = 선발
          - 골리 개인 세이브 수는 없어 기존과 같이 팀 세이브/상대 유효슈팅으로 계산 (교체 시 합산값)
          - 경기별 기대득점(expectedGoals)도 같이 제공 → home_xg / away_xg
  AHL   : HockeyTech 공개 피드 (AHL 공식 사이트가 쓰는 공개 키)
          - 시즌 일정: modulekit/schedule, 경기 요약: statviewfeed/gameSummary
          - 골리별 TOI·유효슈팅·세이브·실점·선발 여부까지 제공 → NHL 형식과 같은 개인 기록

반환 형식: {"home": [goalie...], "away": [goalie...]} — 실패/매칭 불가 시 {}
"""
import json
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone

import requests

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


class _Base:
    def __init__(self, sleep: float = 0.3):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept": "application/json, */*"})
        self.sleep = sleep

    def _json(self, url: str, retries: int = 3):
        last = None
        for i in range(retries):
            try:
                r = self.s.get(url, timeout=30)
                if r.status_code == 200:
                    t = r.text.strip()
                    if t.startswith("(") and t.endswith(")"):      # HockeyTech JSONP
                        t = t[1:-1]
                    return json.loads(t)
                last = f"HTTP {r.status_code}"
            except Exception as e:
                last = str(e)
            time.sleep(2 * (i + 1))
        raise RuntimeError(f"요청 실패 {url}: {last}")


# ----------------------------------------------------------------------
class LiigaGoalies(_Base):
    API = "https://liiga.fi/api/v2"
    # Flashscore 팀명 → liiga.fi 팀명
    NAMES = {
        "Assat": "Ässät", "Hameenlinna": "HPK", "IFK Helsinki": "HIFK", "Karpat": "Kärpät",
        "Kiekko-Espoo": "K-Espoo", "TPS Turku": "TPS", "Vaasan Sport": "Sport",
    }
    TOURNAMENTS = ("runkosarja", "playoffs", "playout", "qualifications")

    def __init__(self, **kw):
        super().__init__(**kw)
        self._season = {}

    def _games(self, season: int) -> list:
        if season not in self._season:
            out = []
            for t in self.TOURNAMENTS:
                try:
                    out += self._json(f"{self.API}/games?tournament={t}&season={season}") or []
                except Exception:
                    pass
            self._season[season] = out
        return self._season[season]

    def find(self, start_utc: str, home: str, away: str):
        st = datetime.strptime(start_utc[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        season = st.year + 1 if st.month >= 7 else st.year       # liiga 시즌 = 끝 연도
        h, a = _norm(self.NAMES.get(home, home)), _norm(self.NAMES.get(away, away))
        for g in self._games(season):
            if _norm(g["homeTeam"]["teamName"]) != h or _norm(g["awayTeam"]["teamName"]) != a:
                continue
            gs = datetime.strptime(g["start"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
            if abs(gs - st) <= timedelta(hours=12):
                return season, g
        return None, None

    def goalies(self, start_utc: str, home: str, away: str) -> dict:
        season, g = self.find(start_utc, home, away)
        if not g:
            return {}
        d = self._json(f"{self.API}/games/{season}/{g['id']}")
        time.sleep(self.sleep)
        out = {"_xg": {"home": g["homeTeam"].get("expectedGoals"), "away": g["awayTeam"].get("expectedGoals")},
               "_source_id": g["id"]}
        for side, key in (("home", "homeTeamPlayers"), ("away", "awayTeamPlayers")):
            gks = [p for p in d.get(key) or [] if p.get("role") == "GOALIE" and not p.get("removed")]
            gks.sort(key=lambda p: (p.get("line") or 99))
            if gks and gks[0].get("line") == 1:
                p = gks[0]
                out[side] = {"name": f'{p.get("lastName", "")} {p.get("firstName", "")[:1]}.'.strip(),
                             "player_id": f'liiga:{p.get("id")}'}
        return out


# ----------------------------------------------------------------------
class AHLGoalies(_Base):
    BASE = "https://lscluster.hockeytech.com/feed/index.php"
    KEY = "key=50c2cd9b5e18e390&client_code=ahl"

    def __init__(self, **kw):
        super().__init__(**kw)
        self._seasons = None
        self._sched = {}
        self._teams = {}

    def _season_ids(self, date: str) -> list:
        """해당 날짜가 속한 시즌의 정규·플레이오프 season_id (올스타 제외)"""
        if self._seasons is None:
            d = self._json(f"{self.BASE}?feed=modulekit&view=seasons&{self.KEY}")
            self._seasons = d["SiteKit"]["Seasons"]
        y = int(date[:4]) if int(date[4:6]) >= 8 else int(date[:4]) - 1
        ids = []
        for s in self._seasons:
            nm = s.get("season_name", "")
            if "All-Star" in nm:
                continue
            if f"{y}-{str(y + 1)[2:]}" in nm or (f"{y + 1}" in nm and "Playoffs" in nm):
                ids.append(s["season_id"])
        return ids

    def _schedule(self, sid: str) -> list:
        if sid not in self._sched:
            d = self._json(f"{self.BASE}?feed=modulekit&view=schedule&season_id={sid}&{self.KEY}")
            self._sched[sid] = d["SiteKit"].get("Schedule") or []
            t = self._json(f"{self.BASE}?feed=modulekit&view=teamsbyseason&season_id={sid}&{self.KEY}")
            for tm in t["SiteKit"].get("Teamsbyseason") or []:
                self._teams[str(tm["id"])] = tm.get("name", "")
        return self._sched[sid]

    def _same(self, fs_name: str, tid: str) -> bool:
        a, b = _norm(fs_name), _norm(self._teams.get(str(tid), ""))
        return bool(a and b) and (a == b or b.startswith(a) or a.startswith(b))

    def goalies(self, date: str, home: str, away: str) -> dict:
        """date = 미국 동부 현지 경기일 YYYYMMDD"""
        iso = f"{date[:4]}-{date[4:6]}-{date[6:]}"
        gid = None
        for sid in self._season_ids(date):
            for g in self._schedule(sid):
                if g.get("date_played") == iso and self._same(home, g["home_team"]) \
                        and self._same(away, g["visiting_team"]):
                    gid = g["game_id"]
                    break
            if gid:
                break
        if not gid:
            return {}
        d = self._json(f"{self.BASE}?feed=statviewfeed&view=gameSummary&game_id={gid}&{self.KEY}&lang=en&site_id=0")
        time.sleep(self.sleep)
        out = {"_source_id": gid}
        for side, key in (("home", "homeTeam"), ("away", "visitingTeam")):
            rows = []
            for gk in (d.get(key) or {}).get("goalies") or []:
                st, info = gk.get("stats") or {}, gk.get("info") or {}
                toi = st.get("timeOnIce")
                if not toi and not gk.get("starting"):
                    continue                      # 등록만 된 백업
                mm = 0.0
                if toi and ":" in toi:
                    m, s = toi.split(":")[:2]
                    mm = round(int(m) + int(s) / 60, 2)
                sa, sv = st.get("shotsAgainst") or 0, st.get("saves") or 0
                rows.append({
                    "player_id": f'ahl:{info.get("id")}',
                    "name": f'{(info.get("firstName") or "")[:1]}. {info.get("lastName", "")}'.strip(),
                    "starter": bool(gk.get("starting")),
                    "toi": mm, "shots_against": sa, "saves": sv,
                    "goals_against": st.get("goalsAgainst"),
                    "sv_pct": round(sv / sa, 3) if sa else None,
                })
            rows.sort(key=lambda r: not r["starter"])
            out[side] = rows
        return out
