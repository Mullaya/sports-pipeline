"""농구 누적 집계 (KBL·WKBL·B리그·NBA) → analytics/{LEAGUE}_stats.json

실행: python analytics/build_kbl_stats.py [KBL|WKBL|BLEAGUE|NBA]   (인자 없으면 KBL)
입력: data/{LEAGUE}/daily/*.json + data/{LEAGUE}/historical/*.json (game_id 중복 제거)
출력 구조:
  meta         : 생성 시각, 시즌 시작일, 집계 경기 수, 리그 평균
  teams        : 이번 시즌 팀별 성적 — 홈/원정, 최근 10경기, 페이스·공수 효율(ORtg/DRtg/Net),
                 Four Factors, 정규시간 총점·언오버 비율, 연장 비율, 휴식일/연전
  last_season  : 지난 시즌 정규리그 팀 성적 (시즌 초 표본 부족 시 기준점)
  leaders      : 팀별 출전시간 상위 7명 (결장자 영향도 판단)
  h2h          : 팀 쌍별 최근 맞대결 5경기 (지난 시즌 포함)

B리그는 팀별 직전 이동거리(last_travel_km)·최근 7일 이동거리(travel_7d_km)도 넣는다
(경기 장소 = 홈팀 연고지 좌표 기준 직선거리, 중립 경기장은 무시).

NBA는 ESPN 박스스코어(문자열 스탯)를 같은 스키마로 변환해 쓰고, 마감 배당(closing_line)이 있으면
팀별 ATS(핸디 커버)·마감 라인 대비 언오버 성적(market)도 넣는다. 48분 경기라 페이스는 48분당 포제션.

컵대회(CUP)·올스타(ALLSTAR)·NBA 플레이인(PLAYIN)은 집계에서 제외. 정규(REG)+플레이오프(PO/FINAL)만 사용.
최근 N경기 지표는 매 실행 때 일별 파일에서 재계산한다.
"""
import os
import sys
import json
import glob
import base64
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import math

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEAGUE = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("LEAGUE", "KBL")).upper()

# 리그별: 시즌 시작일, 언오버 기준선, 이번 시즌 데이터가 0건이면 실패로 볼 날짜
CONFIG = {
    "KBL": {"start": "20260901", "lines": (145.5, 150.5, 155.5, 160.5, 165.5), "alarm": "20261015"},
    "WKBL": {"start": "20261015", "lines": (120.5, 125.5, 130.5, 135.5, 140.5), "alarm": "20261115"},
    "BLEAGUE": {"start": "20260915", "lines": (150.5, 155.5, 160.5, 165.5, 170.5, 175.5, 180.5, 185.5),
                "alarm": "20261001"},
    "NBA": {"start": "20261020", "lines": (215.5, 220.5, 225.5, 230.5, 235.5, 240.5, 245.5),
            "alarm": "20261101", "reg_min": 48},
}
if LEAGUE not in CONFIG:
    sys.exit(f"지원하지 않는 리그: {LEAGUE}")
SEASON_START = os.getenv(f"{LEAGUE}_SEASON_START", CONFIG[LEAGUE]["start"])
OUT_PATH = f"analytics/{LEAGUE}_stats.json"
TOTAL_LINES = CONFIG[LEAGUE]["lines"]
COUNTED = ("REG", "PO", "FINAL")
REG_MIN = CONFIG[LEAGUE].get("reg_min", 40)   # 정규 경기 시간(분) — 연장 1회 = 5분

