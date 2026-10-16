"""V-리그 누적 집계 → analytics/KOVO_stats.json (남자부), analytics/WKOVO_stats.json (여자부)

입력: data/{KOVO|WKOVO}/daily/*.json + data/{KOVO|WKOVO}/historical/*.json (game_id 중복 제거)
출력 구조:
  meta         : 생성 시각, 시즌 시작일, 집계 경기 수, 리그 평균(세트 수 분포·총점·홈 승률)
  teams        : 이번 시즌 정규리그+포스트시즌 팀 성적 — 승점, 세트/점수 득실률, 홈/원정,
                 최근 10경기, 세트당 공격·블로킹·서브·리시브·범실, 세트 수 분포·총점, 휴식일
  last_season  : 지난 시즌 정규리그 팀 성적 (시즌 초 표본 부족 시 기준점)
  cup          : 가장 최근 컵대회 팀 성적 (시즌 전 전력 점검용 — 정규 집계와 분리)
  leaders      : 팀별 득점 상위 6명 + 주전 세터·리베로 (결장 판단용)
  h2h          : 팀 쌍별 최근 맞대결 6경기 (지난 시즌·컵대회 포함, 태그 표기)

세트당 지표는 해당 경기 세트 수로 정규화한다. 최근 N경기 지표는 매 실행 때 일별 파일에서 재계산.
"""
import os
import sys
import json
import glob
import base64
from collections import defaultdict, Counter
from datetime import datetime, timedelta, timezone

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEASON_START = os.getenv("KOVO_SEASON_START", "20260901")   # 2026-27 시즌 (컵대회는 별도 섹션)
LEAGUES = ("KOVO", "WKOVO")
COUNTED = ("REG", "PO", "FINAL")


def kst_now():
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=9)


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
            g["date"] = d.get("date") or os.path.basename(f)[:8]
            uniq[g["game_id"]] = g
    return sorted(uniq.values(), key=lambda x: (x["date"], x.get("start_kst", "")))


def pct(a, b, nd=3):
    return round(a / b, nd) if b else None


def per(a, b, nd=2):
    return round(a / b, nd) if b else None


def days_between(a: str, b: str) -> int:
    return (datetime.strptime(b, "%Y%m%d") - datetime.strptime(a, "%Y%m%d")).days


def match_points(sw: int, sl: int) -> int:
    """V-리그 승점: 3-0·3-1 승 3점, 3-2 승 2점, 2-3 패 1점, 그 외 0점"""
    if sw == 3:
        return 3 if sl <= 1 else 2
    return 1 if sw == 2 else 0


# ----------------------------------------------------------------------
def team_rows(games):
    rows = defaultdict(list)
    for g in games:
        for side in ("home", "away"):
            opp = "away" if side == "home" else "home"
            sw, sl = g[f"{side}_sets"], g[f"{opp}_sets"]
            rows[g[f"{side}_team"]].append({
                "date": g["date"], "type": g.get("game_type"), "is_home": side == "home",
                "opp": g[f"{opp}_team"],
                "sw": sw, "sl": sl, "win": sw > sl,
                "pf": g.get(f"{side}_points", 0), "pa": g.get(f"{opp}_points", 0),
                "sets": g.get("set_count") or (sw + sl),
                "total": g.get("total_points", 0),
                "st": g.get(f"{side}_stats") or {}, "ost": g.get(f"{opp}_stats") or {},
            })
    for team, rs in rows.items():
        prev = None
        for r in rs:
            r["rest"] = days_between(prev, r["date"]) - 1 if prev else None
            prev = r["date"]
    return rows


def split(rs):
    if not rs:
        return {"gp": 0}
    n = len(rs)
    w = sum(r["win"] for r in rs)
    sw, sl = sum(r["sw"] for r in rs), sum(r["sl"] for r in rs)
    pf, pa = sum(r["pf"] for r in rs), sum(r["pa"] for r in rs)
    return {
        "gp": n, "w": w, "l": n - w, "win_pct": pct(w, n),
        "match_pts": sum(match_points(r["sw"], r["sl"]) for r in rs),
        "sets_won": sw, "sets_lost": sl, "set_ratio": per(sw, sl, 3),
        "point_ratio": per(pf, pa, 3),
        "pf_per_set": per(pf, sw + sl, 2), "pa_per_set": per(pa, sw + sl, 2),
    }


