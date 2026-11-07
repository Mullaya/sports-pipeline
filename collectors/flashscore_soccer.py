"""축구(J리그·K리그) 일별 경기 수집기 — Flashscore 피드 (유럽 하키 수집기와 같은 피드·서명 사용)

대상 리그 (SOCCER_LEAGUES):
  J1 / J2 / J3 : 일본 J리그 (2026-27 시즌부터 8월~5월 추계춘제 → 시즌 URL "-2026-2027")
  K1 / K2      : 한국 K리그1·K리그2 (춘추제 → 시즌 URL "-2026")

수집 단위: 현지 날짜(J리그 Asia/Tokyo, K리그 Asia/Seoul) YYYYMMDD 하루치 종료 경기
- 결과: 최종 스코어, 전·후반 스코어, 스테이지(정규/파이널A·B/플레이오프), 라운드
- 팀 스탯: Flashscore 경기 통계 'Match' 구간 전부 (xG, 점유율, 슈팅, 유효슈팅, 코너킥, 카드 등)
  → 키는 통계명을 소문자 snake_case로 바꿔 저장, 숫자는 %·괄호를 떼고 숫자로 변환
- 득점 기록: 시간, 팀, 득점자(가능한 경우)

시즌 URL은 후보(-y1-y2, -y, 접미사 없음)를 차례로 시도해 seasonId가 있는 첫 페이지를 쓴다.
→ J리그 시즌 전환(2026 특별대회 → 2026-27)이나 K리그 단일연도 표기 모두 같은 코드로 처리.
"""
import re
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from collectors.flashscore_hockey_collector import (
    FEED, SITE, FlashscoreHockeyCollector, LEAGUES, _records, _int,
)

SOCCER_LEAGUES = {
    "J1": {"path": "football/japan/j1-league", "country": "109", "tournament": None,
           "tz": "Asia/Tokyo", "calendar": "split"},
    "J2": {"path": "football/japan/j2-league", "country": "109", "tournament": None,
           "tz": "Asia/Tokyo", "calendar": "split"},
    "J3": {"path": "football/japan/j3-league", "country": "109", "tournament": None,
           "tz": "Asia/Tokyo", "calendar": "split"},
    "K1": {"path": "football/south-korea/k-league-1", "country": "106", "tournament": None,
           "tz": "Asia/Seoul", "calendar": "year"},
    "K2": {"path": "football/south-korea/k-league-2", "country": "106", "tournament": None,
           "tz": "Asia/Seoul", "calendar": "year"},
}
for _k, _v in SOCCER_LEAGUES.items():
    LEAGUES.setdefault(f"{_k}_FS", _v)


def soccer_season_key(date: str, calendar: str) -> tuple:
    d = datetime.strptime(date, "%Y%m%d")
    if calendar == "year":
        return (d.year, d.year)
    y = d.year if d.month >= 7 else d.year - 1     # 추계춘제: 7월 이후는 그해 시작 시즌
    return (y, y + 1)


def _slug(name: str) -> str:
    s = re.sub(r"\(.*?\)", "", name).strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s


def _num(v: str):
    if v is None:
        return None
    m = re.match(r"\s*(-?\d+(?:\.\d+)?)", str(v))
    if not m:
        return None
    x = float(m.group(1))
    return int(x) if x.is_integer() and "." not in m.group(1) else x


def _stage_type(za: str) -> str:
    s = (za or "").lower()
    if "friendly" in s or "pre-season" in s:
        return "PRE"
    if "relegation" in s and ("play" in s or "promotion" in s):
        return "RELEG_PO"
    if "play off" in s or "play-off" in s or "playoff" in s:
        return "PO"
    if "championship" in s or "final a" in s or "group a" in s:
        return "FINAL_A"
    if "relegation group" in s or "final b" in s or "group b" in s:
        return "FINAL_B"
    return "REG"