# B리그 홈 연고지 좌표 (통계 키 = 한글 팀명) — 이동거리 계산용
HOME_COORDS = {
    "BLEAGUE": {
        "알바르크 도쿄": (35.63, 139.79), "선로커즈 도쿄": (35.62, 139.78), "센다이": (38.26, 140.87),
        "군마": (36.29, 139.38), "우츠노미야": (36.56, 139.88), "지바 제츠": (35.68, 139.99),
        "알티리 지바": (35.61, 140.11), "홋카이도": (43.06, 141.35), "이바라키": (36.37, 140.47),
        "아키타": (39.72, 140.10), "가와사키": (35.53, 139.70), "요코하마BC": (35.47, 139.62),
        "교토": (35.01, 135.77), "히로시마": (34.39, 132.46), "사가": (33.25, 130.30),
        "산엔": (34.77, 137.39), "미카와": (34.99, 137.00), "시가": (35.00, 135.87),
        "신슈": (36.65, 138.18), "고베": (34.66, 135.21), "나가사키": (32.75, 129.87),
        "시마네": (35.47, 133.05), "도야마": (36.70, 137.21), "나고야D": (35.17, 136.91),
        "류큐": (26.33, 127.80), "오사카": (34.65, 135.43), "FE 나고야": (35.17, 136.91),
        "고시가야": (35.89, 139.79), "후쿠오카": (33.59, 130.40), "니가타": (37.92, 139.04),
    },
}.get(LEAGUE, {})


def km(a, b):
    """두 좌표 사이 직선거리(km)"""
    if not a or not b:
        return None
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return round(6371 * 2 * math.asin(math.sqrt(h)))


def kst_now():
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=9)


