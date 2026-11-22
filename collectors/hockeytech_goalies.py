"""HockeyTech 공개 피드 골리 기록 (OHL·AHL 공식 사이트가 쓰는 공개 키)

Flashscore 라인업 피드(df_li)가 비어 있어 선발 골리를 못 받는 북미 리그 보완용.
  - 시즌 목록: modulekit/seasons → 날짜가 속한 정규시즌·플레이오프 season_id
  - 일정: modulekit/schedule (date_played, home_team, visiting_team id)
  - 경기 요약: statviewfeed/gameSummary → 골리별 TOI·유효슈팅·세이브·실점·선발 여부

반환: {"home": [goalie...], "away": [goalie...], "_source_id": game_id} / 매칭 실패 시 {}
goalie = {player_id, name, starter, toi, shots_against, saves, goals_against, sv_pct}
"""
import json
import re
import time
import unicodedata

import requests

BASE = "https://lscluster.hockeytech.com/feed/index.php"
CLIENTS = {
    "OHL": ("ohl", "f1aa699db3d81487"),
    "AHL": ("ahl", "50c2cd9b5e18e390"),
}
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


ALIASES = {"mississaugasteelheads": "bramptonsteelheads"}     # 2026 연고 이전, 피드는 옛 이름 유지


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]", "", s)
    return ALIASES.get(s, s)


def parse_summary(d: dict, prefix: str) -> dict:
    out = {}
    for side, key in (("home", "homeTeam"), ("away", "visitingTeam")):
        rows = []
        for gk in (d.get(key) or {}).get("goalies") or []:
            st, info = gk.get("stats") or {}, gk.get("info") or {}
            toi = st.get("timeOnIce")
            if not toi and not gk.get("starting"):
                continue                                  # 등록만 된 백업
            mm = 0.0
            if toi and ":" in toi:
                m, s = toi.split(":")[:2]
                mm = round(int(m) + int(s) / 60, 2)
            sa, sv = st.get("shotsAgainst") or 0, st.get("saves") or 0
            rows.append({
                "player_id": f'{prefix}:{info.get("id")}',
                "name": f'{info.get("lastName", "")} {(info.get("firstName") or "")[:1]}.'.strip(),
                "starter": bool(gk.get("starting")),
                "toi": mm, "shots_against": sa, "saves": sv,
                "goals_against": st.get("goalsAgainst"),
                "sv_pct": round(sv / sa, 3) if sa else None,
            })
        rows.sort(key=lambda r: not r["starter"])
        out[side] = rows
    return out


class HockeyTechGoalies:
    def __init__(self, league: str, sleep: float = 0.3):
        self.league = league
        client, key = CLIENTS[league]
        self.params = {"key": key, "client_code": client}
        self.prefix = client
        self.sleep = sleep
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA})
        self._seasons = None
        self._sched, self._teams = {}, {}

    def _json(self, **p):
        for i in range(3):
            try:
                t = self.s.get(BASE, params={**p, **self.params}, timeout=30).text.strip()
                if t.startswith("(") and t.endswith(")"):
                    t = t[1:-1]
                return json.loads(t)
            except Exception:
                if i == 2:
                    raise
                time.sleep(2)

    def season_ids(self, date: str) -> list:
        if self._seasons is None:
            self._seasons = self._json(feed="modulekit", view="seasons")["SiteKit"]["Seasons"]
        iso = f"{date[:4]}-{date[4:6]}-{date[6:]}"
        return [s["season_id"] for s in self._seasons
                if (s.get("start_date") or "") <= iso <= (s.get("end_date") or "9999")
                and "All-Star" not in s.get("season_name", "")
                and "Prospects" not in s.get("season_name", "")]

    def schedule(self, sid: str) -> list:
        if sid not in self._sched:
            self._sched[sid] = self._json(feed="modulekit", view="schedule", season_id=sid)["SiteKit"].get("Schedule") or []
            for tm in self._json(feed="modulekit", view="teamsbyseason", season_id=sid)["SiteKit"].get("Teamsbyseason") or []:
                self._teams[str(tm["id"])] = tm.get("name", "")
        return self._sched[sid]

    def _same(self, fs_name: str, tid: str) -> bool:
        a, b = _norm(fs_name), _norm(self._teams.get(str(tid), ""))
        return bool(a and b) and (a == b or b.startswith(a) or a.startswith(b))

    def find(self, date: str, home: str, away: str):
        iso = f"{date[:4]}-{date[4:6]}-{date[6:]}"
        for sid in self.season_ids(date):
            for g in self.schedule(sid):
                if g.get("date_played") == iso and self._same(home, g["home_team"]) and self._same(away, g["visiting_team"]):
                    return g["game_id"]
        return None

    def summary(self, gid: str) -> dict:
        d = self._json(feed="statviewfeed", view="gameSummary", game_id=gid, lang="en", site_id="0")
        time.sleep(self.sleep)
        return {**parse_summary(d, self.prefix), "_source_id": gid}

    def goalies(self, date: str, home: str, away: str) -> dict:
        """date = 리그 현지 경기일 YYYYMMDD (Flashscore 파일 날짜와 동일)"""
        gid = self.find(date, home, away)
        return self.summary(gid) if gid else {}
