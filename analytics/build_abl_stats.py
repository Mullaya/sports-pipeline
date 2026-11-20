"""ABL(호주 프로야구) 통계 집계 → analytics/ABL_stats.json

- 팀: 시즌 전적, 홈/원정, 최근 10경기, 경기당 득실(rpg/rapg), 득실차, 9이닝/7이닝 분리
- 토탈: 리그·구장별 평균 득점, 7.5/8/8.5/9 오버 비율 (9이닝 정규 경기 기준)
- H2H: 같은 시즌 맞대결 결과
- 전 시즌 팀 요약(시즌 초반 표본 부족 보완용)
StatsAPI ABL 데이터에는 예고 선발이 없어 투수는 승/패 투수 기록만 집계.
"""
import base64
import glob
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINES = (7.5, 8, 8.5, 9)
KST = timezone(timedelta(hours=9))


def load_games():
    seen = {}
    for sub in ("historical", "daily"):
        for f in sorted(glob.glob(os.path.join(ROOT, "data/ABL", sub, "*.json"))):
            for g in json.load(open(f, encoding="utf-8")).get("games", []):
                if g.get("total_runs") is None or g.get("game_type") != "R":
                    continue
                seen[g["game_id"]] = g          # daily가 나중에 읽혀 덮어씀
    return sorted(seen.values(), key=lambda g: g["start_utc"])


def pct(a, b, nd=3):
    return round(a / b, nd) if b else None


def team_summary(rows):
    n = len(rows)
    if not n:
        return None
    w = sum(r["win"] for r in rows)
    rf, ra = sum(r["rf"] for r in rows), sum(r["ra"] for r in rows)
    nine = [r for r in rows if r["inn"] == 9]
    out = {"games": n, "w": w, "l": n - w, "win_pct": pct(w, n),
           "rpg": round(rf / n, 2), "rapg": round(ra / n, 2), "run_diff_pg": round((rf - ra) / n, 2),
           "avg_total": round((rf + ra) / n, 2)}
    if nine:
        out["avg_total_9inn"] = round(sum(r["rf"] + r["ra"] for r in nine) / len(nine), 2)
        out["over_rates_9inn"] = {str(l): pct(sum(r["rf"] + r["ra"] > l for r in nine), len(nine)) for l in LINES}
    return out


def build(games):
    seasons = sorted({g["season"] for g in games})
    cur = seasons[-1]
    res = {"league": "ABL", "updated_kst": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
           "current_season": cur, "seasons": {}}
    for s in seasons:
        gs = [g for g in games if g["season"] == s]
        rows = defaultdict(list)
        for g in gs:
            inn = g.get("scheduled_innings") or 9
            for side, opp in (("home", "away"), ("away", "home")):
                rf, ra = g[f"{side}_score"], g[f"{opp}_score"]
                rows[g[f"{side}_team"]].append({"date": g["date_kst"], "opp": g[f"{opp}_team"], "side": side,
                                                "rf": rf, "ra": ra, "win": int(rf > ra), "inn": inn})
        teams = {}
        for t, rs in rows.items():
            teams[t] = {"season": team_summary(rs),
                        "home": team_summary([r for r in rs if r["side"] == "home"]),
                        "away": team_summary([r for r in rs if r["side"] == "away"]),
                        "last10": team_summary(rs[-10:]),
                        "last10_log": [f'{r["date"]} {"H" if r["side"] == "home" else "A"} {r["opp"]} {r["rf"]}-{r["ra"]}' for r in rs[-10:]]}
        nine = [g for g in gs if (g.get("scheduled_innings") or 9) == 9]
        venues = defaultdict(list)
        for g in nine:
            venues[g["venue"]].append(g["total_runs"])
        h2h = defaultdict(list)
        for g in gs:
            k = " vs ".join(sorted([g["home_team"], g["away_team"]]))
            h2h[k].append(f'{g["date_kst"]} {g["away_team"]} {g["away_score"]} @ {g["home_team"]} {g["home_score"]}')
        res["seasons"][str(s)] = {
            "games": len(gs),
            "league": {"avg_total_9inn": round(sum(g["total_runs"] for g in nine) / len(nine), 2) if nine else None,
                       "over_rates_9inn": {str(l): pct(sum(g["total_runs"] > l for g in nine), len(nine)) for l in LINES},
                       "home_win_pct": pct(sum(g["home_score"] > g["away_score"] for g in gs), len(gs)),
                       "seven_inning_games": len(gs) - len(nine)},
            "venues": {v: {"games": len(t), "avg_total": round(sum(t) / len(t), 2),
                           "over_rates": {str(l): pct(sum(x > l for x in t), len(t)) for l in LINES}}
                       for v, t in venues.items()},
            "teams": teams,
            "h2h": {k: v[-8:] for k, v in h2h.items()} if s == cur else {},
        }
    return res


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
        payload = {"message": "[ABL] 통계 집계 업데이트",
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
    print(f"[ABL] 정규시즌 완료 경기 {len(gs)}")
    upload(json.dumps(build(gs), ensure_ascii=False, indent=2), "analytics/ABL_stats.json")