def _i(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def _ma(v):
    """'47-85' → (47, 85)"""
    try:
        a, b = str(v).split("-")
        return int(a), int(b)
    except (ValueError, AttributeError):
        return 0, 0


def nba_stats(st: dict) -> dict:
    if not st:
        return {}
    fgm, fga = _ma(st.get("fieldGoalsMade-fieldGoalsAttempted"))
    fg3m, fg3a = _ma(st.get("threePointFieldGoalsMade-threePointFieldGoalsAttempted"))
    ftm, fta = _ma(st.get("freeThrowsMade-freeThrowsAttempted"))
    return {"fgm": fgm, "fga": fga, "fg3m": fg3m, "fg3a": fg3a, "ftm": ftm, "fta": fta,
            "oreb": _i(st.get("offensiveRebounds")), "dreb": _i(st.get("defensiveRebounds")),
            "tov": _i(st.get("totalTurnovers", st.get("turnovers"))), "ast": _i(st.get("assists"))}


def nba_player(p: dict) -> dict:
    fg3m, _ = _ma(p.get("threePointFieldGoalsMade-threePointFieldGoalsAttempted"))
    return {"player_id": p.get("id"), "name": p.get("name"), "pos": p.get("pos"),
            "starter": bool(p.get("starter")), "dnp": bool(p.get("dnp")) or not _i(p.get("minutes")),
            "min": _i(p.get("minutes")), "pts": _i(p.get("points")), "reb": _i(p.get("rebounds")),
            "ast": _i(p.get("assists")), "fg3m": fg3m}


def normalize_nba(g: dict) -> dict:
    """ESPN NBA 박스스코어 → KBL 집계 스키마"""
    g = dict(g)
    g["home_short"], g["away_short"] = g.get("home_abbrev"), g.get("away_abbrev")
    g["start_kst"] = g.get("start_utc", "")
    g["reg_total_points"] = (g.get("reg_home_score") or 0) + (g.get("reg_away_score") or 0)
    g["home_stats"], g["away_stats"] = nba_stats(g.get("home_stats")), nba_stats(g.get("away_stats"))
    g["home_players"] = [nba_player(p) for p in g.get("home_players") or []]
    g["away_players"] = [nba_player(p) for p in g.get("away_players") or []]
    return g


def load_games() -> list:
    files = glob.glob(os.path.join(ROOT, "data", LEAGUE, "historical", "*.json")) + \
        glob.glob(os.path.join(ROOT, "data", LEAGUE, "daily", "*.json"))
    uniq = {}
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception as e:
            print(f"  ⚠️ {f} 읽기 실패: {e}")
            continue
        for g in d.get("games", []):
            g["date"] = d.get("date") or os.path.basename(f)[:8]
            uniq[g["game_id"]] = normalize_nba(g) if LEAGUE == "NBA" else g
    games = [g for g in uniq.values() if g.get("game_type") in COUNTED]
    if LEAGUE == "NBA":
        # 올스타전이 REG로 들어와서 정규 팀(20경기 이상 등장)끼리의 경기만 남김
        cnt = defaultdict(int)
        for g in games:
            cnt[g["home_team"]] += 1
            cnt[g["away_team"]] += 1
        games = [g for g in games if cnt[g["home_team"]] >= 20 and cnt[g["away_team"]] >= 20]
    return sorted(games, key=lambda x: (x["date"], x.get("start_kst", "")))


def pct(a, b, nd=3):
    return round(a / b, nd) if b else None


def poss(st: dict) -> float:
    """추정 포제션 = FGA − OREB + TOV + 0.44·FTA"""
    return st.get("fga", 0) - st.get("oreb", 0) + st.get("tov", 0) + 0.44 * st.get("fta", 0)


def days_between(a: str, b: str) -> int:
    return (datetime.strptime(b, "%Y%m%d") - datetime.strptime(a, "%Y%m%d")).days


# ----------------------------------------------------------------------
def team_rows(games):
    rows = defaultdict(list)
    for g in games:
        for side in ("home", "away"):
            opp = "away" if side == "home" else "home"
            st, ost = g.get(f"{side}_stats") or {}, g.get(f"{opp}_stats") or {}
            rows[g[f"{side}_team"]].append({
                "date": g["date"],
                "type": g.get("game_type"),
                "is_home": side == "home",
                "opp": g[f"{opp}_team"],
                "opp_short": g.get(f"{opp}_short") or g[f"{opp}_team"],
                "pf": g[f"{side}_score"], "pa": g[f"{opp}_score"],
                "reg_pf": g.get(f"reg_{side}_score", g[f"{side}_score"]),
                "reg_pa": g.get(f"reg_{opp}_score", g[f"{opp}_score"]),
                "ot": bool(g.get("overtime")),
                "ot_n": g.get("ot_periods") or (1 if g.get("overtime") else 0),
                "line": market_line(g, side),
                "total": g.get("total_points", 0),
                "reg_total": g.get("reg_total_points", g.get("total_points", 0)),
                "st": st, "ost": ost,
                # 경기 장소 = 홈팀 연고지 (중립 경기장은 위치 불명)
                "loc": None if g.get("neutral") else HOME_COORDS.get(g["home_team"]),
                "home_loc": HOME_COORDS.get(g[f"{side}_team"]),
            })
    for rs in rows.values():
        prev = None
        for i, r in enumerate(rs):
            r["rest"] = days_between(prev, r["date"]) - 1 if prev else None
            prev = r["date"]
            # 직전 경기 장소 → 이번 경기 장소 (시즌 첫 경기는 연고지에서 출발)
            r["travel_km"] = km(rs[i - 1]["loc"] if i else r["home_loc"], r["loc"]) if HOME_COORDS else None
    return rows


def split(rs):
    n = len(rs)
    if not n:
        return {"gp": 0}
    w = sum(r["pf"] > r["pa"] for r in rs)
    pf, pa = sum(r["pf"] for r in rs), sum(r["pa"] for r in rs)
    return {
        "gp": n, "w": w, "l": n - w, "win_pct": pct(w, n),
        "pf_pg": round(pf / n, 1), "pa_pg": round(pa / n, 1),
        "margin_pg": round((pf - pa) / n, 1),
        "avg_reg_total": round(sum(r["reg_total"] for r in rs) / n, 1),
    }


def efficiency(rs):
    """페이스·효율·Four Factors (팀 스탯이 있는 경기만)"""
    rs = [r for r in rs if r["st"].get("fga")]
    if not rs:
        return {}
    S = lambda k, side="st": sum(r[side].get(k, 0) for r in rs)
    p_me = sum(poss(r["st"]) for r in rs)
    p_op = sum(poss(r["ost"]) for r in rs)
    p_avg = (p_me + p_op) / 2
    pf, pa = sum(r["reg_pf"] for r in rs), sum(r["reg_pa"] for r in rs)
    # 페이스는 정규시간 기준으로 맞추기 위해 연장 경기는 포제션을 정규/(정규+5·연장수)로 보정
    p40 = sum((poss(r["st"]) + poss(r["ost"])) / 2 * REG_MIN / (REG_MIN + 5 * r["ot_n"]) for r in rs)
    fga, fgm, fg3m = S("fga"), S("fgm"), S("fg3m")
    ofga, ofgm, ofg3m = S("fga", "ost"), S("fgm", "ost"), S("fg3m", "ost")
    return {
        "pace": round(p40 / len(rs), 1),                      # 정규시간(KBL 40분·NBA 48분)당 포제션
        "ortg": round(sum(r["pf"] for r in rs) / p_avg * 100, 1),
        "drtg": round(sum(r["pa"] for r in rs) / p_avg * 100, 1),
        "net_rtg": round((sum(r["pf"] for r in rs) - sum(r["pa"] for r in rs)) / p_avg * 100, 1),
        "efg": pct(fgm + 0.5 * fg3m, fga),
        "opp_efg": pct(ofgm + 0.5 * ofg3m, ofga),
        "tov_pct": pct(S("tov"), p_me),
        "opp_tov_pct": pct(S("tov", "ost"), p_op),
        "oreb_pct": pct(S("oreb"), S("oreb") + S("dreb", "ost")),
        "dreb_pct": pct(S("dreb"), S("dreb") + S("oreb", "ost")),
        "ft_rate": pct(S("ftm"), fga),
        "opp_ft_rate": pct(S("ftm", "ost"), ofga),
        "fg3a_rate": pct(S("fg3a"), fga),
        "fg3_pct": pct(fg3m, S("fg3a")),
        "opp_fg3_pct": pct(ofg3m, S("fg3a", "ost")),
        "reg_pf_pg": round(pf / len(rs), 1), "reg_pa_pg": round(pa / len(rs), 1),
    }


def market_line(g: dict, side: str):
    """마감 배당 → 해당 팀 기준 핸디·총점 기준선 (없으면 None)"""
    cl = g.get("closing_line") or {}
    hs, tot = cl.get("home_spread"), cl.get("total")
    if hs is None and tot is None:
        return None
    return {"spread": None if hs is None else (hs if side == "home" else -hs), "total": tot}


def market(rs):
    """마감 라인 기준 ATS(연장 포함 최종 스코어)·언오버 성적"""
    rs = [r for r in rs if r.get("line")]
    ats = [r for r in rs if r["line"]["spread"] is not None]
    if not rs:
        return {}

    def cover(sub):
        w = sum(r["pf"] - r["pa"] + r["line"]["spread"] > 0 for r in sub)
        p = sum(r["pf"] - r["pa"] + r["line"]["spread"] == 0 for r in sub)
        return {"n": len(sub), "w": w, "l": len(sub) - w - p, "p": p, "cover_pct": pct(w, len(sub) - p)}

    ou = [r for r in rs if r["line"]["total"] is not None]
    over = sum(r["total"] > r["line"]["total"] for r in ou)
    push = sum(r["total"] == r["line"]["total"] for r in ou)
    return {
        "ats": cover(ats),
        "ats_fav": cover([r for r in ats if r["line"]["spread"] < 0]),
        "ats_dog": cover([r for r in ats if r["line"]["spread"] > 0]),
        "ats_home": cover([r for r in ats if r["is_home"]]),
        "ats_away": cover([r for r in ats if not r["is_home"]]),
        "ats_b2b": cover([r for r in ats if r["rest"] == 0]),
        "ats_last10": cover(ats[-10:]),
        # 마감 핸디 대비 평균 초과 득실 (+면 시장이 과소평가)
        "margin_vs_spread": round(sum(r["pf"] - r["pa"] + r["line"]["spread"] for r in ats) / len(ats), 1)
        if ats else None,
        "ou_close": {"n": len(ou), "over": over, "under": len(ou) - over - push, "push": push,
                     "over_pct": pct(over, len(ou) - push)},
        "ou_close_last10": {"over": sum(r["total"] > r["line"]["total"] for r in ou[-10:]),
                            "n": len(ou[-10:])},
        # 마감 총점 대비 평균 초과 득점 (+면 오버 성향)
        "total_vs_close": round(sum(r["total"] - r["line"]["total"] for r in ou) / len(ou), 1) if ou else None,
    }


def summarize(rs):
    n = len(rs)
    s = split(rs)
    s.update(efficiency(rs))
    s.update({
        "ot_rate": pct(sum(r["ot"] for r in rs), n),
        "over_rate_reg": {str(L): pct(sum(r["reg_total"] > L for r in rs), n) for L in TOTAL_LINES},
        "home": split([r for r in rs if r["is_home"]]),
        "away": split([r for r in rs if not r["is_home"]]),
        "last10": {**split(rs[-10:]), **{k: v for k, v in efficiency(rs[-10:]).items()
                                         if k in ("pace", "ortg", "drtg", "net_rtg")}},
        "last10_log": [
            f'{r["date"]} {"vs" if r["is_home"] else "@"} {r["opp_short"]} {r["pf"]}-{r["pa"]} '
            f'{"W" if r["pf"] > r["pa"] else "L"}' + (" (OT)" if r["ot"] else "")
            for r in rs[-10:]
        ],
        "streak": streak(rs),
        "last_game_date": rs[-1]["date"],
        # 휴식: 0 = 연전(백투백). 최근 경기 전 휴식일과 시즌 연전 성적
        "last_rest_days": rs[-1]["rest"],
        "b2b": split([r for r in rs if r["rest"] == 0]),
    })
    m = market(rs)
    if m:
        s["market"] = m
    if HOME_COORDS:
        last = rs[-1]["date"]
        s["last_travel_km"] = rs[-1]["travel_km"]
        s["travel_7d_km"] = sum(r["travel_km"] or 0 for r in rs if days_between(r["date"], last) < 7)
        s["home_loc"] = rs[-1]["home_loc"]
        s["last_loc"] = rs[-1]["loc"]   # 다음 경기 이동거리 = km(last_loc, 다음 경기 홈팀 좌표)
    return s


def streak(rs):
    key = rs[-1]["pf"] > rs[-1]["pa"]
    n = 0
    for r in reversed(rs):
        if (r["pf"] > r["pa"]) == key:
            n += 1
        else:
            break
    return f'{"W" if key else "L"}{n}'


def build_teams(games):
    out = {}
    for team, rs in team_rows(games).items():
        out[team] = summarize(rs)
    return dict(sorted(out.items(), key=lambda kv: -(kv[1].get("win_pct") or 0)))


def build_leaders(games, teams):
    agg = defaultdict(lambda: {"gp": 0, "min": 0.0, "pts": 0, "reb": 0, "ast": 0, "fg3m": 0, "starts": 0})
    last_date = {}
    for g in games:
        for side in ("home", "away"):
            team = g[f"{side}_team"]
            last_date[team] = g["date"]
            for p in g.get(f"{side}_players", []):
                if p.get("dnp"):
                    continue
                a = agg[(team, p.get("player_id") or p.get("name"))]
                a.update(name=p.get("name"), pos=p.get("pos"))
                a["gp"] += 1
                a["starts"] += bool(p.get("starter"))
                a["last_played"] = g["date"]
                for k in ("min", "pts", "reb", "ast", "fg3m"):
                    a[k] += p.get(k, 0)
    by_team = defaultdict(list)
    for (team, _), a in agg.items():
        gp = a["gp"]
        row = {"name": a["name"], "pos": a["pos"], "gp": gp, "starts": a["starts"],
               "last_played": a["last_played"],
               "missed_last_game": a["last_played"] != last_date.get(team)}
        for k in ("min", "pts", "reb", "ast", "fg3m"):
            row[f"{k}_pg"] = round(a[k] / gp, 1)
        by_team[team].append(row)
    return {t: sorted(v, key=lambda x: -x["min_pg"] * x["gp"])[:7]
            for t, v in by_team.items() if t in teams}


def build_h2h(games):
    pairs = defaultdict(list)
    for g in games:
        key = " vs ".join(sorted([g["home_team"], g["away_team"]]))
        pairs[key].append(f'{g["date"]} {g["away_short"]} {g["away_score"]}-{g["home_score"]} '
                          f'{g["home_short"]}' + (" (OT)" if g.get("overtime") else "")
                          + (f' [{g["game_type"]}]' if g.get("game_type") != "REG" else ""))
    return {k: v[-5:] for k, v in pairs.items()}


def league_avg(games):
    if not games:
        return {}
    n = len(games)
    return {
        "games": n,
        "home_win_pct": pct(sum(g["home_score"] > g["away_score"] for g in games), n),
        "avg_total": round(sum(g["total_points"] for g in games) / n, 1),
        "avg_reg_total": round(sum(g["reg_total_points"] for g in games) / n, 1),
        "ot_rate": pct(sum(bool(g.get("overtime")) for g in games), n),
        "over_rate_reg": {str(L): pct(sum(g["reg_total_points"] > L for g in games), n) for L in TOTAL_LINES},
        **league_market(games),
    }


def league_market(games):
    cl = [g for g in games if (g.get("closing_line") or {}).get("home_spread") is not None]
    ou = [g for g in games if (g.get("closing_line") or {}).get("total") is not None]
    if not cl and not ou:
        return {}
    m = lambda g: g["home_score"] - g["away_score"] + g["closing_line"]["home_spread"]
    fav_cover = [m(g) < 0 if g["closing_line"]["home_spread"] > 0 else m(g) > 0
                 for g in cl if g["closing_line"]["home_spread"] != 0 and m(g) != 0]
    return {"market": {
        "games_with_line": len(cl),
        "home_cover_pct": pct(sum(m(g) > 0 for g in cl), sum(m(g) != 0 for g in cl)),
        "fav_cover_pct": pct(sum(fav_cover), len(fav_cover)),
        "over_close_pct": pct(sum(g["total_points"] > g["closing_line"]["total"] for g in ou),
                              sum(g["total_points"] != g["closing_line"]["total"] for g in ou)),
    }}


# ----------------------------------------------------------------------
def upload(content: str, path: str):
    token, repo = os.getenv("GITHUB_TOKEN"), os.getenv("GITHUB_REPOSITORY")
    if not token or not repo:
        with open(os.path.join(ROOT, path), "w", encoding="utf-8") as fh:
            fh.write(content)
        print(f"  💾 로컬 저장: {path}")
        return
    h = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    r = requests.get(url, headers=h)
    payload = {"message": f"[{LEAGUE}] 통계 집계 업데이트",
               "content": base64.b64encode(content.encode()).decode(), "branch": "main"}
    if r.status_code == 200:
        payload["sha"] = r.json()["sha"]
    r = requests.put(url, headers=h, json=payload)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"업로드 실패 {r.status_code}: {r.text[:200]}")
    print(f"  📁 {path} 업로드 완료")


