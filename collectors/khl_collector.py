"""KHL 일별 경기 수집기 (KHL 공식 모바일 앱 API: khl.api.webcaster.pro, 키 불필요)

수집 단위: 모스크바 날짜(YYYYMMDD, UTC+3) 하루치 완료 경기
- 경기 결과: 스코어, 정규/연장/승부치기(SO) 구분, 피리어드별 득점
- 팀 경기 스탯: 유효슈팅, 파워플레이(골/기회), 숏핸디드 골, PIM, 페이스오프 승
- 골리 / 스케이터: 경기 스탯 (match_stats 원본 항목을 dict로 정리)
- 득점 기록: 시간, 피리어드, PP/SH/EN 구분

참고: 오류도 HTTP 200 + {"error": {...}} 로 내려옴.
"""
import time
from datetime import datetime, timedelta, timezone

import requests

API = "https://khl.api.webcaster.pro/api/khl_mobile"
MSK = timezone(timedelta(hours=3))


def _unwrap(obj):
    """{"event": {...}} 래핑 해제"""
    if isinstance(obj, dict) and "event" in obj and isinstance(obj["event"], dict):
        return obj["event"]
    return obj


def _int(x, default=0):
    try:
        return int(float(x))
    except Exception:
        return default


def _pair(s):
    """'3:2' -> (3, 2) / None -> None"""
    if s in (None, "", "-"):
        return None
    try:
        a, b = str(s).replace("-", ":").split(":")[:2]
        return int(a), int(b)
    except Exception:
        return None


def _stats_dict(match_stats):
    """match_stats가 [{title/key, val}] 리스트든 dict든 평평한 dict로"""
    if isinstance(match_stats, dict):
        return match_stats
    out = {}
    for s in match_stats or []:
        if isinstance(s, dict):
            k = s.get("key") or s.get("id") or s.get("title")
            if k is not None:
                out[str(k)] = s.get("val", s.get("value"))
    return out


