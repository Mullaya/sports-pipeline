"""NHL 일별 경기 수집기 (NHL 공식 공개 API: api-web.nhle.com, 키 불필요)

수집 단위: 북미 현지 날짜(YYYYMMDD) 하루치 완료 경기
- 경기 결과: 스코어, 정규/연장/승부치기 구분, 피리어드별 득점
- 팀 경기 스탯: 유효슈팅, 파워플레이, PIM, 히트, 블락, 페이스오프, 턴오버
- 골리: 선발 여부, 세이브/유효슈팅, SV%, 실점, TOI, 결과(W/L/O)
- 스케이터: 골/어시/포인트/+-/슈팅/TOI/PP골
"""
import time
import requests

API = "https://api-web.nhle.com/v1"


def _name(obj):
    """NHL API는 이름을 {"default": "..."} 형태로 줌"""
    if isinstance(obj, dict):
        return obj.get("default", "")
    return obj or ""


def _toi_to_min(toi: str) -> float:
    """'59:41' -> 59.68"""
    try:
        m, s = str(toi).split(":")
        return round(int(m) + int(s) / 60, 2)
    except Exception:
        return 0.0


def _frac(s):
    """'1/3' -> (1, 3)"""
    try:
        a, b = str(s).split("/")
        return int(a), int(b)
    except Exception:
        return 0, 0


