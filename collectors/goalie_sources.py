"""골리 데이터 보조 소스 — 리그 공식 사이트 (Flashscore 라인업 피드 중단 대응, 2026-11)

- Liiga: liiga.fi 공개 일정·경기 상세 → 경기별 선발 골리(라인업 1라인 골리)
- DEL:  penny-del.org 공개 골리 기록표 → 시즌 골리 성적(GP·실점·세이브·SV%)
"""
import re
import time
import unicodedata
from datetime import datetime, timezone

import requests

UA = {"User-Agent": "Mozilla/5.0 (compatible; sports-pipeline/1.0)"}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _ascii(s: str) -> str:
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()


def _short(first: str, last: str) -> str:
    """Flashscore 표기와 맞춤: 'Salonen D.' (악센트 제거)"""
    first, last = _ascii(first).strip(), _ascii(last).strip()
    return f"{last} {first[:1]}.".strip() if first else last


# ----------------------------------------------------------------------
# Liiga
# ----------------------------------------------------------------------
# Flashscore 팀명(정규화) → liiga.fi 팀명(정규화)
LIIGA_ALIAS = {
    "hameenlinna": "hpk", "ifkhelsinki": "hifk", "kiekkoespoo": "kespoo",
    "tpsturku": "tps", "vaasansport": "sport",
}


class LiigaStarters:
    API = "https://liiga.fi/api/v2"

    def __init__(self, sleep: float = 0.3):
        self.sleep = sleep
        self._sched = {}

    @staticmethod
    def _season(dt: datetime) -> int:
        return dt.year + 1 if dt.month >= 7 else dt.year

    def _get(self, url: str):
        r = requests.get(url, headers=UA, timeout=25)
        r.raise_for_status()
        return r.json()

    def schedule(self, season: int) -> list:
        if season not in self._sched:
            games = []
            for tour in ("runkosarja", "playoffs"):
                try:
                    games += self._get(f"{self.API}/schedule?tournament={tour}&season={season}") or []
                except Exception:
                    pass
            self._sched[season] = games
        return self._sched[season]

    @staticmethod
    def _key(name: str) -> str:
        n = _norm(name)
        return LIIGA_ALIAS.get(n, n)

    def find_game(self, start_utc: str, home: str, away: str):
        dt = datetime.strptime(start_utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        hk, ak = self._key(home), self._key(away)
        for g in self.schedule(self._season(dt)):
            if _norm(g.get("homeTeamName")) != hk or _norm(g.get("awayTeamName")) != ak:
                continue
            try:
                gs = datetime.strptime(g["start"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
            except Exception:
                continue
            if abs((gs - dt).total_seconds()) <= 12 * 3600:
                return g
        return None

    def starters(self, start_utc: str, home: str, away: str) -> dict:
        g = self.find_game(start_utc, home, away)
        if not g:
            return {}
        time.sleep(self.sleep)
        d = self._get(f"{self.API}/games/{g['season']}/{g['id']}")
        out = {}
        for side, key in (("home", "homeTeamPlayers"), ("away", "awayTeamPlayers")):
            gks = [p for p in d.get(key) or [] if p.get("role") == "GOALIE"]
            st = [p for p in gks if p.get("line") == 1] or []
            if st:
                p = st[0]
                out[side] = {"name": _short(p.get("firstName", ""), p.get("lastName", "")),
                             "player_id": f"liiga:{p.get('id')}", "source": "liiga.fi"}
        return out


# ----------------------------------------------------------------------
# DEL
# ----------------------------------------------------------------------
def del_season_slug(date: str) -> str:
    y, m = int(date[:4]), int(date[4:6])
    y1 = y if m >= 7 else y - 1
    return f"saison-{y1}-{str(y1 + 1)[2:]}"


def _cells(tr: str) -> list:
    out = []
    for td in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S):
        alt = re.search(r'(?:alt|title|data-team|aria-label)="([^"]+)"', td)
        link = re.search(r'(?:href|src)="([^"]+)"', td)
        txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", td)).strip()
        if not txt and alt:
            txt = alt.group(1).strip()
        if not txt and link:
            seg = [x for x in re.split(r"[/?#]", link.group(1)) if x]
            txt = re.sub(r"\.(svg|png|jpe?g|webp)$", "", seg[-1]) if seg else ""
        out.append(txt)
    return out


def _num(s: str):
    s = (s or "").replace("%", "").replace(",", ".").strip()
    try:
        return float(s) if "." in s else int(s)
    except ValueError:
        return None


def del_goalie_table(date: str) -> dict:
    url = f"https://www.penny-del.org/statistik/{del_season_slug(date)}/hauptrunde/goaliestats/basis"
    r = requests.get(url, headers=UA, timeout=25)
    r.raise_for_status()
    m = re.search(r"<table.*?</table>", r.text, re.S)
    if not m:
        raise RuntimeError("DEL 골리 표를 찾지 못함")
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(0), re.S)
    head = _cells(rows[0]) if rows else []
    goalies = []
    for tr in rows[1:]:
        c = _cells(tr)
        if len(c) < 15:
            continue
        # 0 # | 1 Team | 2 # | 3 Spieler | 4 Nat | 5 POS | 6 GP | 7 Min. | 8 S | 9 N | 10 SO | 11 GT | 12 GTS | 13 SV | 14 SV%
        name = c[3]
        if "," in name:
            last, first = [x.strip() for x in name.split(",", 1)]
            name = _short(first, last)
        sv_pct = _num(c[14])
        if isinstance(sv_pct, (int, float)) and sv_pct > 1:
            sv_pct = round(sv_pct / 100, 4)
        goalies.append({
            "name": name, "raw_name": c[3], "team": c[1], "jersey": c[2], "nat": c[4],
            "gp": _num(c[6]), "toi": c[7], "w": _num(c[8]), "l": _num(c[9]), "so": _num(c[10]),
            "ga": _num(c[11]), "gaa": _num(c[12]), "saves": _num(c[13]), "sv_pct": sv_pct,
        })
    return {"date": date, "league": "DEL", "source": "penny-del.org", "header": head, "goalies": goalies}