class FlashscoreSoccer(FlashscoreHockeyCollector):

    def __init__(self, league: str, sleep: float = 0.4):
        if league not in SOCCER_LEAGUES:
            raise ValueError(f"지원하지 않는 축구 리그: {league}")
        super().__init__(f"{league}_FS", sleep=sleep)
        self.soccer_league = league

    # ------------------------------------------------------------------
    def season_matches(self, y1: int, y2: int) -> dict:
        key = (y1, y2)
        if key in self._season_cache:
            return self._season_cache[key]
        cands = [f"-{y1}-{y2}", f"-{y1}"] if y1 != y2 else [f"-{y1}", f"-{y1}-{y1 + 1}"]
        cands.append("")
        html, sid, used = None, None, None
        for suf in cands:
            try:
                page = self._get(f"{SITE}/{self.cfg['path']}{suf}/results/", retries=1)
            except Exception:
                continue
            m = re.search(r"seasonId:\s*(\d+)", page)
            if m:
                html, sid, used = page, m.group(1), suf
                break
        if not html:
            raise RuntimeError(f"{self.soccer_league} {y1}-{y2} 시즌 페이지를 찾지 못함")
        if used == "":
            print(f"  [{self.soccer_league}] ⚠️ 시즌 URL 없이 최신 페이지 사용 ({y1}-{y2})")
        tour = re.search(r'tournament_id"\s*:\s*"(\w+)"', html)
        tour = tour.group(1) if tour else self.cfg.get("tournament")
        if not tour:
            raise RuntimeError(f"{self.soccer_league} tournament_id를 찾지 못함")
        cty = re.search(r'country_?[iI]d"?\s*[:=]\s*"?(\d+)', html)
        country = cty.group(1) if cty else self.cfg["country"]
        total = re.search(r"allEventsCount:\s*(\d+)", html)

        recs = {}
        for m in re.finditer(r"""initialFeeds\[["'](?:summary-)?results["']\]\s*=\s*\{\s*data:\s*`(.*?)`""", html, re.S):
            for r in _records(m.group(1)):
                recs.setdefault(r["AA"], r)
        for page in range(1, 40):
            text = self._get(f"{FEED}tr_1_{country}_{tour}_{sid}_{page}_0_en_2", feed=True)
            batch = _records(text)
            if not batch:
                break
            new = 0
            for r in batch:
                if r["AA"] not in recs:
                    new += 1
                recs.setdefault(r["AA"], r)
            if not new:
                break
            time.sleep(self.sleep)
        if total and len(recs) < int(total.group(1)):
            print(f"  [{self.soccer_league}] ⚠️ {y1}-{y2} 목록 {len(recs)}/{total.group(1)}경기만 확인됨")
        print(f"  [{self.soccer_league}] 시즌 목록 {len(recs)}경기 (URL 접미사 '{used}')")
        self._season_cache[key] = recs
        return recs

    # ------------------------------------------------------------------
    def collect_daily(self, date: str) -> dict:
        y1, y2 = soccer_season_key(date, self.cfg["calendar"])
        games = []
        recs = self.season_matches(y1, y2)
        for rec in sorted(recs.values(), key=lambda r: _int(r.get("AD"), 0)):
            if rec.get("AB") != "3":
                continue
            st = _int(rec.get("AD"))
            if not st:
                continue
            local = datetime.fromtimestamp(st, timezone.utc).astimezone(self.tz)
            if local.strftime("%Y%m%d") != date:
                continue
            try:
                games.append(self._build_soccer_game(rec, local))
            except Exception as e:
                print(f"  [{self.soccer_league}] 경기 {rec.get('AA')} 파싱 실패: {e}")
            time.sleep(self.sleep)
        return {"date": date, "league": self.soccer_league, "source": "flashscore", "games": games}

    def _build_soccer_game(self, r: dict, local: datetime) -> dict:
        mid = r["AA"]
        hs, as_ = _int(r.get("AG"), 0), _int(r.get("AH"), 0)
        h1 = (_int(r.get("BA")), _int(r.get("BB")))
        stats = self._soccer_stats(mid)
        time.sleep(self.sleep)
        goals = self._soccer_goals(mid)
        return {
            "game_id": "fs_" + mid,
            "game_type": _stage_type(r.get("ZA")),
            "stage": r.get("ZA", ""),
            "round": r.get("ER", ""),
            "start_local": local.strftime("%Y-%m-%dT%H:%M:%S"),
            "start_utc": datetime.fromtimestamp(_int(r["AD"]), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "home_team": r.get("AE", ""),
            "away_team": r.get("AF", ""),
            "home_team_id": r.get("PX"),
            "away_team_id": r.get("PY"),
            "home_score": hs,
            "away_score": as_,
            "total_goals": hs + as_,
            "ht_home": h1[0],
            "ht_away": h1[1],
            "result": "H" if hs > as_ else ("A" if hs < as_ else "D"),
            "home_stats": stats.get("home", {}),
            "away_stats": stats.get("away", {}),
            "goals": goals,
        }

    def _soccer_stats(self, mid: str) -> dict:
        try:
            text = self._get(f"{FEED}df_st_1_{mid}", feed=True)
        except Exception as e:
            print(f"  [{self.soccer_league}] 스탯 실패 {mid}: {e}")
            return {}
        home, away, section = {}, {}, None
        for blk in text.split("~"):
            d = dict(kv.split("÷", 1) for kv in blk.split("¬") if "÷" in kv)
            if "SE" in d:
                section = d["SE"]
                continue
            if section != "Match" or "SG" not in d:
                continue
            k = _slug(d["SG"])
            if "xg" in d["SG"].lower() and "xgot" not in d["SG"].lower() and "on target" not in d["SG"].lower():
                k = "xg"
            hv, av = _num(d.get("SH")), _num(d.get("SI"))
            if hv is not None:
                home[k] = hv
            if av is not None:
                away[k] = av
        return {"home": home, "away": away} if home else {}

    def _soccer_goals(self, mid: str) -> list:
        try:
            text = self._get(f"{FEED}df_sui_1_{mid}", feed=True)
        except Exception:
            return []
        out = []
        for blk in text.split("~"):
            if not blk.startswith("III÷"):
                continue
            if "IK÷Goal" not in blk and "IK÷Own goal" not in blk and "IK÷Penalty" not in blk:
                continue
            side = re.search(r"IA÷(\d)", blk)
            tm = re.search(r"IB÷([^¬]*)", blk)
            who = re.search(r"IF÷([^¬]*)", blk)
            kind = re.search(r"IK÷([^¬]*)", blk)
            out.append({
                "minute": tm.group(1) if tm else "",
                "team": "home" if side and side.group(1) == "1" else "away",
                "player": who.group(1) if who else "",
                "type": kind.group(1) if kind else "",
            })
        return out