class NHLCollector:

    def __init__(self, sleep: float = 0.4):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "sports-pipeline/1.0"})
        self.sleep = sleep

    def _get(self, path: str, retries: int = 3):
        url = f"{API}{path}"
        last = None
        for i in range(retries):
            try:
                r = self.session.get(url, timeout=20)
                if r.status_code == 200:
                    return r.json()
                if r.status_code == 404:
                    return None
                last = f"HTTP {r.status_code}"
            except Exception as e:
                last = str(e)
            time.sleep(2 * (i + 1))
        raise RuntimeError(f"NHL API 실패 {path}: {last}")

    # ------------------------------------------------------------------
    def collect_daily(self, date: str) -> dict:
        """date: YYYYMMDD (북미 현지 경기 날짜)"""
        iso = f"{date[:4]}-{date[4:6]}-{date[6:]}"
        score = self._get(f"/score/{iso}") or {}

        games = []
        for g in score.get("games", []):
            # 완료 경기만 (OFF/FINAL). 프리시즌(gameType 1)은 제외, 정규 2 / 플옵 3
            if g.get("gameState") not in ("OFF", "FINAL"):
                continue
            if g.get("gameType") not in (2, 3):
                continue
            try:
                games.append(self._build_game(g))
            except Exception as e:
                print(f"  [NHL] 경기 {g.get('id')} 파싱 실패: {e}")
            time.sleep(self.sleep)

        return {"date": date, "league": "NHL", "games": games}

    # ------------------------------------------------------------------
    def _build_game(self, g: dict) -> dict:
        gid = g["id"]
        home, away = g.get("homeTeam", {}), g.get("awayTeam", {})
        hs, as_ = home.get("score", 0), away.get("score", 0)

        end_type = (g.get("gameOutcome") or {}).get("lastPeriodType") \
            or (g.get("periodDescriptor") or {}).get("periodType", "REG")

        box = self._get(f"/gamecenter/{gid}/boxscore") or {}
        time.sleep(self.sleep)
        rail = self._get(f"/gamecenter/{gid}/right-rail") or {}

        team_stats = self._team_stats(rail, box, home, away)
        periods = self._period_scores(g, rail)

        # 정규시간(60분) 스코어: 연장/SO 승리 골 1개 제외
        reg_home, reg_away = hs, as_
        if end_type in ("OT", "SO"):
            if hs > as_:
                reg_home = hs - 1
            else:
                reg_away = as_ - 1

        pbg = box.get("playerByGameStats", {})
        return {
            "game_id": gid,
            "game_type": "REG" if g.get("gameType") == 2 else "PO",
            "start_utc": g.get("startTimeUTC", ""),
            "venue": _name(g.get("venue")),
            "home_team": _name(home.get("name")) or home.get("abbrev", ""),
            "away_team": _name(away.get("name")) or away.get("abbrev", ""),
            "home_abbrev": home.get("abbrev", ""),
            "away_abbrev": away.get("abbrev", ""),
            "home_score": hs,
            "away_score": as_,
            "total_goals": hs + as_,
            "end_type": end_type,              # REG / OT / SO
            "reg_home_score": reg_home,        # 3-way(정규시간) 판정용
            "reg_away_score": reg_away,
            "reg_total_goals": reg_home + reg_away,
            "winner": home.get("abbrev") if hs > as_ else away.get("abbrev"),
            "period_scores": periods,
            "home_stats": team_stats["home"],
            "away_stats": team_stats["away"],
            "home_goalies": self._goalies(pbg.get("homeTeam", {})),
            "away_goalies": self._goalies(pbg.get("awayTeam", {})),
            "home_skaters": self._skaters(pbg.get("homeTeam", {})),
            "away_skaters": self._skaters(pbg.get("awayTeam", {})),
        }

    # ------------------------------------------------------------------
    def _team_stats(self, rail, box, home, away) -> dict:
        out = {"home": {}, "away": {}}
        for row in rail.get("teamGameStats", []) or []:
            cat = row.get("category")
            hv, av = row.get("homeValue"), row.get("awayValue")
            if cat == "powerPlay":
                hg, ho = _frac(hv)
                ag, ao = _frac(av)
                out["home"].update(pp_goals=hg, pp_opps=ho)
                out["away"].update(pp_goals=ag, pp_opps=ao)
            elif cat in ("sog", "pim", "hits", "blockedShots",
                         "giveaways", "takeaways", "faceoffWinningPctg"):
                key = {"sog": "shots", "blockedShots": "blocked",
                       "faceoffWinningPctg": "fo_pct"}.get(cat, cat)
                out["home"][key] = hv
                out["away"][key] = av
        # right-rail 실패 시 스코어보드 SOG로 보완
        out["home"].setdefault("shots", home.get("sog", box.get("homeTeam", {}).get("sog", 0)))
        out["away"].setdefault("shots", away.get("sog", box.get("awayTeam", {}).get("sog", 0)))
        for side in ("home", "away"):
            out[side].setdefault("pp_goals", 0)
            out[side].setdefault("pp_opps", 0)
        return out

    def _period_scores(self, g, rail) -> list:
        lines = (rail.get("linescore") or {}).get("byPeriod") or []
        res = []
        for p in lines:
            pd = p.get("periodDescriptor", {})
            res.append({
                "period": pd.get("number"),
                "type": pd.get("periodType", "REG"),
                "home": p.get("home", 0),
                "away": p.get("away", 0),
            })
        if res:
            return res
        # 보완: goals 목록으로 계산
        agg = {}
        for goal in g.get("goals", []) or []:
            pd = goal.get("periodDescriptor", {})
            n = pd.get("number")
            agg.setdefault(n, {"period": n, "type": pd.get("periodType", "REG"), "home": 0, "away": 0})
            side = "home" if goal.get("isHome") else "away"
            agg[n][side] += 1
        return [agg[k] for k in sorted(agg)]

    def _goalies(self, team: dict) -> list:
        res = []
        for gk in team.get("goalies", []) or []:
            toi = _toi_to_min(gk.get("toi", "0:00"))
            if toi <= 0:
                continue  # 미출전 백업
            sa = gk.get("shotsAgainst")
            ga = gk.get("goalsAgainst", 0)
            if sa is None:
                sv, sa = _frac(gk.get("saveShotsAgainst", "0/0"))
            else:
                sv = gk.get("saves", sa - ga)
            res.append({
                "player_id": gk.get("playerId"),
                "name": _name(gk.get("name")),
                "starter": bool(gk.get("starter", False)),
                "decision": gk.get("decision", ""),
                "toi": toi,
                "shots_against": sa,
                "saves": sv,
                "goals_against": ga,
                "sv_pct": round(sv / sa, 3) if sa else None,
            })
        return res

    def _skaters(self, team: dict) -> list:
        res = []
        for grp in ("forwards", "defense"):
            for s in team.get(grp, []) or []:
                res.append({
                    "player_id": s.get("playerId"),
                    "name": _name(s.get("name")),
                    "pos": s.get("position", "D" if grp == "defense" else "F"),
                    "g": s.get("goals", 0),
                    "a": s.get("assists", 0),
                    "pts": s.get("points", 0),
                    "pm": s.get("plusMinus", 0),
                    "sog": s.get("sog", s.get("shots", 0)),
                    "ppg": s.get("powerPlayGoals", 0),
                    "hits": s.get("hits", 0),
                    "blk": s.get("blockedShots", 0),
                    "pim": s.get("pim", 0),
                    "toi": _toi_to_min(s.get("toi", "0:00")),
                })
        return res
