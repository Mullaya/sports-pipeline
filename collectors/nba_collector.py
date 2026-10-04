"""NBA 일별 경기 수집기 (ESPN 공개 API: site.api.espn.com, 키 불필요)

수집 단위: 미국 현지 날짜(YYYYMMDD) 하루치 완료 경기 (정규시즌 + 플레이인 + 플레이오프)
- 경기 결과: 스코어, 쿼터별 득점, 연장 여부
- 마감 라인: 스프레드 / 토탈 / 머니라인 (ESPN pickcenter) → ATS·O/U 자동 판정
- 팀 경기 스탯: FG/3P/FT, 리바운드, 어시스트, 턴오버, 스틸, 블락 등
- 선수 스탯: 출전 시간, 득점, 리바운드, 어시스트 등 + 선발/결장(DNP) 여부
"""
import time
import requests

API = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"

# ESPN season.type: 1 프리시즌 / 2 정규 / 3 플레이오프 / 5 플레이인
SEASON_TYPES = {2: "REG", 3: "PO", 5: "PLAYIN"}


def _int(x, default=0):
    try:
        return int(float(x))
    except Exception:
        return default


def _float(x):
    try:
        return float(x)
    except Exception:
        return None


class NBACollector:

    def __init__(self, sleep: float = 0.4):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "sports-pipeline/1.0"})
        self.sleep = sleep

    def _get(self, path: str, params: dict = None, retries: int = 3):
        url = f"{API}{path}"
        last = None
        for i in range(retries):
            try:
                r = self.session.get(url, params=params, timeout=20)
                if r.status_code == 200:
                    return r.json()
                if r.status_code == 404:
                    return None
                last = f"HTTP {r.status_code}"
            except Exception as e:
                last = str(e)
            time.sleep(2 * (i + 1))
        raise RuntimeError(f"NBA API 실패 {path}: {last}")

    # ------------------------------------------------------------------
    def collect_daily(self, date: str) -> dict:
        """date: YYYYMMDD (미국 현지 경기 날짜)"""
        board = self._get("/scoreboard", {"dates": date}) or {}

        games = []
        for ev in board.get("events", []):
            if not ((ev.get("status") or {}).get("type") or {}).get("completed"):
                continue
            if (ev.get("season") or {}).get("type") not in SEASON_TYPES:
                continue
            try:
                games.append(self._build_game(ev))
            except Exception as e:
                print(f"  [NBA] 경기 {ev.get('id')} 파싱 실패: {e}")
            time.sleep(self.sleep)

        return {"date": date, "league": "NBA", "games": games}

    # ------------------------------------------------------------------
    def _build_game(self, ev: dict) -> dict:
        gid = ev["id"]
        comp = (ev.get("competitions") or [{}])[0]
        sides = {c.get("homeAway"): c for c in comp.get("competitors", [])}
        home, away = sides.get("home", {}), sides.get("away", {})
        hs, as_ = _int(home.get("score")), _int(away.get("score"))

        h_lines = [_int(l.get("value")) for l in home.get("linescores", []) or []]
        a_lines = [_int(l.get("value")) for l in away.get("linescores", []) or []]
        ot_periods = max(len(h_lines), len(a_lines)) - 4

        summary = self._get("/summary", {"event": gid}) or {}
        venue = comp.get("venue") or {}
        h_abbr = (home.get("team") or {}).get("abbreviation", "")
        a_abbr = (away.get("team") or {}).get("abbreviation", "")
        line = self._closing_line(summary, h_abbr, a_abbr)

        game = {
            "game_id": gid,
            "game_type": SEASON_TYPES.get((ev.get("season") or {}).get("type"), "REG"),
            "season": (ev.get("season") or {}).get("year"),
            "start_utc": ev.get("date", ""),
            "venue": venue.get("fullName", ""),
            "neutral_site": comp.get("neutralSite", False),
            "home_team": (home.get("team") or {}).get("displayName", ""),
            "away_team": (away.get("team") or {}).get("displayName", ""),
            "home_abbrev": h_abbr,
            "away_abbrev": a_abbr,
            "home_score": hs,
            "away_score": as_,
            "total_points": hs + as_,
            "overtime": ot_periods > 0,
            "ot_periods": max(ot_periods, 0),
            # 정규시간(48분) 스코어 — 연장 경기 4Q 종료 시점 동점
            "reg_home_score": sum(h_lines[:4]) if h_lines else hs,
            "reg_away_score": sum(a_lines[:4]) if a_lines else as_,
            "winner": h_abbr if hs > as_ else a_abbr,
            "home_record": self._record(home),
            "away_record": self._record(away),
            "quarter_scores": {"home": h_lines, "away": a_lines},
            "closing_line": line,
        }

        if line.get("home_spread") is not None:
            margin = hs - as_ + line["home_spread"]
            game["ats_winner"] = h_abbr if margin > 0 else (a_abbr if margin < 0 else "PUSH")
        if line.get("total") is not None:
            t = hs + as_
            game["ou_result"] = "OVER" if t > line["total"] else ("UNDER" if t < line["total"] else "PUSH")

        team_stats = self._team_stats(summary)
        game["home_stats"] = team_stats.get(h_abbr, {})
        game["away_stats"] = team_stats.get(a_abbr, {})
        players = self._players(summary)
        game["home_players"] = players.get(h_abbr, [])
        game["away_players"] = players.get(a_abbr, [])
        return game

    # ------------------------------------------------------------------
    @staticmethod
    def _record(c: dict) -> str:
        for r in c.get("records", []) or []:
            if r.get("type") == "total":
                return r.get("summary", "")
        return ""

    @staticmethod
    def _closing_line(summary: dict, h_abbr: str, a_abbr: str) -> dict:
        """home_spread는 홈팀 기준(음수 = 홈 페이버릿). details("BOS -5.5")로 부호 확정."""
        pcs = summary.get("pickcenter") or []
        if not pcs:
            return {}
        p = pcs[0]
        hto, ato = p.get("homeTeamOdds") or {}, p.get("awayTeamOdds") or {}
        details = (p.get("details") or "").strip()
        spread = None
        parts = details.split()
        if details.upper() == "EVEN":
            spread = 0.0
        elif len(parts) == 2 and _float(parts[1]) is not None:
            fav, val = parts[0], abs(_float(parts[1]))
            if fav == h_abbr:
                spread = -val
            elif fav == a_abbr:
                spread = val
        if spread is None:
            raw = _float(p.get("spread"))
            if raw is not None:
                spread = -abs(raw) if hto.get("favorite") else abs(raw)
        return {
            "provider": (p.get("provider") or {}).get("name", ""),
            "details": details,
            "home_spread": spread,
            "total": _float(p.get("overUnder")),
            "home_ml": hto.get("moneyLine"),
            "away_ml": ato.get("moneyLine"),
        }

    @staticmethod
    def _team_stats(summary: dict) -> dict:
        out = {}
        for t in (summary.get("boxscore") or {}).get("teams", []) or []:
            abbr = (t.get("team") or {}).get("abbreviation", "")
            out[abbr] = {s.get("name"): s.get("displayValue")
                         for s in t.get("statistics", []) or [] if s.get("name")}
        return out

    @staticmethod
    def _players(summary: dict) -> dict:
        """{팀약자: [{id, name, pos, starter, dnp, <key>: <value>...}]}"""
        out = {}
        for t in (summary.get("boxscore") or {}).get("players", []) or []:
            abbr = (t.get("team") or {}).get("abbreviation", "")
            rows = []
            for grp in t.get("statistics", []) or []:
                keys = grp.get("keys") or grp.get("labels") or []
                for a in grp.get("athletes", []) or []:
                    ath = a.get("athlete") or {}
                    row = {
                        "id": ath.get("id"),
                        "name": ath.get("displayName", ""),
                        "pos": (ath.get("position") or {}).get("abbreviation", ""),
                        "starter": bool(a.get("starter")),
                        "dnp": bool(a.get("didNotPlay")),
                    }
                    if a.get("didNotPlay"):
                        row["dnp_reason"] = a.get("reason", "")
                    else:
                        row.update(dict(zip(keys, a.get("stats", []) or [])))
                    rows.append(row)
            out[abbr] = rows
        return out
