"""KBL 누락 경기 탐색 (임시)"""
import sys, os, glob, json
sys.path.insert(0, os.getcwd())
from collectors.kbl_collector import KBLCollector, API

have = set()
for f in glob.glob("data/KBL/*/*.json"):
    for g in json.load(open(f, encoding="utf-8"))["games"]:
        have.add(g["game_id"])

c = KBLCollector(sleep=0.2)
gs = []
for fr, to in (("2025-09-01", "2026-06-10"), ("2026-09-01", "2026-10-14")):
    gs += c._get(API, {"fields": "basic", "categoryId": "kbl", "fromDate": fr, "toDate": to, "size": 1000})["games"]
miss = [g for g in gs if g["statusCode"] == "RESULT" and g["gameId"] not in have]
print("missing", len(miss))
for g in miss:
    print(g["gameDate"], g["gameId"], g["homeTeamName"], g["awayTeamName"], g.get("cancel"), g.get("suspended"))
    try:
        x = c._build_game(g["gameId"])
        print("   build ok", x["game_type"], x["home_score"], x["away_score"])
    except Exception as e:
        print("   build ERR", repr(e)[:300])
