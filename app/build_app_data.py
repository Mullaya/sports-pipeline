"""분석 앱 데이터 생성 → data/app/latest.json  (GitHub Actions 매시간)

오늘·내일(KST) 경기 목록 + 경기별 분석 재료(매치업 팩) + 라인업 상태.
일정·라인업·최근 경기/맞대결은 Flashscore 공통 피드, 팀 통계는 analytics/*_stats.json에서 붙인다.

경기 1건 구조:
  id, league, group(하키/농구/배구/야구/축구), comp, start(unix), status(예정/진행/종료), score
  home/away: {name(원문), key(통계 키 또는 null)}
  lineup: {available, checked_kst, groups: {그룹명: {home:[..], away:[..]}}}
  form:   {home:[최근 5], away:[최근 5], h2h:[맞대결 5]}   (Flashscore, 모든 리그)
  stats:  {home, away, goalies, h2h, leaders, pitchers}     (통계 파일이 있는 리그만)

라인업·최근경기 피드는 요청을 아끼려고 이전 latest.json 값을 재사용한다:
  최근경기/맞대결 → 하루 1회, 라인업 → 시작 4시간 전부터 경기 시작 후 30분까지만 갱신.
"""
import os
import re
import sys
import json
import time
from datetime import datetime, timedelta, timezone

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from collectors.flashscore_hockey_collector import LEAGUES as FS_HOCKEY  # KHL 팀명 매핑 재사용

OUT = os.path.join(ROOT, "data", "app", "latest.json")
FEED = "https://global.flashscore.ninja/2/x/feed/"
HDR = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
       "x-fsign": "SW9D1eZo", "Referer": "https://www.flashscore.com/", "Origin": "https://www.flashscore.com"}
KST = timezone(timedelta(hours=9))
SLEEP = 0.3

# (리그코드, 종목 그룹, Flashscore sport id, 대회명(스테이지 앞부분), 통계 파일)
LEAGUES = [
    ("NHL", "하키", 4, "USA: NHL", "NHL"),
    ("KHL", "하키", 4, "RUSSIA: KHL", "KHL"),
    ("DEL", "하키", 4, "GERMANY: DEL", "DEL"),
    ("CZE", "하키", 4, "CZECH REPUBLIC: Extraliga", "CZE"),
    ("LIIGA", "하키", 4, "FINLAND: Liiga", "LIIGA"),
    ("SHL", "하키", 4, "SWEDEN: SHL", "SHL"),
    ("NBA", "농구", 3, "USA: NBA", None),
    ("KBL", "농구", 3, "SOUTH KOREA: KBL", "KBL"),
    ("KOVO", "배구", 12, "SOUTH KOREA: V-League", "KOVO"),
    ("WKOVO", "배구", 12, "SOUTH KOREA: V-League Women", "WKOVO"),
    ("MLB", "야구", 6, "USA: MLB", "MLB"),
    ("KBO", "야구", 6, "SOUTH KOREA: KBO", None),
    ("NPB", "야구", 6, "JAPAN: NPB", None),
    ("EPL", "축구", 1, "ENGLAND: Premier League", None),
    ("LALIGA", "축구", 1, "SPAIN: LaLiga", None),
    ("BUNDES", "축구", 1, "GERMANY: Bundesliga", None),
    ("SERIEA", "축구", 1, "ITALY: Serie A", None),
    ("LIGUE1", "축구", 1, "FRANCE: Ligue 1", None),
    ("EREDIV", "축구", 1, "NETHERLANDS: Eredivisie", None),
    ("SCOT", "축구", 1, "SCOTLAND: Premiership", None),
    ("TUR", "축구", 1, "TURKEY: Super Lig", None),
    ("KLEAGUE", "축구", 1, "SOUTH KOREA: K League 1", None),
    ("UCL", "축구", 1, "EUROPE: Champions League", None),
    ("UEL", "축구", 1, "EUROPE: Europa League", None),
]
LEAGUE_NAMES = {
    "NHL": "NHL", "KHL": "KHL", "DEL": "독일 DEL", "CZE": "체코 엑스트라리가", "LIIGA": "핀란드 Liiga", "SHL": "스웨덴 SHL", "NBA": "NBA", "KBL": "KBL",
    "KOVO": "V리그 남자", "WKOVO": "V리그 여자", "MLB": "MLB", "KBO": "KBO", "NPB": "NPB",
    "EPL": "EPL", "LALIGA": "라리가", "BUNDES": "분데스리가", "SERIEA": "세리에A", "LIGUE1": "리그1",
    "EREDIV": "에레디비시", "SCOT": "스코틀랜드", "TUR": "튀르키예", "KLEAGUE": "K리그1",
    "UCL": "챔피언스리그", "UEL": "유로파리그",
}

