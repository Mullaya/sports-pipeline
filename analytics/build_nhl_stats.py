"""NHL 누적 집계 → analytics/NHL_stats.json

입력: data/NHL/daily/*.json + data/NHL/historical/*.json (시즌 구분은 날짜 기준)
출력 구조:
  meta     : 생성 시각, 시즌 시작일, 집계 경기 수
  teams    : 팀별 시즌 성적, 홈/원정 분리, 최근 10경기, PP/PK, PDO, 정규시간 무승부율, 언오버 적중률
  goalies  : 골리별 SV%/GAA, 최근 5선발 SV%, 홈/원정 SV%, 마지막 선발일(백투백 판단)
  h2h      : 팀 쌍별 최근 맞대결 5경기 (지난 시즌 포함)

모든 최근 N경기 지표는 매 실행 때 일별 파일에서 재계산한다 (MLB last5 스테일 문제 재발 방지).
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
SEASON_START = os.getenv("NHL_SEASON_START", "20260901")   # 2026-27 시즌
OUT_PATH = "analytics/NHL_stats.json"
TOTAL_LINES = (4.5, 5.5, 6.5)


def load_games() -> list:
    """daily + historical 전체를 읽어 game_id로 중복 제거 (시즌 구분은 날짜로)"""
    games = []
    files = glob.glob(os.path.join(ROOT, "data", "NHL", "historical", "*.json")) + \
        glob.glob(os.path.join(ROOT, "data", "NHL", "daily", "*.json"))
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception as e:
            print(f"  ⚠️ {f} 읽기 실패: {e}")
            continue
        for g in d.get("games", []):
            g["date"] = d.get("date") or os.path.basename(f)[:8]
            games.append(g)
    # 같은 경기 중복 제거 (daily/historical 겹침)
    uniq = {}
    for g in games:
        uniq[g["game_id"]] = g
    return sorted(uniq.values(), key=lambda x: (x["date"], x.get("start_utc", "")))


def r3(x):
    return round(x, 3) if x is not None else None


def pct(a, b):
    return round(a / b, 3) if b else None


# ----------------------------------------------------------------------
def team_result(g, side):
    """W / L / OTL 와 정규시간 결과(RW/RL/RD)"""
    me = g[f"{side}_score"]
    op = g["away_score" if side == "home" else "home_score"]
    if me > op:
        res = "W"
    elif g.get("end_type") in ("OT", "SO"):
        res = "OTL"
    else:
        res = "L"
    reg_me = g.get(f"reg_{side}_score", me)
    reg_op = g.get("reg_away_score" if side == "home" else "reg_home_score", op)
    reg = "RW" if reg_me > reg_op else ("RL" if reg_me < reg_op else "RD")
    return res, reg


def build_teams(games):
    rows = defaultdict(list)
    for g in games:
        for side in ("home", "away"):
            opp = "away" if side == "home" else "home"
            res, reg = team_result(g, side)
            st, ost = g.get(f"{side}_stats", {}), g.get(f"{opp}_stats", {})
            gk_sa = sum(x.get("shots_against") or 0 for x in g.get(f"{side}_goalies", []))
            gk_ga = sum(x.get("goals_against") or 0 for x in g.get(f"{side}_goalies", []))
            rows[g[f"{side}_abbrev"]].append({
                "date": g["date"],
                "name": g[f"{side}_team"],
                "is_home": side == "home",
                "opp": g[f"{opp}_abbrev"],
                "gf": g[f"{side}_score"],
                "ga": g[f"{opp}_score"],
                "res": res,
                "reg": reg,
                "end": g.get("end_type", "REG"),
                "total": g.get("total_goals", 0),
                "reg_total": g.get("reg_total_goals", g.get("total_goals", 0)),
                "sf": st.get("shots") or 0,
                "sa": ost.get("shots") or 0,
                "ppg": st.get("pp_goals", 0), "ppo": st.get("pp_opps", 0),
                "ppga": ost.get("pp_goals", 0), "pko": ost.get("pp_opps", 0),
                # SV%는 골리 기록 기준(빈 골문 실점 제외)
                "gk_sa": gk_sa, "gk_ga": gk_ga,
            })

    teams = {}
    for ab, rs in rows.items():
        teams[ab] = summarize(rs)
        teams[ab]["name"] = rs[-1]["name"]
    return teams


def split(rs):
    n = len(rs)
    if not n:
        return {"gp": 0}
    w = sum(r["res"] == "W" for r in rs)
    l = sum(r["res"] == "L" for r in rs)
    otl = sum(r["res"] == "OTL" for r in rs)
    gf, ga = sum(r["gf"] for r in rs), sum(r["ga"] for r in rs)
    return {
        "gp": n, "w": w, "l": l, "otl": otl, "pts": 2 * w + otl,
        "reg_w": sum(r["reg"] == "RW" for r in rs),
        "reg_d": sum(r["reg"] == "RD" for r in rs),
        "reg_l": sum(r["reg"] == "RL" for r in rs),
        "gf_pg": round(gf / n, 2), "ga_pg": round(ga / n, 2),
        "sf_pg": round(sum(r["sf"] for r in rs) / n, 1),
        "sa_pg": round(sum(r["sa"] for r in rs) / n, 1),
    }


def summarize(rs):
    s = split(rs)
    sf, sa = sum(r["sf"] for r in rs), sum(r["sa"] for r in rs)
    gf = sum(r["gf"] for r in rs)
    gk_sa, gk_ga = sum(r["gk_sa"] for r in rs), sum(r["gk_ga"] for r in rs)
    sh = pct(gf, sf)
    sv = pct(gk_sa - gk_ga, gk_sa)
    ppg, ppo = sum(r["ppg"] for r in rs), sum(r["ppo"] for r in rs)
    ppga, pko = sum(r["ppga"] for r in rs), sum(r["pko"] for r in rs)
    n = len(rs)

    s.update({
        "shot_share": pct(sf, sf + sa),                 # 슈팅 점유율 (Corsi 대용)
        "sh_pct": sh, "sv_pct": sv,
        "pdo": round((sh + sv) * 100, 1) if sh is not None and sv is not None else None,
        "pp_pct": pct(ppg, ppo), "pk_pct": round(1 - ppga / pko, 3) if pko else None,
        "reg_draw_rate": pct(s["reg_d"], n),            # 3-way 무승부(연장행) 비율
        "avg_total": round(sum(r["total"] for r in rs) / n, 2),
        "avg_reg_total": round(sum(r["reg_total"] for r in rs) / n, 2),
        "over_rate_reg": {str(L): pct(sum(r["reg_total"] > L for r in rs), n) for L in TOTAL_LINES},
        "home": split([r for r in rs if r["is_home"]]),
        "away": split([r for r in rs if not r["is_home"]]),
        "last10": split(rs[-10:]),
        "last10_log": [
            f'{r["date"]} {"vs" if r["is_home"] else "@"} {r["opp"]} {r["gf"]}-{r["ga"]} {r["res"]}'
            + (f'({r["end"]})' if r["end"] != "REG" else "")
            for r in rs[-10:]
        ],
        "streak": streak(rs),
        "last_game_date": rs[-1]["date"],
    })
    return s


def streak(rs):
    if not rs:
        return ""
    key = "W" if rs[-1]["res"] == "W" else "L"
    n = 0
    for r in reversed(rs):
        if (r["res"] == "W") == (key == "W"):
            n += 1
        else:
            break
    return f"{key}{n}"


# ----------------------------------------------------------------------
def build_goalies(games):
    log = defaultdict(list)
    for g in games:
        for side in ("home", "away"):
            for gk in g.get(f"{side}_goalies", []):
                pid = gk.get("player_id") or gk.get("name")
                log[pid].append({**gk, "date": g["date"], "team": g[f"{side}_abbrev"],
                                 "is_home": side == "home",
                                 "opp": g["away_abbrev" if side == "home" else "home_abbrev"]})
    out = {}
    for pid, rs in log.items():
        starts = [r for r in rs if r.get("starter")]
        out[str(pid)] = {
            "name": rs[-1]["name"],
            "team": rs[-1]["team"],
            **gk_line(rs),
            "starts": len(starts),
            "w": sum(r.get("decision") == "W" for r in rs),
            "l": sum(r.get("decision") == "L" for r in rs),
            "o": sum(r.get("decision") == "O" for r in rs),
            "last5_starts": gk_line(starts[-5:]),
            "home": gk_line([r for r in rs if r["is_home"]]),
            "away": gk_line([r for r in rs if not r["is_home"]]),
            "last_start_date": starts[-1]["date"] if starts else None,
            "log": [f'{r["date"]} {"vs" if r["is_home"] else "@"} {r["opp"]} '
                    f'{r["saves"]}/{r["shots_against"]} {r.get("decision","")}' for r in rs[-5:]],
        }
    return out


def gk_line(rs):
    sa = sum(r.get("shots_against") or 0 for r in rs)
    ga = sum(r.get("goals_against") or 0 for r in rs)
    toi = sum(r.get("toi") or 0 for r in rs)
    return {"gp": len(rs), "sv_pct": pct(sa - ga, sa),
            "gaa": round(ga * 60 / toi, 2) if toi else None}


# ----------------------------------------------------------------------
def build_h2h(games):
    pairs = defaultdict(list)
    for g in games:
        key = "-".join(sorted([g["home_abbrev"], g["away_abbrev"]]))
        pairs[key].append(f'{g["date"]} {g["away_abbrev"]} {g["away_score"]}-{g["home_score"]} '
                          f'{g["home_abbrev"]}' + (f' ({g["end_type"]})' if g.get("end_type") != "REG" else ""))
    return {k: v[-5:] for k, v in pairs.items()}


def build_leaders(games, season_teams):
    """팀별 포인트 상위 6명 — 결장자 영향도 판단용"""
    agg = defaultdict(lambda: {"gp": 0, "g": 0, "a": 0, "pts": 0, "toi": 0.0})
    for g in games:
        for side in ("home", "away"):
            team = g[f"{side}_abbrev"]
            for s in g.get(f"{side}_skaters", []):
                k = (team, s.get("player_id") or s.get("name"))
                a = agg[k]
                a.update(name=s.get("name"), pos=s.get("pos"))
                a["gp"] += 1
                a["g"] += s.get("g", 0)
                a["a"] += s.get("a", 0)
                a["pts"] += s.get("pts", 0)
                a["toi"] += s.get("toi", 0)
    by_team = defaultdict(list)
    for (team, _), a in agg.items():
        a["toi_pg"] = round(a.pop("toi") / a["gp"], 1) if a["gp"] else 0
        by_team[team].append(a)
    return {t: sorted(v, key=lambda x: (-x["pts"], -x["toi_pg"]))[:6]
            for t, v in by_team.items() if t in season_teams}


# ----------------------------------------------------------------------
def upload(content: str, path: str):
    token, repo = os.getenv("GITHUB_TOKEN"), os.getenv("GITHUB_REPOSITORY")
    if not token or not repo:
        local = os.path.join(ROOT, path)
        with open(local, "w", encoding="utf-8") as fh:
            fh.write(content)
        print(f"  💾 로컬 저장: {path}")
        return
    h = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    r = requests.get(url, headers=h)
    payload = {"message": "[NHL] 통계 집계 업데이트",
               "content": base64.b64encode(content.encode()).decode(), "branch": "main"}
    if r.status_code == 200:
        payload["sha"] = r.json()["sha"]
    r = requests.put(url, headers=h, json=payload)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"업로드 실패 {r.status_code}: {r.text[:200]}")
    print(f"  📁 {path} 업로드 완료")


def main():
    all_games = load_games()
    season = [g for g in all_games if g["date"] >= SEASON_START]
    past = [g for g in all_games if g["date"] < SEASON_START]

    print(f"===== NHL 집계: 이번 시즌 {len(season)}경기 / 지난 시즌 {len(past)}경기 =====")
    if not season:
        # silent fail 방지: 시즌 중인데 경기 0이면 실패로 표시
        kst = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=9)
        if kst.strftime("%Y%m%d") > "20261005":
            print("❌ 이번 시즌 경기 데이터가 0건입니다 — 수집 단계 확인 필요")
            sys.exit(1)
        print("  이번 시즌 데이터 없음 — 집계 건너뜀")
        return

    teams = build_teams(season)
    out = {
        "meta": {
            "generated_kst": (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M"),
            "season_start": SEASON_START,
            "games": len(season),
            "last_game_date": season[-1]["date"],
            "notes": "reg_* = 정규시간(60분) 기준 / sv_pct 빈골문 실점 제외 / shot_share = 유효슈팅 점유율",
        },
        "teams": teams,
        "goalies": build_goalies(season),
        "leaders": build_leaders(season, teams),
        "h2h": build_h2h(past + season),
    }
    upload(json.dumps(out, ensure_ascii=False, indent=1), OUT_PATH)


if __name__ == "__main__":
    main()
