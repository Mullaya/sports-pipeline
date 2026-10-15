"""KBL 누적 집계 → analytics/KBL_stats.json

입력: data/KBL/daily/*.json + data/KBL/historical/*.json (game_id 중복 제거)
출력 구조:
  meta         : 생성 시각, 시즌 시작일, 집계 경기 수, 리그 평균
  teams        : 이번 시즌 팀별 성적 — 홈/원정, 최근 10경기, 페이스·공수 효율(ORtg/DRtg/Net),
                 Four Factors, 정규시간 총점·언오버 비율, 연장 비율, 휴식일/연전
  last_season  : 지난 시즌 정규리그 팀 성적 (시즌 초 표본 부족 시 기준점)
  leaders      : 팀별 출전시간 상위 7명 (결장자 영향도 판단)
  h2h          : 팀 쌍별 최근 맞대결 5경기 (지난 시즌 포함)

컵대회(CUP)·올스타(ALLSTAR)는 집계에서 제외. 정규(REG)+플레이오프(PO/FINAL)만 사용.
최근 N경기 지표는 매 실행 때 일별 파일에서 재계산한다.
"""
import os
import sys
import json
import glob
import base64
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEASON_START = os.getenv("KBL_SEASON_START", "20260901")   # 2026-27 시즌
OUT_PATH = "analytics/KBL_stats.json"
TOTAL_LINES = (145.5, 150.5, 155.5, 160.5, 165.5)
COUNTED = ("REG", "PO", "FINAL")


def kst_now():
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=9)


def load_games() -> list:
    files = glob.glob(os.path.join(ROOT, "data", "KBL", "historical", "*.json")) + \
        glob.glob(os.path.join(ROOT, "data", "KBL", "daily", "*.json"))
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
            uniq[g["game_id"]] = g
    games = [g for g in uniq.values() if g.get("game_type") in COUNTED]
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
                "total": g.get("total_points", 0),
                "reg_total": g.get("reg_total_points", g.get("total_points", 0)),
                "st": st, "ost": ost,
            })
    for rs in rows.values():
        prev = None
        for r in rs:
            r["rest"] = days_between(prev, r["date"]) - 1 if prev else None
            prev = r["date"]
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
    # 페이스는 정규 40분 기준으로 맞추기 위해 연장 경기는 포제션을 40/45로 보정
    p40 = sum((poss(r["st"]) + poss(r["ost"])) / 2 * (40 / 45 if r["ot"] else 1) for r in rs)
    fga, fgm, fg3m = S("fga"), S("fgm"), S("fg3m")
    ofga, ofgm, ofg3m = S("fga", "ost"), S("fgm", "ost"), S("fg3m", "ost")
    return {
        "pace": round(p40 / len(rs), 1),                      # 40분당 포제션
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
    }


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
    payload = {"message": "[KBL] 통계 집계 업데이트",
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

    print(f"===== KBL 집계: 이번 시즌 {len(season)}경기 / 지난 시즌 정규 {len(last_reg)}경기 =====")
    if not season:
        if kst_now().strftime("%Y%m%d") > "20261015":
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
                     "/ 컵대회·올스타 제외 / last_rest_days 0 = 연전",
        },
        "teams": teams,
        "last_season": build_teams(last_reg),
        "leaders": build_leaders(season, teams),
        "h2h": build_h2h(past + season),
    }
    upload(json.dumps(out, ensure_ascii=False, indent=1), OUT_PATH)


if __name__ == "__main__":
    main()
