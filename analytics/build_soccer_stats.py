"""축구 누적 집계 (J1~J3·K1·K2·유럽 5대 리그) → analytics/{LEAGUE}_stats.json

실행: python analytics/build_soccer_stats.py EPL LALIGA ...   (인자 없으면 전체)
입력: data/{LEAGUE}/daily/*.json + data/{LEAGUE}/historical/*.json (game_id 중복 제거)
출력:
  meta   : 생성 시각, 시즌 시작일, 경기 수, 리그 평균(홈승·무·원정승, 평균 골, 언오버·양팀득점 비율)
  teams  : 팀별 season / home / away / last6 —
           승무패, 득실, xG·xGA(있으면), 유효슈팅, 1.5/2.5/3.5 오버 비율, 양팀득점, 무실점·무득점 비율
           + last6_log(최근 경기 기록), rest_days(직전 경기 후 휴식일)
  h2h    : 최근 맞대결(지난 시즌 포함 최대 6경기)
정규 리그(REG)만 집계. 친선(PRE)·플레이오프 등은 제외.
"""
import base64
import glob
import json
import os
import sys
from datetime import datetime, timezone, timedelta

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from collectors.flashscore_soccer import SOCCER_LEAGUES, soccer_season_key  # noqa: E402

LINES = (1.5, 2.5, 3.5)


def load_games(league: str) -> list:
    seen = {}
    for sub in ("historical", "daily"):     # daily가 나중 → 같은 경기면 daily 우선
        for f in sorted(glob.glob(os.path.join(ROOT, "data", league, sub, "*.json"))):
            try:
                data = json.load(open(f, encoding="utf-8"))
            except Exception:
                continue
            for g in data.get("games", []):
                if g.get("home_score") is None or g.get("away_score") is None:
                    continue
                g["date"] = (g.get("start_local") or g.get("start_utc", ""))[:10].replace("-", "")
                seen[g.get("game_id") or f"{g['date']}{g['home_team']}{g['away_team']}"] = g
    return sorted(seen.values(), key=lambda g: g.get("start_utc", ""))


def pct(a, n):
    return round(a / n, 3) if n else None


def avg(a, n, d=2):
    return round(a / n, d) if n else None


def rows(games: list, team: str) -> list:
    R = []
    for g in games:
        for s, o in (("home", "away"), ("away", "home")):
            if g[f"{s}_team"] != team:
                continue
            hs, os_ = g.get(f"{s}_stats") or {}, g.get(f"{o}_stats") or {}
            R.append({
                "date": g["date"], "home": s == "home", "opp": g[f"{o}_team"],
                "gf": g[f"{s}_score"], "ga": g[f"{o}_score"],
                "xg": hs.get("xg"), "xga": os_.get("xg"),
                "sot": hs.get("shots_on_target"), "sota": os_.get("shots_on_target"),
            })
    return R


def split(R: list) -> dict:
    n = len(R)
    if not n:
        return {"gp": 0}
    gf, ga = sum(r["gf"] for r in R), sum(r["ga"] for r in R)
    xr = [r for r in R if r["xg"] is not None and r["xga"] is not None]
    sr = [r for r in R if r["sot"] is not None and r["sota"] is not None]
    tot = [r["gf"] + r["ga"] for r in R]
    out = {
        "gp": n, "w": sum(r["gf"] > r["ga"] for r in R), "d": sum(r["gf"] == r["ga"] for r in R),
        "l": sum(r["gf"] < r["ga"] for r in R),
        "gf_pg": avg(gf, n), "ga_pg": avg(ga, n), "total_pg": avg(gf + ga, n),
        "over": {str(L): pct(sum(t > L for t in tot), n) for L in LINES},
        "btts": pct(sum(r["gf"] > 0 and r["ga"] > 0 for r in R), n),
        "clean_sheet": pct(sum(r["ga"] == 0 for r in R), n),
        "failed_to_score": pct(sum(r["gf"] == 0 for r in R), n),
    }
    out["ppg"] = avg(3 * out["w"] + out["d"], n)
    if xr:
        xg, xga = sum(r["xg"] for r in xr), sum(r["xga"] for r in xr)
        out.update({"xg_pg": avg(xg, len(xr)), "xga_pg": avg(xga, len(xr)),
                    "xg_n": len(xr),
                    # 실제 득실 − xG: +면 운/결정력 과열(회귀 후보)
                    "g_minus_xg": avg(sum(r["gf"] for r in xr) - xg, len(xr)),
                    "ga_minus_xga": avg(sum(r["ga"] for r in xr) - xga, len(xr))})
    if sr:
        out.update({"sot_pg": avg(sum(r["sot"] for r in sr), len(sr), 1),
                    "sota_pg": avg(sum(r["sota"] for r in sr), len(sr), 1)})
    return out


