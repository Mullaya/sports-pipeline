"""WKBL 선수 박스스코어 — WKBL 공식 사이트(wkbl.or.kr) 경기 결과 페이지가 쓰는 AJAX 조각

  월별 일정 : /game/sch/schedule1.asp?gun=1&season_gu=<시즌코드>&ym=YYYYMM → result.asp?...game_type=..&game_no=.. 링크
  경기 날짜 : /game/result.asp?season_gu=..&gun=1&game_type=..&game_no=.. 머리말 'YYYY년 MM월 DD일'
  선수 기록 : POST /game/ajax/ajax_game_result_2.asp (season_gu, game_type, game_no) → 팀별 표
              (선수·POS·MIN·2PM-A·3PM-A·FTM-A·OFF·DEF·TOT·AST·PF·ST·TO·BS·PTS, tfoot = 팀합계)
시즌코드: 2026-27 = 047 (매 시즌 +1). 선발 여부는 표에 없어 starter=None.
Flashscore 경기와는 날짜(KST) + 양 팀 최종 점수로 매칭한다.
"""
import re
import time

import requests

BASE = "https://www.wkbl.or.kr"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def season_gu(date: str) -> str:
    y = int(date[:4]) if int(date[4:6]) >= 8 else int(date[:4]) - 1
    return f"{47 + (y - 2026):03d}"


def _ma(v: str):
    try:
        a, b = v.split("-")
        return int(a), int(b)
    except ValueError:
        return 0, 0


def _i(v: str) -> int:
    try:
        return int(v)
    except ValueError:
        return 0


def _strip(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()


class WKBLBox:
    def __init__(self, sleep: float = 0.4):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Referer": BASE + "/game/result.asp"})
        self.sleep = sleep
        self._date = {}      # (gu, type, no) -> YYYYMMDD
        self._month = {}

    def _get(self, url, method="get", **kw):
        last = None
        for i in range(3):
            try:
                r = getattr(self.s, method)(url, timeout=30, **kw)
                if r.status_code == 200:
                    r.encoding = "utf-8"
                    return r.text
                last = f"HTTP {r.status_code}"
            except Exception as e:
                last = str(e)
            time.sleep(2 * (i + 1))
        raise RuntimeError(f"WKBL 공식 요청 실패 {url}: {last}")

    def month_games(self, gu: str, ym: str) -> list:
        key = (gu, ym)
        if key not in self._month:
            t = self._get(f"{BASE}/game/sch/schedule1.asp?gun=1&season_gu={gu}&ym={ym}")
            self._month[key] = sorted(set(re.findall(r"game_type=(\d+)&(?:amp;)?game_no=(\d+)", t)),
                                      key=lambda x: (x[0], int(x[1])))
        return self._month[key]

    def game_date(self, gu: str, gtype: str, no: str):
        k = (gu, gtype, no)
        if k not in self._date:
            t = self._get(f"{BASE}/game/result.asp?season_gu={gu}&gun=1&game_type={gtype}&game_no={no}")
            m = re.search(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", t)
            self._date[k] = f"{m.group(1)}{int(m.group(2)):02d}{int(m.group(3)):02d}" if m else None
            time.sleep(self.sleep)
        return self._date[k]

    def boxscore(self, gu: str, gtype: str, no: str) -> list:
        """[(팀명, 합계득점, [선수...]), ...] — 페이지 순서(홈 먼저)"""
        t = self._get(f"{BASE}/game/ajax/ajax_game_result_2.asp", method="post",
                      data={"season_gu": gu, "game_type": gtype, "game_no": no, "ym": "",
                            "h_player": "", "a_player": ""})
        out = []
        for m in re.finditer(r'<h4[^>]*data-kr="([^"]+)"[^>]*>.*?</h4>\s*<div class="info_table01 type_record">(.*?)</table>',
                             t, re.S):
            team, table = m.group(1), m.group(2)
            body = table.split("<tbody>", 1)[-1].split("</tbody>", 1)[0]
            players = []
            for tr in re.findall(r"<tr>(.*?)</tr>", body, re.S):
                tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
                if len(tds) < 15:
                    continue
                pno = re.search(r"pno=(\d+)", tds[0])
                c = [_strip(x) for x in tds]
                mm = c[2].split(":") if ":" in c[2] else ["0", "0"]
                mins = round(_i(mm[0]) + _i(mm[1]) / 60, 1)
                f2m, f2a = _ma(c[3]); f3m, f3a = _ma(c[4]); ftm, fta = _ma(c[5])
                players.append({
                    "player_id": pno.group(1) if pno else c[0], "name": c[0], "pos": c[1],
                    "starter": None, "dnp": mins == 0, "min": mins,
                    "pts": _i(c[14]), "reb": _i(c[8]), "oreb": _i(c[6]), "dreb": _i(c[7]),
                    "ast": _i(c[9]), "stl": _i(c[11]), "blk": _i(c[13]), "tov": _i(c[12]), "fouls": _i(c[10]),
                    "fg2m": f2m, "fg2a": f2a, "fg3m": f3m, "fg3a": f3a, "ftm": ftm, "fta": fta,
                })
            foot = re.search(r"<tfoot>(.*?)</tfoot>", table, re.S)
            tot = _i(_strip(re.findall(r"<td[^>]*>(.*?)</td>", foot.group(1), re.S)[-1])) if foot else \
                sum(p["pts"] for p in players)
            out.append((team, tot, players))
        return out

    def fill(self, date: str, games: list) -> int:
        todo = [g for g in games if not g.get("home_players")]
        if not todo:
            return 0
        gu = season_gu(date)
        n = 0
        for gtype, no in self.month_games(gu, date[:6]):
            if not todo:
                break
            if self.game_date(gu, gtype, no) != date:
                continue
            try:
                box = self.boxscore(gu, gtype, no)
            except Exception as e:
                print(f"  [WKBL] 박스스코어 실패 {gtype}-{no}: {e}")
                continue
            time.sleep(self.sleep)
            if len(box) != 2:
                continue
            (t1, s1, p1), (t2, s2, p2) = box
            for g in list(todo):
                if (g["home_score"], g["away_score"]) == (s1, s2):
                    g["home_players"], g["away_players"] = p1, p2
                elif (g["home_score"], g["away_score"]) == (s2, s1):
                    g["home_players"], g["away_players"] = p2, p1
                else:
                    continue
                g["official_key"] = f"{gu}-{gtype}-{no}"
                todo.remove(g)
                n += 1
                break
        return n
