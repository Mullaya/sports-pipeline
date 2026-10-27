"""픽 로그 자동 채점.

사용: python analytics/grade_picks.py [data/picks/picks_log.json] [data 경로]

- result가 비어 있는 픽만 일별 결과 파일로 채점하고, 채점 결과를 로그에 다시 기록한다.
- 팀 식별자: MLB는 풀네임(예: "Milwaukee Brewers"), NBA·NHL은 파이프라인 약어(예: "UTAH", "EDM").
- HDP의 line은 side 팀 기준 핸디캡(+1.5, -4.5 등).
- 정산 기준: NHL은 정규시간(ML3W·TOTAL·HDP 모두), MLB·NBA는 연장 포함.
- ML3W(하키 3way 승): 정규시간 무승부면 LOSS.
"""
import json
import os
import sys
from collections import defaultdict

LOG = sys.argv[1] if len(sys.argv) > 1 else "data/picks/picks_log.json"
DATA = sys.argv[2] if len(sys.argv) > 2 else "data"

DAILY = {
    "MLB": "MLB/daily/{d}.json",
    "NBA": "NBA/daily/{d} nba.json",
    "NHL": "NHL/daily/{d} nhl.json",
}


def load_games(league, date):
    path = os.path.join(DATA, DAILY[league].format(d=date))
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("games", [])


def scores(league, g):
    """(away, home, away_score, home_score) — NHL은 정규시간 스코어."""
    if league == "MLB":
        return g["away_team"], g["home_team"], g["away_score"], g["home_score"]
    if league == "NHL":
        return g["away_abbrev"], g["home_abbrev"], g["reg_away_score"], g["reg_home_score"]
    return g["away_abbrev"], g["home_abbrev"], g["away_score"], g["home_score"]


def find_game(league, games, away, home):
    for g in games:
        if g.get("home_score") is None:
            continue
        a, h, _, _ = scores(league, g)
        if (a, h) == (away, home):
            return g, False
        if (a, h) == (home, away):
            return g, True
    return None, False


def grade(p, g):
    league = p["league"]
    a, h, sa, sh = scores(league, g)
    actual = f"{a} {sa} @ {h} {sh}" + (" (reg)" if league == "NHL" else "")
    m, side, line = p["market"], p["side"], p.get("line")
    if m in ("ML", "ML3W"):
        if sa == sh:
            return "LOSS", actual  # NHL 정규시간 무승부
        winner = a if sa > sh else h
        return ("WIN" if winner == side else "LOSS"), actual
    if m == "HDP":
        mine, opp = (sa, sh) if side == a else (sh, sa)
        diff = mine + line - opp
        return ("WIN" if diff > 0 else "PUSH" if diff == 0 else "LOSS"), actual
    if m == "TOTAL":
        tot = sa + sh
        if tot == line:
            return "PUSH", f"{actual} 합계 {tot}"
        over = tot > line
        ok = over if side == "OVER" else not over
        return ("WIN" if ok else "LOSS"), f"{actual} 합계 {tot}"
    return None, actual


def main():
    with open(LOG, encoding="utf-8") as f:
        log = json.load(f)
    picks = log["picks"]
    by_id = {p["id"]: p for p in picks}
    newly = 0
    for p in picks:
        if p.get("result") or p["league"] not in DAILY:
            continue
        games = load_games(p["league"], p["date"])
        if games is None:
            continue
        g, swapped = find_game(p["league"], games, p["away"], p["home"])
        if g is None:
            print(f"[경고] 경기 없음: {p['id']} {p['away']} @ {p['home']}")
            continue
        if swapped:
            print(f"[경고] 홈/원정 뒤바뀜: {p['id']} — 기록 기준으로 채점")
        res, actual = grade(p, g)
        if res:
            p["result"], p["actual"] = res, actual
            newly += 1
            print(f"채점 {p['id']} {p['market']} {p['side']} {p.get('line')} → {res} ({actual})")

    for par in log.get("parlays", []):
        if par.get("result"):
            continue
        rs = [by_id[i].get("result") for i in par["legs"] if i in by_id]
        if "LOSS" in rs:
            par["result"] = "LOSS"
        elif rs and all(r in ("WIN", "PUSH") for r in rs):
            par["result"] = "WIN"

    with open(LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    print(f"\n신규 채점 {newly}건")

    # 요약 (철회·미채점·PUSH 제외)
    def summarize(key):
        agg = defaultdict(lambda: [0, 0])
        for p in picks:
            if p.get("result") in ("WIN", "LOSS"):
                agg[key(p)][0 if p["result"] == "WIN" else 1] += 1
        for k in sorted(agg, key=str):
            w, l = agg[k]
            print(f"  {k}: {w}승 {l}패 ({w / (w + l) * 100:.0f}%)")

    for title, key in [("별점별", lambda p: f"★{p['stars']}"), ("리그별", lambda p: p["league"]),
                       ("마켓별", lambda p: p["market"]), ("날짜별", lambda p: p["date"])]:
        print(f"[{title}]")
        summarize(key)
    pend = [p["id"] for p in picks if not p.get("result")]
    if pend:
        print(f"[미채점 {len(pend)}건] 결과 파일 대기")


if __name__ == "__main__":
    main()
