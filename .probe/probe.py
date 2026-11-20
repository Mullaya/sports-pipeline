import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fhc import FlashscoreHockeyCollector
c = FlashscoreHockeyCollector("OHL")
d = c.collect_daily("20261115")
print("games", len(d["games"]))
for g in d["games"][:3]:
    print(json.dumps({k: v for k, v in g.items() if not isinstance(v, (list, dict))}, ensure_ascii=False)[:500])
    print(" goalies", str(g.get("home_goalies") or g.get("goalies"))[:200])