class KHLCollector:

    def __init__(self, sleep: float = 0.5):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "sports-pipeline/1.0"})
        self.sleep = sleep

    def _get(self, path: str, params=None, retries: int = 3):
        url = f"{API}/{path}"
        last = None
        for i in range(retries):
            try:
                r = self.session.get(url, params=params, timeout=25)
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, dict) and "error" in data:
                        if (data["error"] or {}).get("code") == 404:
                            return None
                        last = f"API error {data['error']}"
                    else:
                        return data
                elif r.status_code == 404:
                    return None
                else:
                    last = f"HTTP {r.status_code}"
            except Exception as e:
                last = str(e)
            time.sleep(2 * (i + 1))
        raise RuntimeError(f"KHL API 실패 {path}: {last}")

    # ------------------------------------------------------------------
    def collect_daily(self, date: str) -> dict:
        """date: YYYYMMDD (모스크바 기준 경기 날짜)"""
        day = datetime.strptime(date, "%Y%m%d").replace(tzinfo=MSK)
        t0, t1 = int(day.timestamp()), int((day + timedelta(days=1)).timestamp())

        events, page = [], 1
        while page <= 10:
            params = [
                ("locale", "en"),
                ("q[start_at_gt_time_from_unixtime]", t0 - 1),
                ("q[start_at_lt_time_from_unixtime]", t1),
                ("order_direction", "asc"),
                ("page", page),
            ]
            batch = self._get("events_v2.json", params) or []
            if isinstance(batch, dict):
                batch = batch.get("events") or batch.get("data") or []
            if not batch:
                break
            events.extend(_unwrap(e) for e in batch)
            if len(batch) < 16:
                break
            page += 1
            time.sleep(self.sleep)

        games, seen = [], set()
        for ev in events:
            if ev.get("id") in seen:
                continue
            seen.add(ev.get("id"))
            if ev.get("game_state_key") != "finished":
                continue
            # 시간 필터가 무시되는 경우 대비: 모스크바 날짜 재확인
            st = _int(ev.get("start_at")) // 1000
            if st and not (t0 <= st < t1):
                continue
            try:
                games.append(self._build_game(ev))
            except Exception as e:
                print(f"  [KHL] 경기 {ev.get('id')} 파싱 실패: {e}")
            time.sleep(self.sleep)

        return {"date": date, "league": "KHL", "games": games}

    # ------------------------------------------------------------------
    def _build_game(self, ev: dict) -> dict:
        det = _unwrap(self._get("event_v2.json", {"id": ev["id"], "locale": "en"}) or {}) or {}
        g = {**ev, **det}

        ta, tb = g.get("team_a") or {}, g.get("team_b") or {}
        sc = _pair(g.get("score")) or (_int(ta.get("gf")), _int(tb.get("gf")))
        a_score, b_score = sc

        scores = g.get("scores") or {}
        so = _pair(scores.get("bullitt"))
        ot = _pair(scores.get("overtime"))
        if so is not None:
            end_type = "SO"
        elif ot is not None and sum(ot) > 0:
            end_type = "OT"
        else:
            end_type = "REG"

        periods = []
        for i, k in enumerate(("first_period", "second_period", "third_period"), 1):
            p = _pair(scores.get(k))
            if p:
                periods.append({"period": i, "type": "REG", "a": p[0], "b": p[1]})
        if ot is not None:
            periods.append({"period": 4, "type": "OT", "a": ot[0], "b": ot[1]})

        # KHL은 team_a = 홈팀 (khl.ru 표기 관례). 경기장 도시와 대조해 확인 플래그 기록
        arena = g.get("arena") or {}
        city = (arena.get("city") or "").lower()
        home_check = None
        if city:
            if city in (ta.get("location") or "").lower():
                home_check = "team_a"
            elif city in (tb.get("location") or "").lower():
                home_check = "team_b"
        home, away = (tb, ta) if home_check == "team_b" else (ta, tb)
        hs, as_ = (b_score, a_score) if home_check == "team_b" else (a_score, b_score)

        reg_h, reg_a = hs, as_
        if end_type in ("OT", "SO"):
            if hs > as_:
                reg_h -= 1
            else:
                reg_a -= 1

        def side(t):
            return {
                "shots": t.get("shots"),
                "pp_goals": t.get("ppg"),
                "pp_opps": t.get("ppc"),
                "sh_goals": t.get("shg"),
                "pim": t.get("pim"),
                "fo_won": t.get("vbr"),
            }

        def flip(p):
            if home_check == "team_b":
                return {"period": p["period"], "type": p["type"], "home": p["b"], "away": p["a"]}
            return {"period": p["period"], "type": p["type"], "home": p["a"], "away": p["b"]}

        return {
            "game_id": g.get("id"),
            "khl_id": g.get("khl_id"),
            "stage_id": g.get("stage_id"),
            "game_type": "PO" if "playoff" in str(g.get("stage_type") or g.get("stage_name") or "").lower() else "REG",
            "start_utc": datetime.fromtimestamp(_int(g.get("start_at")) / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if g.get("start_at") else "",
            "venue": arena.get("name", ""),
            "venue_city": arena.get("city", ""),
            "home_verified": home_check is not None,
            "home_team": home.get("name", ""),
            "away_team": away.get("name", ""),
            "home_team_id": home.get("id"),
            "away_team_id": away.get("id"),
            "home_score": hs,
            "away_score": as_,
            "total_goals": hs + as_,
            "end_type": end_type,               # REG / OT / SO
            "reg_home_score": reg_h,            # 3-way(정규시간) 판정용
            "reg_away_score": reg_a,
            "reg_total_goals": reg_h + reg_a,
            "winner": home.get("name") if hs > as_ else away.get("name"),
            "period_scores": [flip(p) for p in periods],
            "home_stats": side(home),
            "away_stats": side(away),
            "home_goalies": self._players(home, goalies=True),
            "away_goalies": self._players(away, goalies=True),
            "home_skaters": self._players(home, goalies=False),
            "away_skaters": self._players(away, goalies=False),
            "goals": [
                {
                    "period": x.get("period"),
                    "time_s": x.get("time"),
                    "score": x.get("score"),
                    "type": x.get("status_abbr", ""),
                    "author": (x.get("author") or {}).get("name", ""),
                }
                for x in g.get("goals", []) or []
            ],
        }

    @staticmethod
    def _players(team: dict, goalies: bool) -> list:
        res = []
        for p in team.get("players", []) or []:
            role = str(p.get("role_key", "")).lower()
            is_g = role.startswith("goal")
            if is_g != goalies:
                continue
            stats = _stats_dict(p.get("match_stats"))
            if not stats:
                continue  # 미출전
            res.append({
                "player_id": p.get("id"),
                "name": p.get("name", ""),
                "number": p.get("shirt_number"),
                "role": role,
                "stats": stats,
            })
        return res
