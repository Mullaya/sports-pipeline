"""픽 로그 자동 채점.

사용: python analytics/grade_picks.py [data/picks/picks_log.json] [data 경로]

- result가 비어 있는 픽만 일별 결과 파일로 채점하고, 채점 결과를 로그에 다시 기록한다.
- 자동 채점 리그: MLB·NBA·NHL·KBL. 그 외(NPB·KBO 등)는 "수동 채점 필요"로 목록만 출력 —
  result/actual을 직접 채워 넣으면 요약에 포함된다.
- 팀 식별자: MLB는 풀네임(예: "Milwaukee Brewers"), NBA·NHL은 파이프라인 약어(예: "UTAH", "EDM"),
  KBL은 영문(예: "Seoul SK")·한글 풀네임("서울 SK")·약칭("SK") 모두 허용.
- HDP의 line은 side 팀 기준 핸디캡(+1.5, -4.5 등).
- 정산 기준: NHL은 정규시간(ML3W·TOTAL·HDP 모두), MLB·NBA·KBL은 연장 포함.
- ML3W(하키 3way 승): 정규시간 무승부면 LOSS.
- F5_TOTAL: MLB 1~5회 합계(inning_scores). line이 없으면 채점하지 않는다.
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
    "KBL": "KBL/daily/{d} kbl.json",
}

# KBL: 영문·한글 풀네임 → 파이프라인 약칭(home_short/away_short)
KBL_ALIAS = {
    "seoul sk": "SK", "서울 sk": "SK",
    "seoul samsung": "삼성", "서울 삼성": "삼성",
    "busan kcc": "KCC", "부산 kcc": "KCC",
    "suwon kt": "KT", "수원 kt": "KT",
    "anyang jung kwan jang": "정관장", "anyang jungkwanjang": "정관장", "anyang kgc": "정관장", "안양 정관장": "정관장",
    "ulsan hyundai mobis": "현대모비스", "울산 현대모비스": "현대모비스",
    "wonju db": "DB", "원주 db": "DB",
    "goyang sono": "고양소노", "고양 소노": "고양소노",
    "daegu kogas": "한국가스공사", "daegu korea gas corporation": "한국가스공사", "대구 한국가스공사": "한국가스공사",
    "changwon lg": "LG", "창원 lg": "LG",
}


def canon(league, name):
    if name is None:
        return None
    if league == "KBL":
        return KBL_ALIAS.get(name.strip().lower(), name.strip())
    return name


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
    if league == "KBL":
        return g["away_short"], g["home_short"], g["away_score"], g["home_score"]
    return g["away_abbrev"], g["home_abbrev"], g["away_score"], g["home_score"]


def find_game(league, games, away, home):
    away, home = canon(league, away), canon(league, home)
    for g in games:
        if g.get("home_score") is None:
            continue
        a, h, _, _ = scores(league, g)
        if (a, h) == (away, home):
            return g, False
        if (a, h) == (home, away):
            return g, True
    return None, False


def total_result(tot, line, side):
    if tot == line:
        return "PUSH"
    over = tot > line
    return "WIN" if (over if side == "OVER" else not over) else "LOSS"


def grade(p, g):
    league = p["league"]
    a, h, sa, sh = scores(league, g)
    actual = f"{a} {sa} @ {h} {sh}" + (" (reg)" if league == "NHL" else "")
    m, line = p["market"], p.get("line")
    side = canon(league, p["side"])
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
        return total_result(tot, line, side), f"{actual} 합계 {tot}"
    if m == "F5_TOTAL" and league == "MLB":
        inn = [i for i in g.get("inning_scores", []) if i["inning"] <= 5]
        if len(inn) < 5:
            return None, actual
        tot = sum(i["home"] + i["away"] for i in inn)
        return total_result(tot, line, side), f"{actual} 5회 합계 {tot}"
    return None, actual


def main():
    with open(LOG, encoding="utf-8") as f:
        log = json.load(f)
    picks = log["picks"]
    by_id = {p["id"]: p for p in picks}
    newly, manual = 0, []
    for p in picks:
        if p.get("result"):
            continue
        if p["league"] not in DAILY or (p["market"] == "F5_TOTAL" and p["league"] != "MLB"):
            manual.append(p)
            continue
        if p["market"] in ("TOTAL", "F5_TOTAL", "HDP") and p.get("line") is None:
            print(f"[경고] line 없음 — 채점 불가: {p['id']}")
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
    if manual:
        print(f"[수동 채점 필요 {len(manual)}건] result/actual 직접 입력")
        for p in manual:
            print(f"  {p['id']} {p['league']} {p['away']} @ {p['home']} {p['market']} {p['side']} {p.get('line')}")
    pend = [p["id"] for p in picks if not p.get("result") and p not in manual
            and not (p["market"] in ("TOTAL", "F5_TOTAL", "HDP") and p.get("line") is None)]
    if pend:
        print(f"[미채점 {len(pend)}건] 결과 파일 대기: {', '.join(pend)}")


if __name__ == "__main__":
    main()