# Flashscore 영문 표기 → 통계 파일 키 (KBL·V리그는 한글 키)
NAME_MAP = {
    "KHL": FS_HOCKEY["KHL"]["names"],
    "KBL": {"Anyang JungKwanJang": "안양 정관장", "Goyang Sono": "고양 소노", "KCC Egis": "부산 KCC",
            "KoGas": "대구 한국가스공사", "LG Sakers": "창원 LG", "Mobis Phoebus": "울산 현대모비스",
            "Seoul Knights": "서울 SK", "Seoul Thunders": "서울 삼성", "Suwon KT": "수원 KT", "Wonju DB": "원주 DB"},
}
KEYWORDS = {   # 표기가 시즌마다 조금씩 바뀌는 리그는 키워드로
    "KOVO": [("OK", "OK저축은행"), ("Skywalkers", "현대캐피탈"), ("Hyundai", "현대캐피탈"), ("KAL", "대한항공"),
             ("Korean Air", "대한항공"), ("KB", "KB손해보험"), ("Kepco", "한국전력"), ("KEPCO", "한국전력"),
             ("Samsung", "삼성화재"), ("Woori", "우리카드")],
    "WKOVO": [("Expressway", "한국도로공사"), ("GS Caltex", "GS칼텍스"), ("Hungkuk", "흥국생명"), ("Heungkuk", "흥국생명"),
              ("IBK", "IBK기업은행"), ("Pepper", "페퍼저축은행"), ("Red Sparks", "정관장"), ("JungKwanJang", "정관장"),
              ("KGC", "정관장"), ("Hyundai", "현대건설")],
}

TEAM_DROP = {"last10_log"}   # 팩에는 별도로 넣는 항목


def now_kst():
    return datetime.now(KST)


def recs(text):
    """Flashscore 피드 → (대회명, 레코드) 목록"""
    out, za = [], None
    for blk in (text or "").split("~"):
        d = {}
        for kv in blk.split("¬"):
            if "÷" in kv:
                k, v = kv.split("÷", 1)
                d[k] = v
        if "ZA" in d:
            za = d["ZA"]
        elif "AA" in d:
            out.append((za or "", d))
    return out


class FS:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update(HDR)
        self.calls = 0

    def get(self, feed):
        for i in range(3):
            try:
                self.calls += 1
                r = self.s.get(FEED + feed, timeout=25)
                if r.status_code == 200:
                    time.sleep(SLEEP)
                    return r.text
            except Exception:
                pass
            time.sleep(2 * (i + 1))
        return ""


def league_of(sport, za):
    base = za.split(" - ")[0].strip()
    for code, group, sid, comp, stats in LEAGUES:
        if sid == sport and base == comp:
            return code, group, stats
    return None


# ----------------------------------------------------------------------
def parse_lineup(text):
    """df_li → {그룹명: {home:[이름(역할)], away:[...]}}"""
    groups, g, side = {}, None, None
    for blk in (text or "").split("~"):
        d = dict(kv.split("÷", 1) for kv in blk.split("¬") if "÷" in kv)
        if "LB" in d:
            g = d["LB"]
        if "LC" in d:
            side = "home" if d["LC"] == "1" else "away"
        if "LI" in d and g and side and g != "Coaches":
            role = d.get("LR", "")
            pos = d.get("LS", "")
            label = d["LI"] + (f" {role}" if role else "") + (f" [{pos}]" if pos and pos not in ("Goalkeeper",) and len(pos) < 20 else "")
            groups.setdefault(g, {"home": [], "away": []})[side].append(label.strip())
    return groups


