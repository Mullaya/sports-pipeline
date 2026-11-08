"""KBL 공식 API(api.kbl.or.kr) 일별 경기 수집기 — 선수별 박스스코어 포함

네이버 스포츠 API가 GitHub Actions 서버에서 응답하지 않게 되어(2026-10-24~) 1순위 수집원으로 사용.
출력 형식은 네이버 수집기(kbl_collector.py)와 동일하고, game_id도 네이버 형식으로 맞춘다.
  game_id = 날짜 + 홈코드 + 원정코드 + 시즌코드 + 경기구분코드 + 경기번호(2자리)
  예) 20261106 70 55 49 01 55 → 202611067055490155
필드 메모(실데이터 확인): fg/fgA = 2점슛, threep/threepA = 3점슛, fgt/fgtA = 야투 전체,
  rb/offr/defr = 리바운드, bs = 블록, pscore = 페인트존 득점, dk = 덩크
"""
import time

import requests

API = "https://api.kbl.or.kr"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Origin": "https://www.kbl.or.kr",
    "Referer": "https://www.kbl.or.kr/",
    # 공식 웹사이트가 보내는 필수 헤더 (없으면 400 "필수 헤더 정보가 누락되었습니다")
    "Channel": "WEB",
    "TeamCode": "XX",
    "lang": "ko",
    "X-Requested-With": "XMLHttpRequest",
}

# 팀 코드 → (정식 이름, 줄임 이름) — 네이버 수집 데이터와 같은 표기
TEAMS = {
    "06": ("수원 KT", "KT"), "10": ("울산 현대모비스", "현대모비스"), "16": ("원주 DB", "DB"),
    "35": ("서울 삼성", "삼성"), "50": ("창원 LG", "LG"), "55": ("서울 SK", "SK"),
    "60": ("부산 KCC", "KCC"), "64": ("대구 한국가스공사", "한국가스공사"),
    "66": ("고양 소노", "고양소노"), "70": ("안양 정관장", "정관장"),
}


def _int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default


def _game_type(category: str) -> str:
    c = category or ""
    if "정규" in c:
        return "REG"
    if "챔피언" in c:
        return "FINAL"
    if "플레이오프" in c or "6강" in c or "4강" in c:
        return "PO"
    if "컵" in c:
        return "CUP"
    if "올스타" in c:
        return "ALLSTAR"
    return c or "UNKNOWN"


