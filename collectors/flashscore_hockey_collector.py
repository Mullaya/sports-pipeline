"""유럽 하키 일별 경기 수집기 — Flashscore 피드 (키 불필요, x-fsign 공개 서명 사용)

대상 리그 (LEAGUES):
  DEL : 독일 PENNY DEL
  CZE : 체코 Tipsport Extraliga  (공식 hokej.cz는 GitHub Actions IP를 403 차단)

수집 단위: 현지(중부유럽) 날짜 YYYYMMDD 하루치 완료 경기
- 경기 결과: 최종/정규시간 스코어, REG/OT/SO, 피리어드별 득점, 스테이지(정규/PO 등)
- 팀 경기 스탯: 유효슈팅, 세이브, 블록, PP골/기회, SH골, PIM, 페이스오프 승, 빈골문 골, 히트
- 골리: 라인업 기준 선발 골리 (팀 세이브/상대 유효슈팅으로 SA·GA·SV% — 교체 시 오차 가능)
- 득점 기록: 피리어드, 시간, 득점자, 어시스트

경기 목록은 '시즌 결과 목록'(결과 페이지 + tr_ 페이지네이션)에서 가져온다.
→ 날짜 창(-7~+7일) 제한이 있는 일별 피드와 달리 지난 시즌 적재·누락 재수집에 모두 쓸 수 있다.
  한 인스턴스 안에서는 시즌 목록을 캐시하므로 초기적재 때 시즌당 목록 요청은 몇 번뿐이다.

피드 형식: 레코드 '~' 구분, 필드 '¬' 구분, 키/값 '÷' 구분.
  AA=경기ID AD=시작(unix) AB=상태(3=종료) AC=종료유형(3 정규, 10 연장, 11 승부치기)
  AE/AF=홈/원정 AG/AH=최종 AT/AU=정규시간 BA·BC·BE / BB·BD·BF=1~3피리어드 BG/BH=연장
  ZA=대회명(스테이지 포함) ZEE=대회ID
"""
import re
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

SITE = "https://www.flashscore.com"
FEED = "https://global.flashscore.ninja/2/x/feed/"
FSIGN = "SW9D1eZo"          # 사이트 설정(feed_sign)에 노출된 공개 값. 바뀌면 결과 페이지에서 재추출
LOCAL_TZ = ZoneInfo("Europe/Berlin")   # DEL·체코 공통 (CET/CEST)

LEAGUES = {
    "DEL": {"path": "hockey/germany/del", "country": "81", "tournament": "nVp0wiqd"},
    "CZE": {"path": "hockey/czech-republic/extraliga", "country": "62", "tournament": "QR1GYbvD"},
}

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _records(text: str) -> list:
    """피드 텍스트 → 레코드(dict) 리스트. 대회 헤더(ZA)는 뒤따르는 경기에 'ZA'로 붙여 준다."""
    out, za = [], None
    for blk in (text or "").split("~"):
        d = {}
        for kv in blk.split("¬"):
            if "÷" in kv:
                k, v = kv.split("÷", 1)
                d[k] = v
        if "ZA" in d:
            za = d["ZA"]
        if "AA" in d:
            d.setdefault("ZA", za or "")
            out.append(d)
    return out


def _int(x, default=None):
    try:
        return int(x)
    except Exception:
        return default


def _stage_type(za: str) -> str:
    s = (za or "").lower()
    if "pre-season" in s or "friendly" in s:
        return "PRE"
    if "play out" in s or "play-out" in s or "relegation" in s:
        return "RELEG"
    if "pre-play" in s or "play-in" in s:
        return "PLAYIN"
    if "play off" in s or "play-off" in s or "playoff" in s:
        return "PO"
    return "REG"


def season_years(date: str) -> tuple:
    """8월 이후는 그해 시작 시즌, 이전은 전년 시작 시즌"""
    d = datetime.strptime(date, "%Y%m%d")
    y = d.year if d.month >= 8 else d.year - 1
    return y, y + 1