def skills(rs):
    """세트당 경기력 지표 (상대 기록 포함)"""
    sets = sum(r["sets"] for r in rs)
    if not sets:
        return {}
    t = Counter()
    o = Counter()
    for r in rs:
        t.update({k: v for k, v in r["st"].items() if isinstance(v, int)})
        o.update({k: v for k, v in r["ost"].items() if isinstance(v, int)})
    return {
        "att_eff": pct(t["att_kill"], t["att"]),              # 공격 성공률
        "opp_att_eff": pct(o["att_kill"], o["att"]),          # 상대 공격 성공률 (수비력)
        "kills_ps": per(t["att_kill"], sets),
        "blocks_ps": per(t["blk_pts"], sets),
        "opp_blocks_ps": per(o["blk_pts"], sets),
        "aces_ps": per(t["aces"], sets),
        "opp_aces_ps": per(o["aces"], sets),
        "rcv_eff": pct(t["rcv_exact"], t["rcv"]),             # 리시브 정확(효율)
        "opp_rcv_eff": pct(o["rcv_exact"], o["rcv"]),         # 우리 서브가 흔든 정도
        "dig_ps": per(t["dig_ok"], sets),
        "errors_ps": per(t["errors"], sets),                  # 자팀 범실
        "opp_errors_ps": per(o["errors"], sets),
    }