def league_avg(games: list) -> dict:
    n = len(games)
    if not n:
        return {"games": 0}
    tot = [g["home_score"] + g["away_score"] for g in games]
    return {
        "games": n,
        "home_win": pct(sum(g["home_score"] > g["away_score"] for g in games), n),
        "draw": pct(sum(g["home_score"] == g["away_score"] for g in games), n),
        "away_win": pct(sum(g["home_score"] < g["away_score"] for g in games), n),
        "goals_pg": avg(sum(tot), n),
        "home_gf_pg": avg(sum(g["home_score"] for g in games), n),
        "away_gf_pg": avg(sum(g["away_score"] for g in games), n),
        "over": {str(L): pct(sum(t > L for t in tot), n) for L in LINES},
        "btts": pct(sum(g["home_score"] > 0 and g["away_score"] > 0 for g in games), n),
    }


def upload(content: str, path: str, league: str):
    token, repo = os.getenv("GITHUB_TOKEN"), os.getenv("GITHUB_REPOSITORY")
    if not token or not repo:
        with open(os.path.join(ROOT, path), "w", encoding="utf-8") as fh:
            fh.write(content)
        print(f"  💾 로컬 저장: {path}")
        return
    h = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    for attempt in range(5):
        r = requests.get(url, headers=h)
        payload = {"message": f"[{league}] 통계 집계 업데이트",
                   "content": base64.b64encode(content.encode()).decode(), "branch": "main"}
        if r.status_code == 200:
            payload["sha"] = r.json()["sha"]
        r = requests.put(url, headers=h, json=payload)
        if r.status_code in (200, 201):
            print(f"  📁 {path} 업로드 완료")
            return
        if r.status_code in (409, 422, 500, 502, 503) and attempt < 4:
            continue
        raise RuntimeError(f"업로드 실패 {r.status_code}: {r.text[:200]}")


def season_start(league: str, today: str) -> str:
    y1, y2 = soccer_season_key(today, SOCCER_LEAGUES[league]["calendar"])
    return f"{y1}0701" if y1 != y2 else f"{y1}0201"


def build(league: str) -> bool:
    kst = datetime.now(timezone(timedelta(hours=9)))
    today = kst.strftime("%Y%m%d")
    start = season_start(league, today)
    games = [g for g in load_games(league) if g.get("game_type", "REG") == "REG"]
    season = [g for g in games if g["date"] >= start]
    if not season:
        print(f"  [{league}] 이번 시즌 경기 없음 — 건너뜀")
        return False
    teams = sorted({g["home_team"] for g in season} | {g["away_team"] for g in season})
    T = {}
    for t in teams:
        R = rows(season, t)
        T[t] = {
            "season": split(R), "home": split([r for r in R if r["home"]]),
            "away": split([r for r in R if not r["home"]]), "last6": split(R[-6:]),
            "last6_log": [f"{r['date']} {'H' if r['home'] else 'A'} {r['opp']} {r['gf']}-{r['ga']}"
                          + (f" (xG {r['xg']}-{r['xga']})" if r["xg"] is not None else "") for r in R[-6:]],
            "last_game_date": R[-1]["date"] if R else None,
            "rest_days": (datetime.strptime(today, "%Y%m%d") - datetime.strptime(R[-1]["date"], "%Y%m%d")).days - 1 if R else None,
        }
    # 승점 순위
    order = sorted(teams, key=lambda t: (-(3 * T[t]["season"]["w"] + T[t]["season"]["d"]),
                                         -(T[t]["season"]["gf_pg"] - T[t]["season"]["ga_pg"])))
    for i, t in enumerate(order, 1):
        T[t]["rank"] = i
        T[t]["points"] = 3 * T[t]["season"]["w"] + T[t]["season"]["d"]
    h2h = {}
    for g in games:
        k = " vs ".join(sorted((g["home_team"], g["away_team"])))
        h2h.setdefault(k, []).append(f"{g['date']} {g['home_team']} {g['home_score']}-{g['away_score']} {g['away_team']}")
    h2h = {k: v[-6:] for k, v in h2h.items() if any(x[:8] >= start for x in v)}
    out = {"meta": {"generated_kst": kst.strftime("%Y-%m-%d %H:%M"), "league": league,
                    "season_start": start, "games": len(season),
                    "last_game_date": season[-1]["date"], "league_avg": league_avg(season),
                    "notes": "REG만 집계 / over는 해당 기준점 초과 비율 / g_minus_xg +는 득점 과열(회귀 후보) / rest_days는 오늘(KST) 기준"},
           "teams": {t: T[t] for t in order}, "h2h": h2h}
    upload(json.dumps(out, ensure_ascii=False, indent=1), f"analytics/{league}_stats.json", league)
    return True


if __name__ == "__main__":
    targets = sys.argv[1:] or list(SOCCER_LEAGUES)
    for lg in targets:
        try:
            build(lg)
        except Exception as e:
            print(f"  [{lg}] 집계 실패: {e}")
