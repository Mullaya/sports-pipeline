"""B리그 선수 박스스코어 — B.LEAGUE 공식 사이트가 쓰는 공개 JSON (키 불필요)

  일정(경기 키): https://www.bleague.jp/schedule/?data_format=json&tab=1&year=<시즌 시작 연도>&mon=M&day=D&event=2...
                → 응답 HTML 조각 안의 ScheduleKey 목록
  박스스코어   : http://b-league.s3.amazonaws.com/web_json/v2_genius_contexts/<ScheduleKey>/latestid → <id>.json
                HomeBoxscores/AwayBoxscores 중 PeriodCategory=18(경기 전체) 행 = 선수별 합계

Flashscore 경기와는 날짜(KST) + 최종 스코어(홈·원정)로 매칭한다 → 팀명 매핑 불필요.
선수 행은 KBL 수집기와 같은 스키마(player_id/name/starter/dnp/min/pts/reb/...)로 변환한다.
"""
import re
import time
from datetime import datetime, timedelta, timezone

import requests

KST = timezone(timedelta(hours=9))
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
S3 = "http://b-league.s3.amazonaws.com/web_json/v2_genius_contexts"
TOTAL = 18          # PeriodCategory: 1~4 쿼터, 15/16 전·후반, 18 경기 전체


def _min(play_time) -> float:
    if not play_time or ":" not in str(play_time):
        return 0.0
    m, s = str(play_time).split(":")[:2]
    return round(int(m) + int(s) / 60, 1)


def player_row(p: dict) -> dict:
    mins = _min(p.get("PlayTime"))
    return {
        "player_id": str(p.get("PlayerID")), "name": p.get("PlayerNameJ") or p.get("PlayerNameE"),
        "name_en": p.get("PlayerNameE"), "no": p.get("PlayerNo"), "pos": None,
        "starter": p.get("StartingFlg") == 1, "dnp": mins == 0,
        "min": mins, "pts": p.get("Point", 0), "reb": p.get("RB_TOT", 0),
        "oreb": p.get("RB_OFF", 0), "dreb": p.get("RB_DEF", 0), "ast": p.get("AS", 0),
        "stl": p.get("ST", 0), "blk": p.get("BS", 0), "tov": p.get("TO", 0), "fouls": p.get("FOUL", 0),
        "fg2m": p.get("PT2M", 0), "fg2a": p.get("PT2A", 0), "fg3m": p.get("PT3M", 0), "fg3a": p.get("PT3A", 0),
        "ftm": p.get("FTM", 0), "fta": p.get("FTA", 0), "plus_minus": p.get("PLUSMINUS"),
    }


class BLeagueBox:
    def __init__(self, sleep: float = 0.3, events=("2",)):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA})
        self.sleep = sleep
        self.events = events
        self._day_cache = {}

    def _get(self, url, **kw):
        last = None
        for i in range(3):
            try:
                r = self.s.get(url, timeout=30, **kw)
                if r.status_code == 200:
                    return r
                last = f"HTTP {r.status_code}"
            except Exception as e:
                last = str(e)
            time.sleep(2 * (i + 1))
        raise RuntimeError(f"B리그 공식 요청 실패 {url}: {last}")

    def keys_for_date(self, date: str) -> list:
        y, m, d = int(date[:4]), int(date[4:6]), int(date[6:])
        season = y if m >= 8 else y - 1
        keys = []
        for ev in self.events:
            url = (f"https://www.bleague.jp/schedule/?data_format=json&tab=1&year={season}&mon={m}&day={d}"
                   f"&event={ev}&club=&ha=&fb=&index=1")
            try:
                txt = self._get(url).text
            except Exception as e:
                print(f"  [BLEAGUE] 공식 일정 실패 {date}: {e}")
                continue
            keys += re.findall(r"ScheduleKey=(\d+)", txt.replace("\\/", "/"))
        return sorted(set(keys))

    def boxscore(self, key: str) -> dict:
        lid = re.sub(r"\D", "", self._get(f"{S3}/{key}/latestid").text) or "0"
        return self._get(f"{S3}/{key}/{lid}.json").json()

    def games_on(self, date: str) -> list:
        """해당 KST 날짜에 끝난 경기의 (홈점수, 원정점수, 홈선수, 원정선수, 키)"""
        if date in self._day_cache:
            return self._day_cache[date]
        out = []
        for key in self.keys_for_date(date):
            try:
                d = self.boxscore(key)
            except Exception as e:
                print(f"  [BLEAGUE] 박스스코어 실패 {key}: {e}")
                continue
            time.sleep(self.sleep)
            g = d.get("Game") or {}
            ms = re.search(r"/Date\((\d+)", g.get("GameDateTime") or "")
            if not ms or not g.get("GameEndedFlg"):
                continue
            day = datetime.fromtimestamp(int(ms.group(1)) / 1000, KST).strftime("%Y%m%d")
            if day != date:
                continue
            # 경기 전체(18) 행 중 선수 행만 (팀 합계 행은 선수 이름이 비어 있음)
            rows = lambda k: [player_row(p) for p in d.get(k) or [] if p.get("PeriodCategory") == TOTAL
                              and (p.get("PlayerNameJ") or p.get("PlayerNameE"))]
            out.append({"key": key, "home_score": g.get("HomeTeamScore"), "away_score": g.get("AwayTeamScore"),
                        "home_players": rows("HomeBoxscores"), "away_players": rows("AwayBoxscores")})
        self._day_cache[date] = out
        return out

    def fill(self, date: str, games: list) -> int:
        """Flashscore 경기 목록에 선수 기록을 채운다. 채운 경기 수 반환"""
        offs = self.games_on(date)
        n = 0
        for g in games:
            if g.get("home_players"):
                continue
            cand = [o for o in offs if (o["home_score"], o["away_score"]) == (g["home_score"], g["away_score"])]
            if len(cand) != 1:
                continue
            o = cand[0]
            g["home_players"], g["away_players"] = o["home_players"], o["away_players"]
            g["official_key"] = o["key"]
            n += 1
        return n
