"""유럽 하키(KHL / DEL / CZE) 누적 집계 → analytics/{LEAGUE}_stats.json

사용: python analytics/build_hockey_stats.py [KHL DEL CZE]   (인자 없으면 전부)

입력: data/{LEAGUE}/daily/*.json + data/{LEAGUE}/historical/*.json (game_id 중복 제거, 시즌 구분은 날짜)
출력 구조:
  meta        : 생성 시각, 시즌 시작일, 경기 수, 리그 평균(정규시간 총득점·무승부율·홈승률), 승점 규칙
  teams       : 이번 시즌 정규리그 팀 성적 — 순위표, 홈/원정, 최근 10경기(+로그), 연속 기록,
                정규시간 3-way(RW/RD/RL), 언오버 비율(정규시간, 사이트 정산 기준), 슈팅 점유율,
                SH%/SV%/PDO, PP/PK, 휴식일·백투백
  goalies     : 선발 골리별 SV%·GAA, 최근 5선발, 홈/원정, 마지막 선발일
  leaders     : 팀별 공격포인트 상위 6명 (득점 기록 기준 — KHL은 어시스트 미제공이라 골만)
  last_season : 지난 시즌 정규리그 팀 성적 (시즌 초 표본 부족 시 기준점)
  h2h         : 팀 쌍별 최근 맞대결 5경기 (지난 시즌 포함)

최근 N경기 지표는 매 실행 때 일별 파일에서 재계산한다 (MLB last5 스테일 문제 재발 방지).
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
TOTAL_LINES = (4.5, 5.5, 6.5)

LEAGUE_CFG = {
    # points: 정규승, 연장/SO승, 연장/SO패
    "KHL": {"season_start": os.getenv("KHL_SEASON_START", "20260801"), "points": (2, 2, 1),
            "fail_after": "20260915"},
    "DEL": {"season_start": os.getenv("DEL_SEASON_START", "20260801"), "points": (3, 2, 1),
            "fail_after": "20261001"},
    "CZE": {"season_start": os.getenv("CZE_SEASON_START", "20260801"), "points": (3, 2, 1),
            "fail_after": "20261001"},
}


def kst_now():
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=9)


def pct(a, b, nd=3):
    return round(a / b, nd) if b else None


def load_games(league: str) -> list:
    files = glob.glob(os.path.join(ROOT, "data", league, "historical", "*.json")) + \
        glob.glob(os.path.join(ROOT, "data", league, "daily", "*.json"))
    uniq = {}
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception as e:
            print(f"  ⚠️ {f} 읽기 실패: {e}")
            continue
        for g in d.get("games", []):
            if g.get("home_score") is None:
                continue
            g["date"] = d.get("date") or os.path.basename(f)[:8]
            uniq[str(g["game_id"])] = g
    return sorted(uniq.values(), key=lambda x: (x["date"], x.get("start_utc", "")))


def days_between(a: str, b: str) -> int:
    return (datetime.strptime(b, "%Y%m%d") - datetime.strptime(a, "%Y%m%d")).days


# ----------------------------------------------------------------------
def team_rows(games):
    rows = defaultdict(list)
    for g in games:
        for side in ("home", "away"):
            opp = "away" if side == "home" else "home"
            me, op = g[f"{side}_score"], g[f"{opp}_score"]
            end = g.get("end_type", "REG")
            if me > op:
                res = "W" if end == "REG" else "OTW"
            else:
                res = "L" if end == "REG" else "OTL"
            reg_me = g.get(f"reg_{side}_score", me)
            reg_op = g.get(f"reg_{opp}_score", op)
            st, ost = g.get(f"{side}_stats") or {}, g.get(f"{opp}_stats") or {}
            gks = g.get(f"{side}_goalies") or []
            rows[g[f"{side}_team"]].append({
                "date": g["date"], "is_home": side == "home", "opp": g[f"{opp}_team"],
                "gf": me, "ga": op, "res": res, "end": end,
                "reg": "RW" if reg_me > reg_op else ("RL" if reg_me < reg_op else "RD"),
                "reg_total": g.get("reg_total_goals", me + op),
                "sf": st.get("shots"), "sa": ost.get("shots"),
                "ppg": st.get("pp_goals") or 0, "ppo": st.get("pp_opps") or 0,
                "ppga": ost.get("pp_goals") or 0, "pko": ost.get("pp_opps") or 0,
                # SV%: 골리 기록(빈골문 제외) 우선, 없으면 팀 기준
                "gk_sa": sum(x.get("shots_against") or 0 for x in gks),
                "gk_ga": sum(x.get("goals_against") or 0 for x in gks),
                "gk_ok": bool(gks) and all(x.get("shots_against") is not None for x in gks),
            })
    return rows


def split(rs, points):
    n = len(rs)
    if not n:
        return {"gp": 0}
    rw = sum(r["res"] == "W" for r in rs)
    otw = sum(r["res"] == "OTW" for r in rs)
    otl = sum(r["res"] == "OTL" for r in rs)
    l = sum(r["res"] == "L" for r in rs)
    gf, ga = sum(r["gf"] for r in rs), sum(r["ga"] for r in rs)
    p_rw, p_otw, p_otl = points
    return {
        "gp": n, "w": rw + otw, "reg_wins": rw, "ot_wins": otw, "otl": otl, "l": l,
        "pts": rw * p_rw + otw * p_otw + otl * p_otl,
        "reg_w": sum(r["reg"] == "RW" for r in rs),
        "reg_d": sum(r["reg"] == "RD" for r in rs),
        "reg_l": sum(r["reg"] == "RL" for r in rs),
        "gf_pg": round(gf / n, 2), "ga_pg": round(ga / n, 2),
        "avg_reg_total": round(sum(r["reg_total"] for r in rs) / n, 2),
    }


def summarize(rs, points, today: str):
    s = split(rs, points)
    n = len(rs)
    shot_rows = [r for r in rs if r["sf"] is not None and r["sa"] is not None]
    sf, sa = sum(r["sf"] for r in shot_rows), sum(r["sa"] for r in shot_rows)
    gf_shot = sum(r["gf"] for r in shot_rows)
    gk_rows = [r for r in rs if r["gk_ok"]]
    gk_sa, gk_ga = sum(r["gk_sa"] for r in gk_rows), sum(r["gk_ga"] for r in gk_rows)
    sh, sv = pct(gf_shot, sf), pct(gk_sa - gk_ga, gk_sa)
    ppg, ppo = sum(r["ppg"] for r in rs), sum(r["ppo"] for r in rs)
    ppga, pko = sum(r["ppga"] for r in rs), sum(r["pko"] for r in rs)
    last = rs[-1]["date"]
    prev = rs[-2]["date"] if n > 1 else None

    s.update({
        "sf_pg": round(sf / len(shot_rows), 1) if shot_rows else None,
        "sa_pg": round(sa / len(shot_rows), 1) if shot_rows else None,
        "shot_share": pct(sf, sf + sa),
        "sh_pct": sh, "sv_pct": sv,
        "pdo": round((sh + sv) * 100, 1) if sh is not None and sv is not None else None,
        "pp_pct": pct(ppg, ppo), "pk_pct": round(1 - ppga / pko, 3) if pko else None,
        "reg_draw_rate": pct(s["reg_d"], n),
        "over_rate_reg": {str(L): pct(sum(r["reg_total"] > L for r in rs), n) for L in TOTAL_LINES},
        "home": split([r for r in rs if r["is_home"]], points),
        "away": split([r for r in rs if not r["is_home"]], points),
        "last10": split(rs[-10:], points),
        "last10_log": [
            f'{r["date"]} {"vs" if r["is_home"] else "@"} {r["opp"]} {r["gf"]}-{r["ga"]} {r["res"]}'
            for r in rs[-10:]
        ],
        "streak": streak(rs),
        "last_game_date": last,
        "days_since_last": days_between(last, today),
        "last_was_b2b": prev is not None and days_between(prev, last) == 1,
    })
    return s


def streak(rs):
    win = rs[-1]["res"] in ("W", "OTW")
    n = 0
    for r in reversed(rs):
        if (r["res"] in ("W", "OTW")) == win:
            n += 1
        else:
            break
    return f'{"W" if win else "L"}{n}'


def build_teams(games, points, today):
    rows = team_rows(games)
    teams = {t: summarize(rs, points, today) for t, rs in rows.items()}
    order = sorted(teams, key=lambda t: (-teams[t]["pts"], -(teams[t]["gf_pg"] - teams[t]["ga_pg"])))
    for i, t in enumerate(order, 1):
        teams[t]["rank_pts"] = i      # 전체 승점 순위 (컨퍼런스/디비전 구분 없음)
    return {t: teams[t] for t in order}


# ----------------------------------------------------------------------
def build_goalies(games):
    log = defaultdict(list)
    for g in games:
        for side in ("home", "away"):
            opp = "away" if side == "home" else "home"
            for gk in g.get(f"{side}_goalies") or []:
                if not gk.get("starter"):
                    continue
                key = f'{g[f"{side}_team"]}|{gk.get("player_id") or gk.get("name")}'
                log[key].append({**gk, "date": g["date"], "team": g[f"{side}_team"],
                                 "is_home": side == "home", "opp": g[f"{opp}_team"],
                                 "won": g[f"{side}_score"] > g[f"{opp}_score"]})
    out = {}
    for key, rs in log.items():
        out[key] = {
            "name": rs[-1].get("name"), "team": rs[-1]["team"],
            "starts": len(rs), "w": sum(r["won"] for r in rs),
            **gk_line(rs),
            "last5_starts": gk_line(rs[-5:]),
            "home": gk_line([r for r in rs if r["is_home"]]),
            "away": gk_line([r for r in rs if not r["is_home"]]),
            "last_start_date": rs[-1]["date"],
            "log": [f'{r["date"]} {"vs" if r["is_home"] else "@"} {r["opp"]} '
                    + (f'{r["saves"]}/{r["shots_against"]}' if r.get("shots_against") is not None else "SV 미상")
                    + (" W" if r["won"] else " L") for r in rs[-5:]],
        }
    return dict(sorted(out.items(), key=lambda kv: (kv[1]["team"], -kv[1]["starts"])))


def gk_line(rs):
    ok = [r for r in rs if r.get("shots_against") is not None]
    sa = sum(r["shots_against"] for r in ok)
    ga = sum(r.get("goals_against") or 0 for r in ok)
    toi = sum(r.get("toi") or 60 for r in ok)
    return {"gp_with_sv": len(ok), "sv_pct": pct(sa - ga, sa),
            "gaa": round(ga * 60 / toi, 2) if toi else None}


def build_leaders(games):
    agg = defaultdict(lambda: {"g": 0, "a": 0})
    for g in games:
        for x in g.get("goals") or []:
            side = x.get("team")
            if side not in ("home", "away"):
                continue
            team = g[f"{side}_team"]
            if x.get("author"):
                agg[(team, x["author"])]["g"] += 1
            for a in x.get("assists") or []:
                agg[(team, a)]["a"] += 1
    by_team = defaultdict(list)
    for (team, name), v in agg.items():
        by_team[team].append({"name": name, "g": v["g"], "a": v["a"], "pts": v["g"] + v["a"]})
    return {t: sorted(v, key=lambda x: (-x["pts"], -x["g"]))[:6] for t, v in by_team.items()}


def _pair(s):
    try:
        a, b = [int(v) for v in str(s).replace("-", ":").split(":")[:2]]
        return a, b
    except Exception:
        return None


def khl_goal_sides(games):
    """KHL 원본 goals에는 팀 필드가 없고 score는 'team_a:team_b' 기준이다.
    마지막 골 스코어를 최종 스코어(SO 결승골 제외)와 대조해 a가 홈인지 판정한 뒤,
    스코어 증가 쪽으로 각 골의 팀을 붙인다. 판정 불가 경기는 건너뜀."""
    for g in games:
        gl = [x for x in (g.get("goals") or []) if _pair(x.get("score"))]
        if not gl or any("team" in x for x in gl):
            continue
        gl.sort(key=lambda x: (int(x.get("period") or 0), int(x.get("time_s") or 0)))
        hs, as_ = g["home_score"], g["away_score"]
        if g.get("end_type") == "SO":
            hs, as_ = hs - (hs > as_), as_ - (as_ > hs)
        last = _pair(gl[-1]["score"])
        if last == (hs, as_):
            home_is_a = True
        elif last == (as_, hs):
            home_is_a = False
        else:
            continue
        prev = (0, 0)
        for x in gl:
            a, b = _pair(x["score"])
            x["team"] = "home" if (a > prev[0]) == home_is_a else "away"
            prev = (a, b)


def build_h2h(games):
    pairs = defaultdict(list)
    for g in games:
        key = " | ".join(sorted([g["home_team"], g["away_team"]]))
        tag = f' ({g["end_type"]})' if g.get("end_type") not in (None, "REG") else ""
        pairs[key].append(f'{g["date"]} {g["away_team"]} {g["away_score"]}-{g["home_score"]} {g["home_team"]}{tag}')
    return {k: v[-5:] for k, v in pairs.items()}


def league_avgs(games):
    n = len(games)
    if not n:
        return {}
    return {
        "avg_reg_total": round(sum(g.get("reg_total_goals", g["total_goals"]) for g in games) / n, 2),
        "reg_draw_rate": pct(sum(g.get("end_type") != "REG" for g in games), n),
        "home_win_rate": pct(sum(g["home_score"] > g["away_score"] for g in games), n),
        "home_reg_win_rate": pct(sum(g.get("reg_home_score", 0) > g.get("reg_away_score", 0) for g in games), n),
        "over_rate_reg": {str(L): pct(sum(g.get("reg_total_goals", 0) > L for g in games), n) for L in TOTAL_LINES},
    }


# ----------------------------------------------------------------------
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


def build(league: str) -> bool:
    cfg = LEAGUE_CFG[league]
    start, points = cfg["season_start"], cfg["points"]
    all_games = load_games(league)
    if league == "KHL":
        khl_goal_sides(all_games)
    all_games = [g for g in all_games if g.get("game_type", "REG") not in ("EXHIB", "PRE")]   # 친선·시범 제외
    season = [g for g in all_games if g["date"] >= start]
    past = [g for g in all_games if g["date"] < start]
    reg = [g for g in season if g.get("game_type", "REG") == "REG"]
    past_reg = [g for g in past if g.get("game_type", "REG") == "REG"]
    today = kst_now().strftime("%Y%m%d")

    print(f"===== {league} 집계: 이번 시즌 {len(season)}경기(정규 {len(reg)}) / 지난 시즌 {len(past)}경기 =====")
    if not reg:
        if today > cfg["fail_after"]:
            print(f"❌ {league} 이번 시즌 정규리그 경기가 0건 — 수집 단계 확인 필요")
            return False
        print("  이번 시즌 데이터 없음 — 집계 건너뜀")
        return True

    out = {
        "meta": {
            "generated_kst": kst_now().strftime("%Y-%m-%d %H:%M"),
            "league": league,
            "season_start": start,
            "games": len(reg),
            "last_game_date": reg[-1]["date"],
            "points_rule": {"reg_win": points[0], "ot_win": points[1], "ot_loss": points[2]},
            "league_avg": league_avgs(reg),
            "notes": "reg_* = 정규시간(60분) 기준 (하키 언오버 사이트 정산 기준) / "
                     "w = 정규승+연장승 / shot_share = 유효슈팅 점유율 / rank_pts = 전체 승점 순위",
        },
        "teams": build_teams(reg, points, today),
        "goalies": build_goalies(season),
        "leaders": build_leaders(reg),
        "last_season": build_teams(past_reg, points, today) if past_reg else {},
        "h2h": build_h2h(past + season),
    }
    for t in out["last_season"].values():   # 지난 시즌은 휴식일 지표가 무의미
        for k in ("days_since_last", "last_was_b2b", "last10_log"):
            t.pop(k, None)
    upload(json.dumps(out, ensure_ascii=False, indent=1), f"analytics/{league}_stats.json", league)
    return True


def main():
    leagues = [a.upper() for a in sys.argv[1:]] or list(LEAGUE_CFG)
    ok = True
    for lg in leagues:
        try:
            ok = build(lg) and ok
        except Exception as e:
            print(f"❌ {lg} 집계 실패: {e}")
            ok = False
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
