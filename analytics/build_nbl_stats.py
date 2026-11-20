"""NBL(호주 농구) 통계 집계 → analytics/NBL_stats.json

- 팀: 시즌/홈/원정/최근 10경기 득실, 정규시간 총점, 총점 라인별 오버율, 연장 비율, 직전 휴식일
- 리그 평균 총점·홈 승률
- 주요 선수: 팀별 평균 출전시간 상위 7명 + 최근 2경기 결장(DNP) 여부
- H2H: 같은 팀 쌍 최근 6경기 (지난 시즌 포함)
- 지난 시즌 팀 요약 (시즌 초반 표본 보완)
정규시즌(REG)만 집계. 시즌 = ESPN season.year (예: 2027 = 2026-27).
"""
import base64
import glob
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINES = (180.5, 185.5, 190.5, 195.5, 200.5)
KST = timezone(timedelta(hours=9))


def load_games():
    seen = {}
    for sub in ("historical", "daily"):
        for f in sorted(glob.glob(os.path.join(ROOT, "data/NBL", sub, "*.json"))):
            for g in json.load(open(f, encoding="utf-8")).get("games", []):
                if g.get("game_type") != "REG" or g.get("home_score") is None:
                    continue
                g = dict(g)
                g["_date"] = os.path.basename(f)[:8]
                seen[str(g["game_id"])] = g
    return sorted(seen.values(), key=lambda g: g.get("start_utc") or g["_date"])


def r1(x):
    return round(x, 1)


def summ(rows):
    n = len(rows)
    if not n:
        return None
    w = sum(r["win"] for r in rows)
    pf, pa = sum(r["pf"] for r in rows), sum(r["pa"] for r in rows)
    reg = [r["reg_total"] for r in rows]
    return {"games": n, "w": w, "l": n - w, "ppg": r1(pf / n), "oppg": r1(pa / n), "diff": r1((pf - pa) / n),
            "avg_total": r1((pf + pa) / n), "avg_reg_total": r1(sum(reg) / n),
            "over_rates_reg": {str(l): round(sum(t > l for t in reg) / n, 3) for l in LINES},
            "ot_games": sum(r["ot"] for r in rows)}


def _min(v):
    try:
        return float(str(v).split(":")[0])
    except Exception:
        return None


def build(games):
    seasons = sorted({g.get("season") for g in games if g.get("season")})
    cur = seasons[-1]
    today = datetime.now(KST).strftime("%Y%m%d")
    out = {"league": "NBL", "updated_kst": datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "current_season": cur}
    for s in seasons[-2:]:
        gs = [g for g in games if g.get("season") == s]
        rows = defaultdict(list)
        players = defaultdict(lambda: defaultdict(list))
        for g in gs:
            reg_t = (g.get("reg_home_score") or g["home_score"]) + (g.get("reg_away_score") or g["away_score"])
            for side, opp in (("home", "away"), ("away", "home")):
                t = g[f"{side}_team"]
                pf, pa = g[f"{side}_score"], g[f"{opp}_score"]
                rows[t].append({"date": g["_date"], "opp": g[f"{opp}_team"], "side": side, "pf": pf, "pa": pa,
                                "win": int(pf > pa), "reg_total": reg_t, "ot": int(bool(g.get("overtime")))})
                for p in g.get(f"{side}_players") or []:
                    players[t][p.get("name")].append((g["_date"], p.get("dnp"), _min(p.get("minutes") or p.get("MIN"))))
        teams = {}
        for t, rs in rows.items():
            info = {"season": summ(rs), "home": summ([r for r in rs if r["side"] == "home"]),
                    "away": summ([r for r in rs if r["side"] == "away"]), "last10": summ(rs[-10:]),
                    "last5_log": [f'{r["date"]} {"H" if r["side"] == "home" else "A"} {r["opp"]} {r["pf"]}-{r["pa"]}' for r in rs[-5:]]}
            if s == cur:
                last = rs[-1]["date"]
                info["rest_days_since_last"] = (datetime.strptime(today, "%Y%m%d") - datetime.strptime(last, "%Y%m%d")).days - 1
                recent_dates = sorted({r["date"] for r in rs})[-2:]
                ps = []
                for name, apps in players[t].items():
                    mins = [m for _, d, m in apps if not d and m is not None]
                    if not mins:
                        continue
                    ps.append({"name": name, "gp": len(mins), "mpg": r1(sum(mins) / len(mins)),
                               "missed_recent": [d for d, dnp, _ in apps if d in recent_dates and dnp]
                               + [d for d in recent_dates if d not in {a[0] for a in apps}]})
                info["key_players"] = sorted(ps, key=lambda p: -p["mpg"] * p["gp"])[:7]
            teams[t] = info
        block = {"games": len(gs),
                 "league_avg_total": r1(sum(g["home_score"] + g["away_score"] for g in gs) / len(gs)) if gs else None,
                 "home_win_pct": round(sum(g["home_score"] > g["away_score"] for g in gs) / len(gs), 3) if gs else None,
                 "teams": teams}
        out["season" if s == cur else "last_season"] = block
    h2h = defaultdict(list)
    for g in games:
        h2h[" vs ".join(sorted([g["home_team"], g["away_team"]]))].append(
            f'{g["_date"]} {g["away_team"]} {g["away_score"]} @ {g["home_team"]} {g["home_score"]}')
    out["h2h"] = {k: v[-6:] for k, v in h2h.items()}
    return out


def upload(content, path):
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
        payload = {"message": "[NBL] 통계 집계 업데이트",
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


if __name__ == "__main__":
    gs = load_games()
    print(f"[NBL] 정규시즌 경기 {len(gs)}")
    if gs:
        upload(json.dumps(build(gs), ensure_ascii=False, indent=2), "analytics/NBL_stats.json")