def totals(rs):
    if not rs:
        return {}
    n = len(rs)
    sc = Counter(r["sets"] for r in rs)
    tot = sorted(r["total"] for r in rs)
    return {
        "set_count_dist": {str(k): pct(sc.get(k, 0), n) for k in (3, 4, 5)},
        "full_set_rate": pct(sc.get(5, 0), n),
        "avg_total_points": round(sum(tot) / n, 1),
        "median_total_points": tot[n // 2],
        "avg_points_per_set_both": per(sum(tot), sum(r["sets"] for r in rs), 1),
    }


def streak(rs):
    key = rs[-1]["win"]
    n = 0
    for r in reversed(rs):
        if r["win"] == key:
            n += 1
        else:
            break
    return f'{"W" if key else "L"}{n}'


def summarize(rs):
    s = split(rs)
    s.update(skills(rs))
    s.update(totals(rs))
    s.update({
        "home": split([r for r in rs if r["is_home"]]),
        "away": split([r for r in rs if not r["is_home"]]),
        "last10": {**split(rs[-10:]), **{k: v for k, v in skills(rs[-10:]).items()
                                         if k in ("att_eff", "opp_att_eff", "rcv_eff", "errors_ps")}},
        "last10_log": [
            f'{r["date"]} {"vs" if r["is_home"] else "@"} {r["opp"]} {r["sw"]}-{r["sl"]} '
            f'{"W" if r["win"] else "L"} ({r["pf"]}-{r["pa"]})' + ("" if r["type"] == "REG" else f' [{r["type"]}]')
            for r in rs[-10:]
        ],
        "streak": streak(rs),
        "last_game_date": rs[-1]["date"],
        "last_rest_days": rs[-1]["rest"],
        "short_rest": split([r for r in rs if r["rest"] is not None and r["rest"] <= 1]),
    })
    return s


def build_teams(games):
    out = {t: summarize(rs) for t, rs in team_rows(games).items()}
    return dict(sorted(out.items(), key=lambda kv: (-(kv[1].get("match_pts") or 0),
                                                    -(kv[1].get("w") or 0),
                                                    -(kv[1].get("set_ratio") or 0))))


def build_leaders(games):
    agg = defaultdict(lambda: Counter())
    meta = {}
    last_date = {}
    for g in games:
        for side in ("home", "away"):
            team = g[f"{side}_team"]
            last_date[team] = g["date"]
            for p in g.get(f"{side}_players", []):
                if not p.get("sets"):
                    continue
                key = (team, p.get("player_id") or p.get("name"))
                meta[key] = {"name": p.get("name"), "pos": p.get("pos"), "last_played": g["date"]}
                a = agg[key]
                a["gp"] += 1
                for k in ("sets", "pts", "att", "att_kill", "blk_pts", "aces", "rcv", "rcv_exact",
                          "dig_ok", "set_att", "set_exact", "errors"):
                    a[k] += p.get(k, 0) or 0
    by_team = defaultdict(list)
    for key, a in agg.items():
        team = key[0]
        m = meta[key]
        by_team[team].append({
            "name": m["name"], "pos": m["pos"], "gp": a["gp"], "sets": a["sets"],
            "pts_ps": per(a["pts"], a["sets"]), "pts_pg": per(a["pts"], a["gp"], 1),
            "att_eff": pct(a["att_kill"], a["att"]),
            "blk_ps": per(a["blk_pts"], a["sets"]), "aces_ps": per(a["aces"], a["sets"]),
            "rcv_eff": pct(a["rcv_exact"], a["rcv"]) if a["rcv"] >= 20 else None,
            "set_exact_ps": per(a["set_exact"], a["sets"]) if m["pos"] == "S" else None,
            "dig_ps": per(a["dig_ok"], a["sets"]) if m["pos"] == "L" else None,
            "last_played": m["last_played"],
            "missed_last_game": m["last_played"] != last_date.get(team),
            "_pts": a["pts"],
        })
    out = {}
    for team, rows in by_team.items():
        rows.sort(key=lambda x: -x["_pts"])
        top = rows[:6]
        # 주전 세터·리베로는 득점 순위와 무관하게 포함 (출전 세트 최다)
        for pos in ("S", "L"):
            cand = sorted([r for r in rows if r["pos"] == pos], key=lambda x: -x["sets"])
            if cand and cand[0] not in top:
                top.append(cand[0])
        for r in top:
            r.pop("_pts", None)
            for k in [k for k, v in r.items() if v is None]:
                r.pop(k)
        out[team] = top
    return out


def build_h2h(games):
    pairs = defaultdict(list)
    for g in games:
        key = " vs ".join(sorted([g["home_team"], g["away_team"]]))
        pairs[key].append(
            f'{g["date"]} {g["away_team"]} {g["away_sets"]}-{g["home_sets"]} {g["home_team"]}'
            f' ({g.get("away_points", 0)}-{g.get("home_points", 0)})'
            + ("" if g.get("game_type") == "REG" else f' [{g.get("game_type")}]'))
    return {k: v[-6:] for k, v in pairs.items()}


def league_avg(games):
    if not games:
        return {}
    n = len(games)
    sc = Counter(g.get("set_count") for g in games)
    return {
        "games": n,
        "home_win_pct": pct(sum(g["home_sets"] > g["away_sets"] for g in games), n),
        "set_count_dist": {str(k): pct(sc.get(k, 0), n) for k in (3, 4, 5)},
        "avg_total_points": round(sum(g["total_points"] for g in games) / n, 1),
        "avg_total_by_sets": {str(k): round(sum(g["total_points"] for g in games if g.get("set_count") == k)
                                            / sc[k], 1) for k in (3, 4, 5) if sc.get(k)},
        "set_score_dist": dict(Counter(
            "-".join(map(str, sorted([g["home_sets"], g["away_sets"]], reverse=True))) for g in games)),
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
    r = requests.get(url, headers=h)
    payload = {"message": f"[{league}] 통계 집계 업데이트",
               "content": base64.b64encode(content.encode()).decode(), "branch": "main"}
    if r.status_code == 200:
        payload["sha"] = r.json()["sha"]
    r = requests.put(url, headers=h, json=payload)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"업로드 실패 {r.status_code}: {r.text[:200]}")
    print(f"  📁 {path} 업로드 완료")


def build(league: str) -> bool:
    games = load_games(league)
    if not games:
        print(f"  [{league}] 데이터 없음 — 건너뜀")
        return False
    past_start = f"{int(SEASON_START[:4]) - 1}{SEASON_START[4:]}"
    league_games = [g for g in games if g.get("game_type") in COUNTED]
    season = [g for g in league_games if g["date"] >= SEASON_START]
    last_all = [g for g in league_games if past_start <= g["date"] < SEASON_START]
    last_reg = [g for g in last_all if g["game_type"] == "REG"]
    cups = [g for g in games if g.get("game_type") == "CUP"]
    cup_year = cups[-1]["date"][:4] if cups else None
    cup = [g for g in cups if g["date"][:4] == cup_year]

    print(f"===== {league} 집계: 이번 시즌 {len(season)}경기 / 지난 시즌 {len(last_all)}경기 "
          f"(정규 {len(last_reg)}) / {cup_year} 컵 {len(cup)}경기 =====")

    out = {
        "meta": {
            "league": league,
            "generated_kst": kst_now().strftime("%Y-%m-%d %H:%M"),
            "season_start": SEASON_START,
            "games": len(season),
            "last_game_date": games[-1]["date"],
            "league_avg": league_avg(season),
            "league_avg_last_season": league_avg(last_reg),
            "notes": "match_pts = V리그 승점(3-0·3-1 승 3, 3-2 승 2, 2-3 패 1) / *_ps = 세트당 "
                     "/ att_eff = 공격 성공률, rcv_eff = 리시브 정확 비율 / opp_* = 상대 기록 "
                     "/ last_rest_days 0 = 연일 경기 / teams·last_season은 컵대회 제외",
        },
        "teams": build_teams(season),
        "last_season": build_teams(last_reg),
        "last_season_postseason": [
            f'{g["date"]} {g["away_team"]} {g["away_sets"]}-{g["home_sets"]} {g["home_team"]} [{g["game_type"]}]'
            for g in last_all if g["game_type"] != "REG"],
        "cup": {"year": cup_year, "teams": build_teams(cup), "league_avg": league_avg(cup)} if cup else {},
        # 이번 시즌 기록이 쌓이기 전엔 컵대회 기준, 그다음은 이번 시즌 기준
        "leaders": build_leaders(season if len(season) >= 6 else cup or last_reg),
        "leaders_basis": "season" if len(season) >= 6 else ("cup" if cup else "last_season"),
        "leaders_last_season": build_leaders(last_reg),
        "h2h": build_h2h(games),
    }
    upload(json.dumps(out, ensure_ascii=False, indent=1), f"analytics/{league}_stats.json", league)
    return True


def main():
    built = [build(lg) for lg in LEAGUES]
    if not any(built) and kst_now().strftime("%Y%m%d") > "20261101":
        print("❌ V-리그 데이터가 0건입니다 — 수집 단계 확인 필요")
        sys.exit(1)


if __name__ == "__main__":
    main()
