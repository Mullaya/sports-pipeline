"""NFL 일별 경기 수집기 (ESPN 공개 API: site.api.espn.com, 키 불필요)

수집 단위: 미국 현지 날짜(YYYYMMDD) 하루치 완료 경기 (정규시즌 + 플레이오프)
- 경기 결과: 스코어, 쿼터별 득점, 연장 여부, 주차(week)
- 마감 라인: 스프레드 / 토탈 / 머니라인 (ESPN pickcenter, 있을 때만) → ATS·O/U 판정용
- 팀 경기 스탯: 퍼스트다운, 총 야드, 패싱/러싱 야드, 턴오버, 3rd down 등
- 선수 스탯: passing / rushing / receiving / defensive 등 그룹별
- 환경: 구장, 실내 여부, 날씨(실외 경기)
"""
import time
import requests

API = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"


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


class NFLCollector:

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
        raise RuntimeError(f"NFL API 실패 {path}: {last}")

    # ------------------------------------------------------------------
    def collect_daily(self, date: str) -> dict:
        """date: YYYYMMDD (미국 현지 경기 날짜)"""
        board = self._get("/scoreboard", {"dates": date}) or {}

        games = []
        for ev in board.get("events", []):
            status = (ev.get("status") or {}).get("type", {})
            if not status.get("completed"):
                continue
            # 프리시즌(1) 제외, 정규 2 / 포스트시즌 3
            if (ev.get("season") or {}).get("type") not in (2, 3):
                continue
            try:
                games.append(self._build_game(ev))
            except Exception as e:
                print(f"  [NFL] 경기 {ev.get('id')} 파싱 실패: {e}")
            time.sleep(self.sleep)

        return {"date": date, "league": "NFL", "games": games}

    # ------------------------------------------------------------------
    def _build_game(self, ev: dict) -> dict:
        gid = ev["id"]
        comp = (ev.get("competitions") or [{}])[0]
        sides = {c.get("homeAway"): c for c in comp.get("competitors", [])}
        home, away = sides.get("home", {}), sides.get("away", {})
        hs, as_ = _int(home.get("score")), _int(away.get("score"))

        h_lines = [_int(l.get("value")) for l in home.get("linescores", []) or []]
        a_lines = [_int(l.get("value")) for l in away.get("linescores", []) or []]
        overtime = max(len(h_lines), len(a_lines)) > 4

        summary = self._get("/summary", {"event": gid}) or {}
        venue = comp.get("venue") or {}
        weather = (summary.get("gameInfo") or {}).get("weather") or {}

        h_abbr = (home.get("team") or {}).get("abbreviation", "")
        a_abbr = (away.get("team") or {}).get("abbreviation", "")
        line = self._closing_line(summary, h_abbr, a_abbr)

        game = {
            "game_id": gid,
            "game_type": "REG" if (ev.get("season") or {}).get("type") == 2 else "PO",
            "season": (ev.get("season") or {}).get("year"),
            "week": (ev.get("week") or {}).get("number"),
            "start_utc": ev.get("date", ""),
            "venue": venue.get("fullName", ""),
            "indoor": venue.get("indoor"),
            "neutral_site": comp.get("neutralSite", False),
            "weather": {
                "temp_f": weather.get("temperature"),
                "condition": weather.get("displayValue"),
                "precip_pct": weather.get("precipitation"),
                "wind_mph": weather.get("windSpeed"),
            } if weather else None,
            "home_team": (home.get("team") or {}).get("displayName", ""),
            "away_team": (away.get("team") or {}).get("displayName", ""),
            "home_abbrev": h_abbr,
            "away_abbrev": a_abbr,
            "home_score": hs,
            "away_score": as_,
            "total_points": hs + as_,
            "overtime": overtime,
            "winner": h_abbr if hs > as_ else (a_abbr if as_ > hs else "TIE"),
            "home_record": self._record(home),
            "away_record": self._record(away),
            "quarter_scores": {"home": h_lines, "away": a_lines},
            "closing_line": line,
        }

        # ATS / O/U 판정 (라인이 있을 때만)
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
        game["home_players"] = players.get(h_abbr, {})
        game["away_players"] = players.get(a_abbr, {})
        return game

    # ------------------------------------------------------------------
    @staticmethod
    def _record(c: dict) -> str:
        for r in c.get("records", []) or []:
            if r.get("type") == "total":
                return r.get("summary", "")
        return ""

    @staticmethod
    def _closing_line(summary: dict, h_abbr: str = "", a_abbr: str = "") -> dict:
        """ESPN pickcenter 첫 번째 제공사 기준. home_spread는 홈팀 기준(음수 = 홈 페이버릿).
        부호는 details("BUF -3" / "EVEN")에서 읽어 확정하고, 못 읽으면 favorite 플래그로 보정."""
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
            "details": p.get("details", ""),
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
        """{팀약자: {그룹명: [{name, id, <key>: <value>...}]}}"""
        out = {}
        for t in (summary.get("boxscore") or {}).get("players", []) or []:
            abbr = (t.get("team") or {}).get("abbreviation", "")
            groups = {}
            for grp in t.get("statistics", []) or []:
                keys = grp.get("keys") or grp.get("labels") or []
                rows = []
                for a in grp.get("athletes", []) or []:
                    ath = a.get("athlete") or {}
                    row = {"id": ath.get("id"), "name": ath.get("displayName", "")}
                    row.update(dict(zip(keys, a.get("stats", []) or [])))
                    rows.append(row)
                if rows:
                    groups[grp.get("name", "")] = rows
            out[abbr] = groups
        return out