def parse_h2h(text, n=5):
    """df_hh(Overall) → 홈 최근, 원정 최근, 맞대결"""
    sections, cur, overall = [], None, False
    for blk in (text or "").split("~"):
        d = dict(kv.split("÷", 1) for kv in blk.split("¬") if "÷" in kv)
        if "KA" in d:
            overall = d["KA"] == "Overall"
            continue
        if not overall:
            continue
        if "KB" in d:
            cur = {"title": d["KB"], "rows": []}
            sections.append(cur)
        elif "KC" in d and cur is not None and len(cur["rows"]) < n:
            ts = datetime.fromtimestamp(int(d["KC"]), KST).strftime("%y.%m.%d")
            res = {"w": "승", "l": "패", "d": "무"}.get(d.get("WIS", ""), "")
            cur["rows"].append(f'{ts} {d.get("KJ","").lstrip("*")} {d.get("KL","")} {d.get("KK","").lstrip("*")}'
                               + (f" ({res})" if res else "") + (f' [{d.get("KF")}]' if d.get("KF") else ""))
    out = {"home": [], "away": [], "h2h": []}
    lasts = [s for s in sections if s["title"].startswith("Last matches")]
    if lasts:
        out["home"] = lasts[0]["rows"]
    if len(lasts) > 1:
        out["away"] = lasts[1]["rows"]
    for s in sections:
        if s["title"].lower().startswith("head-to-head"):
            out["h2h"] = s["rows"]
    return out


# ----------------------------------------------------------------------
class Stats:
    """analytics 파일 로더 + 팀/골리/맞대결 추출"""

    def __init__(self):
        self.cache = {}

    def load(self, name):
        if name in self.cache:
            return self.cache[name]
        d = None
        try:
            if name == "MLB":
                d = {"teams": {}, "pitchers": {}}
                for div in ("AL_East", "AL_Central", "AL_West", "NL_East", "NL_Central", "NL_West"):
                    x = json.load(open(os.path.join(ROOT, "analytics", f"MLB_{div}.json"), encoding="utf-8"))
                    d["teams"].update(x.get("teams", {}))
                    d["pitchers"].update(x.get("pitchers", {}))
            else:
                d = json.load(open(os.path.join(ROOT, "analytics", f"{name}_stats.json"), encoding="utf-8"))
        except Exception as e:
            print(f"  ⚠️ 통계 파일 {name} 로드 실패: {e}")
        self.cache[name] = d
        return d

    def team_key(self, league, stats_name, raw):
        d = self.load(stats_name)
        if not d:
            return None
        teams = set(d.get("teams", {})) | set(d.get("last_season", {}) or {})
        if raw in teams:
            return raw
        m = NAME_MAP.get(league, {}).get(raw)
        if m:
            return m
        for kw, key in KEYWORDS.get(league, []):
            if kw in raw:
                return key
        if league == "NHL":   # 통계 키=약어, name=닉네임 ("Wild") → 원문이 닉네임으로 끝나면 일치
            for ab, t in d.get("teams", {}).items():
                if t.get("name") and raw.endswith(t["name"]):
                    return ab
        low = raw.lower()
        for k in teams:
            if k.lower() in low or low in k.lower():
                return k
        return None

    @staticmethod
    def slim(t):
        if not t:
            return None
        return {k: v for k, v in t.items() if k not in TEAM_DROP}

    def pack(self, league, stats_name, hk, ak):
        d = self.load(stats_name)
        if not d:
            return None
        teams, last = d.get("teams", {}), d.get("last_season", {}) or {}
        out = {"meta": {k: d.get("meta", {}).get(k) for k in ("league_avg", "points_rule", "games", "last_game_date", "notes")
                        if d.get("meta", {}).get(k) is not None}}
        for side, key in (("home", hk), ("away", ak)):
            if not key:
                continue
            t = teams.get(key)
            out[side] = {
                "key": key,
                "season": self.slim(t),
                "last10_log": (t or {}).get("last10_log"),
                "last_season": self.slim(last.get(key)) if last else None,
            }
        # 골리 (하키)
        gk = d.get("goalies")
        if gk and (hk or ak):
            sel = {}
            for side, key in (("home", hk), ("away", ak)):
                rows = [v for v in gk.values() if v.get("team") == key]
                rows.sort(key=lambda v: -(v.get("starts") or v.get("gp") or 0))
                sel[side] = rows[:3]
            out["goalies"] = sel
        # 맞대결
        h2h = d.get("h2h") or {}
        if hk and ak:
            for k, v in h2h.items():
                parts = re.split(r"\s*\|\s*|\s+vs\s+|-", k)
                if hk in parts and ak in parts:
                    out["h2h"] = v
                    break
        # 리더
        ld = d.get("leaders") or {}
        if ld:
            out["leaders"] = {side: (ld.get(key) or [])[:5] for side, key in (("home", hk), ("away", ak)) if key}
        return out


