"""KBL 수집기 실데이터 테스트 (임시)"""
import sys, os, json
from collections import Counter
sys.path.insert(0, os.getcwd())
from collectors.kbl_collector import KBLCollector, API

c = KBLCollector(sleep=0.2)

# 1) 시즌 전체 목록 → 날짜·상태 분포
res = c._get(API, {"fields": "basic", "categoryId": "kbl",
                   "fromDate": "2025-09-01", "toDate": "2026-06-10", "size": 1000})
gs = res.get("games", [])
print("season list", len(gs), "total count", res.get("gameTotalCount"))
print("status", Counter(g["statusCode"] for g in gs))
print("months", sorted(Counter(g["gameDate"][:7] for g in gs).items()))

# 2) 월별 첫 경기 roundCode 확인 + 샘플 수집
seen = {}
for g in gs:
    m = g["gameDate"][:7]
    if m in seen:
        continue
    info = c._get(f"{API}/{g['gameId']}").get("game", {})
    seen[m] = info.get("roundCode")
    print(m, g["gameDate"], info.get("roundCode"), info.get("seriesGameNo"), info.get("homeTeamName"), info.get("awayTeamName"))

# 3) 연장 경기 탐색 + 수집기 검증
for d in ("20250920", "20251003", "20260325", "20260513"):
    data = c.collect_daily(d)
    print("\n==", d, len(data["games"]))
    for x in data["games"]:
        hp = sum(p["pts"] for p in x["home_players"])
        ap = sum(p["pts"] for p in x["away_players"])
        print(f"  {x['game_type']:6} {x['home_team']} {x['home_score']}-{x['away_score']} {x['away_team']} "
              f"OT={x['overtime']} reg={x['reg_home_score']}-{x['reg_away_score']} q={x['quarter_scores']} "
              f"player_sum={hp}/{ap} fga={x['home_stats'].get('fga')} n_pl={len(x['home_players'])}")

ot = []
for g in gs:
    if g["statusCode"] == "RESULT" and len(ot) < 1:
        pass
# 연장 경기 하나 찾아서 출력 (쿼터 배열 5번째 확인)
for g in gs[200:400]:
    info = c._get(f"{API}/{g['gameId']}").get("game", {})
    hq, aq = info.get("homeTeamScoreByQuarter"), info.get("awayTeamScoreByQuarter")
    if hq and sum(hq[:4]) != info.get("homeTeamScore"):
        print("\nOT game", g["gameDate"], hq, aq, info.get("homeTeamScore"), info.get("awayTeamScore"))
        x = c._build_game(g["gameId"])
        print(json.dumps({k: x[k] for k in ("overtime", "reg_home_score", "reg_away_score", "quarter_scores", "home_score", "away_score")}, ensure_ascii=False))
        break
print("\nsample game json:")
d = c.collect_daily("20251101")
print(json.dumps(d["games"][0], ensure_ascii=False)[:2500])