class FlashscoreHockeyCollector:

    def __init__(self, league: str, sleep: float = 0.4):
        if league not in LEAGUES:
            raise ValueError(f"지원하지 않는 리그: {league}")
        self.league = league
        self.cfg = LEAGUES[league]
        self.sleep = sleep
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": UA, "Accept": "*/*"})
        self._season_cache = {}     # (y1, y2) -> {match_id: record}

    # ------------------------------------------------------------------
    def _get(self, url: str, feed: bool = False, retries: int = 3) -> str:
        headers = {"x-fsign": FSIGN, "Referer": SITE + "/", "Origin": SITE} if feed else {}
        last = None
        for i in range(retries):
            try:
                r = self.session.get(url, headers=headers, timeout=25)
                if r.status_code == 200:
                    return r.text
                last = f"HTTP {r.status_code}"
            except Exception as e:
                last = str(e)
            time.sleep(2 * (i + 1))
        raise RuntimeError(f"Flashscore 요청 실패 {url}: {last}")

    def season_matches(self, y1: int, y2: int) -> dict:
        """시즌 전체 경기 레코드 (결과 페이지 초기 데이터 + tr_ 페이지네이션)"""
        key = (y1, y2)
        if key in self._season_cache:
            return self._season_cache[key]

        html = self._get(f"{SITE}/{self.cfg['path']}-{y1}-{y2}/results/")
        sid = re.search(r"seasonId:\s*(\d+)", html)
        if not sid:
            raise RuntimeError(f"{self.league} {y1}-{y2} seasonId를 찾지 못함 (페이지 구조 변경?)")
        sid = sid.group(1)
        tour = re.search(r'tournament_id"\s*:\s*"(\w+)"', html)
        tour = tour.group(1) if tour else self.cfg["tournament"]
        total = re.search(r"allEventsCount:\s*(\d+)", html)

        recs = {}
        m = re.search(r'initialFeeds\["summary-results"\]\s*=\s*\{\s*data:\s*`(.*?)`', html, re.S)
        for r in _records(m.group(1) if m else ""):
            recs[r["AA"]] = r
        for page in range(1, 30):
            text = self._get(f"{FEED}tr_4_{self.cfg['country']}_{tour}_{sid}_{page}_0_en_2", feed=True)
            batch = _records(text)
            if not batch:
                break
            for r in batch:
                recs.setdefault(r["AA"], r)
            time.sleep(self.sleep)

        if total and len(recs) < int(total.group(1)):
            print(f"  [{self.league}] ⚠️ {y1}-{y2} 목록 {len(recs)}/{total.group(1)}경기만 확인됨")
        self._season_cache[key] = recs
        return recs

    # ------------------------------------------------------------------
    def collect_daily(self, date: str) -> dict:
        """date: YYYYMMDD (중부유럽 현지 경기 날짜)"""
        y1, y2 = season_years(date)
        games = []
        for rec in sorted(self.season_matches(y1, y2).values(), key=lambda r: _int(r.get("AD"), 0)):
            if rec.get("AB") != "3":          # 종료 경기만
                continue
            st = _int(rec.get("AD"))
            if not st:
                continue
            local = datetime.fromtimestamp(st, timezone.utc).astimezone(LOCAL_TZ)
            if local.strftime("%Y%m%d") != date:
                continue
            try:
                games.append(self._build_game(rec))
            except Exception as e:
                print(f"  [{self.league}] 경기 {rec.get('AA')} 파싱 실패: {e}")
            time.sleep(self.sleep)
        return {"date": date, "league": self.league, "source": "flashscore", "games": games}

    # ------------------------------------------------------------------
    def _build_game(self, r: dict) -> dict:
        mid = r["AA"]
        hs, as_ = _int(r.get("AG"), 0), _int(r.get("AH"), 0)
        periods = []
        for i, (a, b) in enumerate((("BA", "BB"), ("BC", "BD"), ("BE", "BF")), 1):
            if a in r or b in r:
                periods.append({"period": i, "type": "REG", "home": _int(r.get(a), 0), "away": _int(r.get(b), 0)})
        reg_h = sum(p["home"] for p in periods)
        reg_a = sum(p["away"] for p in periods)
        if "AT" in r and "AU" in r:
            reg_h, reg_a = _int(r["AT"], reg_h), _int(r["AU"], reg_a)

        ac = r.get("AC")
        if ac == "11" or "RPA" in r:
            end_type = "SO"
        elif ac == "10" or (hs, as_) != (reg_h, reg_a):
            end_type = "OT"
        else:
            end_type = "REG"
        if "BG" in r or "BH" in r:
            periods.append({"period": 4, "type": "OT", "home": _int(r.get("BG"), 0), "away": _int(r.get("BH"), 0)})

        stats = self._stats(mid)
        time.sleep(self.sleep)
        starters = self._starting_goalies(mid)
        time.sleep(self.sleep)
        goals = self._goals(mid)

        h_st, a_st = stats.get("home", {}), stats.get("away", {})
        return {
            "game_id": mid,
            "game_type": _stage_type(r.get("ZA")),
            "stage": r.get("ZA", ""),
            "round": r.get("ER", ""),
            "start_utc": datetime.fromtimestamp(_int(r["AD"]), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "home_team": r.get("AE", ""),
            "away_team": r.get("AF", ""),
            "home_team_id": r.get("PX"),
            "away_team_id": r.get("PY"),
            "home_score": hs,
            "away_score": as_,
            "total_goals": hs + as_,
            "end_type": end_type,               # REG / OT / SO
            "reg_home_score": reg_h,            # 3-way(정규 60분) 판정용
            "reg_away_score": reg_a,
            "reg_total_goals": reg_h + reg_a,
            "winner": r.get("AE") if hs > as_ else r.get("AF"),
            "period_scores": periods,
            "home_stats": h_st,
            "away_stats": a_st,
            "home_goalies": self._goalie_line(starters.get("home"), opp=a_st, own=h_st),
            "away_goalies": self._goalie_line(starters.get("away"), opp=h_st, own=a_st),
            "goals": goals,
        }

    # ------------------------------------------------------------------
    STAT_KEYS = {
        "Shots on Goal": "shots", "Goalkeeper Saves": "saves", "Blocked shots": "blocked",
        "Power-play Goals": "pp_goals", "Shorthanded Goals": "sh_goals", "PIM": "pim",
        "Faceoffs Won": "fo_won", "Empty Net Goals": "en_goals", "Hits": "hits",
        "Penalties": "penalties",
    }

    def _stats(self, mid: str) -> dict:
        """경기 전체(Match) 섹션만 사용. PP 기회는 'Power-play PCT'의 (골/기회)에서 추출"""
        text = self._get(f"{FEED}df_st_1_{mid}", feed=True)
        home, away = {}, {}
        section = None
        for blk in text.split("~"):
            d = dict(kv.split("÷", 1) for kv in blk.split("¬") if "÷" in kv)
            if "SE" in d:
                section = d["SE"]
                continue
            if section != "Match" or "SG" not in d:
                continue
            name, hv, av = d["SG"], d.get("SH", ""), d.get("SI", "")
            if name in self.STAT_KEYS:
                k = self.STAT_KEYS[name]
                home[k], away[k] = _int(hv), _int(av)
            elif name == "Power-play PCT":
                for side, v in ((home, hv), (away, av)):
                    m = re.search(r"\((\d+)/(\d+)\)", v)
                    if m:
                        side["pp_opps"] = int(m.group(2))
        if not home:
            return {}
        return {"home": home, "away": away}

    def _starting_goalies(self, mid: str) -> dict:
        """라인업 'Line 1'의 (G) = 선발 골리. LC÷1 홈, LC÷2 원정"""
        try:
            text = self._get(f"{FEED}df_li_1_{mid}", feed=True)
        except Exception:
            return {}
        out, line, side = {}, None, None
        for blk in text.split("~"):
            d = dict(kv.split("÷", 1) for kv in blk.split("¬") if "÷" in kv)
            if "LB" in d:
                line = d["LB"]
            if "LC" in d:
                side = "home" if d["LC"] == "1" else "away"
            if line == "Line 1" and d.get("LR") == "(G)" and side and side not in out:
                out[side] = {"name": d.get("LI", ""), "player_id": d.get("LP")}
        return out

    @staticmethod
    def _goalie_line(starter, opp: dict, own: dict) -> list:
        if not starter:
            return []
        sa = opp.get("shots")
        saves = own.get("saves")
        if sa is None or saves is None:
            return [{**starter, "starter": True, "shots_against": None,
                     "goals_against": None, "saves": None, "sv_pct": None}]
        ga = max(sa - saves, 0)
        return [{**starter, "starter": True, "shots_against": sa, "goals_against": ga,
                 "saves": saves, "sv_pct": round(saves / sa, 3) if sa else None,
                 "note": "팀 세이브 기준(골리 교체 시 합산값)"}]

    def _goals(self, mid: str) -> list:
        """득점 이벤트: IK=Goal 레코드 + 뒤따르는 Assistance"""
        try:
            text = self._get(f"{FEED}df_sui_1_{mid}", feed=True)
        except Exception:
            return []
        goals, period = [], None
        for blk in text.split("~"):
            if blk.startswith("AC÷"):
                period = blk.split("¬")[0][3:]
                continue
            if not blk.startswith("III÷"):
                continue
            # 한 이벤트 안에 득점자·어시스트가 IF/IK 쌍으로 이어진다
            pairs = re.findall(r"IF÷([^¬]*)¬(?:[^~]*?)IK÷([^¬]*)", blk)
            kinds = [k for _, k in pairs]
            if not kinds or kinds[0] != "Goal":
                continue
            side = re.search(r"IA÷(\d)", blk)
            tm = re.search(r"IB÷([^¬]*)", blk)
            sc = re.search(r"INX÷(\d+)¬IOX÷(\d+)", blk)
            goals.append({
                "period": period,
                "time": tm.group(1) if tm else "",
                "team": "home" if side and side.group(1) == "1" else "away",
                "score": f"{sc.group(1)}:{sc.group(2)}" if sc else "",
                "author": pairs[0][0],
                "assists": [n for n, k in pairs[1:] if k.startswith("Assist")],
            })
        return goals