def mlb_probables(date_us_list):
    """MLB 예고 선발 (statsapi) → {(원정, 홈): (원정선발, 홈선발)}"""
    out = {}
    for d in date_us_list:
        try:
            r = requests.get("https://statsapi.mlb.com/api/v1/schedule",
                             params={"sportId": 1, "date": d, "hydrate": "probablePitcher"}, timeout=20).json()
        except Exception:
            continue
        for dt in r.get("dates", []):
            for g in dt.get("games", []):
                a, h = g["teams"]["away"], g["teams"]["home"]
                out[(a["team"]["name"], h["team"]["name"])] = (
                    (a.get("probablePitcher") or {}).get("fullName"), (h.get("probablePitcher") or {}).get("fullName"))
    return out


# ----------------------------------------------------------------------
def main():
    t0 = time.time()
    now = now_kst()
    try:
        prev = {g["id"]: g for g in json.load(open(OUT, encoding="utf-8")).get("games", [])}
    except Exception:
        prev = {}

    fs, st = FS(), Stats()
    seen, games, unmapped = set(), [], {}
    sports = sorted({sid for _, _, sid, _, _ in LEAGUES})
    for sport in sports:
        for off in (0, 1):          # tz=9 → KST 오늘·내일
            for za, r in recs(fs.get(f"f_{sport}_{off}_9_en_1")):
                lg = league_of(sport, za)
                if not lg or r["AA"] in seen:
                    continue
                seen.add(r["AA"])
                code, group, stats_name = lg
                ab = r.get("AB", "1")
                g = {
                    "id": r["AA"], "league": code, "league_name": LEAGUE_NAMES[code], "group": group,
                    "comp": za, "round": r.get("ER", ""),
                    "start": int(r.get("AD", 0)),
                    "status": {"1": "예정", "2": "진행", "3": "종료"}.get(ab, "기타"),
                    "home": {"name": r.get("AE", "")}, "away": {"name": r.get("AF", "")},
                }
                if ab in ("2", "3") and r.get("AG") is not None:
                    g["score"] = {"home": r.get("AG"), "away": r.get("AH")}
                    # 피리어드/세트/쿼터별 점수 (BA/BB, BC/BD, ... 홈/원정 쌍)
                    parts = []
                    for hk, ak in (("BA", "BB"), ("BC", "BD"), ("BE", "BF"), ("BG", "BH"), ("BI", "BJ")):
                        if r.get(hk) is None and r.get(ak) is None:
                            break
                        parts.append([r.get(hk, ""), r.get(ak, "")])
                    if parts:
                        g["score"]["parts"] = parts
                if stats_name:
                    for side in ("home", "away"):
                        k = st.team_key(code, stats_name, g[side]["name"])
                        g[side]["key"] = k
                        if not k:
                            unmapped.setdefault(code, set()).add(g[side]["name"])
                games.append(g)

    games.sort(key=lambda g: (g["start"], g["league"]))
    probs = mlb_probables(sorted({datetime.fromtimestamp(g["start"], timezone(timedelta(hours=-5))).strftime("%Y-%m-%d")
                                  for g in games if g["league"] == "MLB"}))

    today = now.strftime("%Y%m%d")
    # 수동 갱신(픽 데스크 '갱신' 버튼): 지정 경기는 시간창과 무관하게 라인업을 다시 확인
    force_ids = {x.strip() for x in os.environ.get("FORCE_IDS", "").split(",") if x.strip()}
    for g in games:
        p = prev.get(g["id"], {})
        mins_to_start = (g["start"] - now.timestamp()) / 60
        # 최근 경기·맞대결: 하루 1회
        if p.get("form") and p.get("form_date") == today:
            g["form"], g["form_date"] = p["form"], p["form_date"]
        else:
            g["form"], g["form_date"] = parse_h2h(fs.get(f"df_hh_1_{g['id']}")), today
        # 라인업: 시작 4시간 전 ~ 시작 후 30분 갱신, 그 밖은 이전 값 유지
        forced = g["id"] in force_ids and g["status"] != "종료"
        if forced or -30 <= mins_to_start <= 240 or (not p.get("lineup") and g["status"] != "예정"):
            groups = parse_lineup(fs.get(f"df_li_1_{g['id']}"))
            avail = any(v["home"] or v["away"] for k, v in groups.items() if k != "Substitutes")
            g["lineup"] = {"available": avail, "checked_kst": now.strftime("%m/%d %H:%M"), "groups": groups}
            if avail and not (p.get("lineup") or {}).get("available"):
                g["lineup"]["confirmed_kst"] = now.strftime("%m/%d %H:%M")
            elif (p.get("lineup") or {}).get("confirmed_kst"):
                g["lineup"]["confirmed_kst"] = p["lineup"]["confirmed_kst"]
        else:
            g["lineup"] = p.get("lineup") or {"available": False, "checked_kst": None, "groups": {}}
        # 통계 팩
        stats_name = next((s for c, _, _, _, s in LEAGUES if c == g["league"]), None)
        if stats_name:
            pk = st.pack(g["league"], stats_name, g["home"].get("key"), g["away"].get("key"))
            if g["league"] == "MLB":
                pp = probs.get((g["away"]["name"], g["home"]["name"]))
                if pp:
                    pit = st.load("MLB").get("pitchers", {})
                    pk["probables"] = {"away": pp[0], "home": pp[1],
                                       "away_stats": pit.get(pp[0] or ""), "home_stats": pit.get(pp[1] or "")}
            g["stats"] = pk

    out = {
        "meta": {
            "generated_kst": now.strftime("%Y-%m-%d %H:%M"),
            "trigger": os.environ.get("RUN_REASON", "schedule"),
            "dates_kst": [now.strftime("%Y-%m-%d"), (now + timedelta(days=1)).strftime("%Y-%m-%d")],
            "games": len(games),
            "flashscore_calls": fs.calls,
            "unmapped_teams": {k: sorted(v) for k, v in unmapped.items()},
            "leagues": [{"code": c, "name": LEAGUE_NAMES[c], "group": grp} for c, grp, _, _, _ in LEAGUES],
        },
        "games": games,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
    by = {}
    for g in games:
        by[g["league"]] = by.get(g["league"], 0) + 1
    print(f"===== 앱 데이터 {len(games)}경기 {by} | 피드 {fs.calls}회 | {time.time()-t0:.0f}초 =====")
    if unmapped:
        print(f"  ⚠️ 통계 매핑 실패 팀: {out['meta']['unmapped_teams']}")


if __name__ == "__main__":
    main()