class KBLOfficialCollector:

    def __init__(self, sleep: float = 0.3):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.sleep = sleep

    def _get(self, path: str, retries: int = 3):
        last = None
        for i in range(retries):
            try:
                r = self.session.get(API + path, timeout=20)
                if r.status_code == 200:
                    return r.json()
                last = f"HTTP {r.status_code} {r.text[:120]}"
            except Exception as e:
                last = str(e)
            time.sleep(2 * (i + 1))
        raise RuntimeError(f"KBL 공식 API 실패 {path}: {last}")

    def collect_daily(self, date: str) -> dict:
        """date: YYYYMMDD (한국 날짜)"""
        lst = self._get(f"/match/list?fromDate={date}&toDate={date}&tcodeList=all") or []
        games = []
        for m in lst:
            if m.get("gameDate") != date or not m.get("isEnded"):
                continue
            # 1군 경기만 (D리그 등 다른 대회가 같은 목록에 섞여 옴 — 예: S49G07)
            if _game_type(m.get("seasonCategoryName")) not in ("REG", "PO", "FINAL", "CUP"):
                continue
            for attempt in range(2):
                try:
                    games.append(self._build_game(m))
                    break
                except Exception as e:
                    if attempt:
                        print(f"  [KBL] 경기 {m.get('gmkey')} 파싱 실패: {e}")
                    time.sleep(3)
        return {"date": date, "league": "KBL", "source": "kbl.or.kr", "games": games}

    # ------------------------------------------------------------------
    def _build_game(self, m: dict) -> dict:
        gk = m["gmkey"]
        detail = self._get(f"/match/{gk}") or {}
        time.sleep(self.sleep)
        team_rec = self._get(f"/match/{gk}/team-record") or []
        time.sleep(self.sleep)
        players = self._get(f"/match/{gk}/player-stat") or []
        time.sleep(self.sleep)

        g = detail.get("game") or {}
        hc, ac = str(m.get("tcodeH")), str(m.get("tcodeA"))
        hs, as_ = _int(m.get("scoreH")), _int(m.get("scoreA"))

        tr = (detail.get("teamrecords") or {})
        hq_rec, aq_rec = tr.get("home") or {}, tr.get("away") or {}
        hq = [_int(hq_rec.get(f"scoreq{i}")) for i in range(1, 5)]
        aq = [_int(aq_rec.get(f"scoreq{i}")) for i in range(1, 5)]
        quarters = [{"q": f"Q{i+1}", "home": hq[i], "away": aq[i]} for i in range(4)]
        reg_home, reg_away = sum(hq), sum(aq)
        if hs - reg_home or as_ - reg_away:
            quarters.append({"q": "OT", "home": hs - reg_home, "away": as_ - reg_away})

        # 네이버 형식 game_id (하이라이트 링크에 그대로 실려 옴 — 없으면 같은 규칙으로 조립)
        gid = None
        hl = g.get("highlightUrl") or ""
        if "/game/" in hl:
            gid = hl.rsplit("/", 1)[-1]
        if not gid or not gid.isdigit():
            gid = f"{m['gameDate']}{hc}{ac}{m.get('seasonCode')}{m.get('gameCode', '01')}{_int(m.get('gameNo')):02d}"

        st = m.get("gameStart") or "0000"
        d = m["gameDate"]
        team_by_code = {str(t.get("tcode")): t.get("records") or {} for t in team_rec}

        return {
            "game_id": gid,
            "game_type": _game_type(m.get("seasonCategoryName")),
            "round_code": "kbl_official",
            "season": int(str(m.get("seasonName1", "0"))[:4] or 0) or None,
            "start_kst": f"{d[:4]}-{d[4:6]}-{d[6:]}T{st[:2]}:{st[2:4]}:00",
            "venue": m.get("stadiumname", ""),
            "home_team": TEAMS.get(hc, (m.get("tnameH"), ""))[0],
            "away_team": TEAMS.get(ac, (m.get("tnameA"), ""))[0],
            "home_short": TEAMS.get(hc, ("", m.get("tnameH")))[1],
            "away_short": TEAMS.get(ac, ("", m.get("tnameA")))[1],
            "home_code": hc,
            "away_code": ac,
            "neutral": False,
            "series_game_no": None,
            "home_score": hs,
            "away_score": as_,
            "total_points": hs + as_,
            "margin_home": hs - as_,
            "overtime": (hs - reg_home) > 0 or (as_ - reg_away) > 0,
            "reg_home_score": reg_home,
            "reg_away_score": reg_away,
            "reg_total_points": reg_home + reg_away,
            "winner": "HOME" if hs > as_ else "AWAY",
            "quarter_scores": quarters,
            "home_stats": self._team_stats(team_by_code.get(hc, {})),
            "away_stats": self._team_stats(team_by_code.get(ac, {})),
            "home_players": self._players([p for p in players if str((p.get("player") or {}).get("tcode")) == hc]),
            "away_players": self._players([p for p in players if str((p.get("player") or {}).get("tcode")) == ac]),
        }

    @staticmethod
    def _team_stats(t: dict) -> dict:
        if not t:
            return {}
        return {
            "fgm": _int(t.get("fgt")), "fga": _int(t.get("fgtA")),
            "fg2m": _int(t.get("fg")), "fg2a": _int(t.get("fgA")),
            "fg3m": _int(t.get("threep")), "fg3a": _int(t.get("threepA")),
            "ftm": _int(t.get("ft")), "fta": _int(t.get("ftA")),
            "reb": _int(t.get("rb")), "oreb": _int(t.get("offr")), "dreb": _int(t.get("defr")),
            "ast": _int(t.get("ast")), "stl": _int(t.get("stl")), "blk": _int(t.get("bs")),
            "tov": _int(t.get("to")), "fouls": _int(t.get("foul")),
            "paint_pts": _int(t.get("pscore")), "dunks": _int(t.get("dk")),
        }

    @staticmethod
    def _players(rows: list) -> list:
        res = []
        for row in rows:
            p, r = row.get("player") or {}, row.get("records") or {}
            sec = _int(r.get("playMin")) * 60 + _int(r.get("playSec"))
            res.append({
                "player_id": p.get("pcode"),
                "name": p.get("pname", ""),
                "pos": p.get("pos", ""),
                "starter": bool(_int(row.get("startFlag"))),
                "dnp": sec == 0,
                "min": round(sec / 60, 1),
                "pts": _int(r.get("score")),
                "reb": _int(r.get("rb")), "oreb": _int(r.get("offr")), "dreb": _int(r.get("defr")),
                "ast": _int(r.get("ast")), "stl": _int(r.get("stl")), "blk": _int(r.get("bs")),
                "tov": _int(r.get("to")), "fouls": _int(r.get("foul")),
                "fg2m": _int(r.get("fg")), "fg2a": _int(r.get("fgA")),
                "fg3m": _int(r.get("threep")), "fg3a": _int(r.get("threepA")),
                "ftm": _int(r.get("ft")), "fta": _int(r.get("ftA")),
            })
        return res