def main():
    games = load_games()
    season = [g for g in games if g["date"] >= SEASON_START]
    past = [g for g in games if g["date"] < SEASON_START]
    past_season_start = f"{int(SEASON_START[:4]) - 1}{SEASON_START[4:]}"
    last_reg = [g for g in past if g["date"] >= past_season_start and g["game_type"] == "REG"]

    print(f"===== {LEAGUE} 집계: 이번 시즌 {len(season)}경기 / 지난 시즌 정규 {len(last_reg)}경기 =====")
    if not season:
        if kst_now().strftime("%Y%m%d") > CONFIG[LEAGUE]["alarm"]:
            print("❌ 이번 시즌 경기 데이터가 0건입니다 — 수집 단계 확인 필요")
            sys.exit(1)
        print("  이번 시즌 데이터 없음 — 집계 건너뜀")
        return

    teams = build_teams(season)
    out = {
        "meta": {
            "generated_kst": kst_now().strftime("%Y-%m-%d %H:%M"),
            "season_start": SEASON_START,
            "games": len(season),
            "last_game_date": season[-1]["date"],
            "league_avg": league_avg(season),
            "league_avg_last_season": league_avg(last_reg),
            "notes": "reg_* = 4쿼터까지(연장 제외) / pace = 40분당 포제션 / ortg·drtg = 100포제션당 득·실점 "
                     "/ 컵대회·올스타 제외 / last_rest_days 0 = 연전"
                     + (" / market = 마감 배당(DraftKings) 기준 ATS·언오버, 연장 포함 최종 스코어" if LEAGUE == "NBA" else "")
                     + (" / *_km = 연고지 좌표 기준 직선 이동거리" if HOME_COORDS else ""),
        },
        "teams": teams,
        "last_season": build_teams(last_reg),
        "leaders": build_leaders(season, teams),
        "h2h": build_h2h(past + season),
    }
    upload(json.dumps(out, ensure_ascii=False, indent=1), OUT_PATH)


if __name__ == "__main__":
    main()
