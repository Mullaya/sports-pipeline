import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ThreadPoolExecutor
from htg import HockeyTechGoalies
h = HockeyTechGoalies("OHL", sleep=0.1)
h.season_ids("20261101")
sids = [s["season_id"] for s in h._seasons if s["season_name"][:4] in ("2024","2025","2026") and ("Regular" in s["season_name"] or "Playoffs" in s["season_name"])]
games = []
for sid in sids:
    for g in h.schedule(sid):
        if str(g.get("final")) == "1" or g.get("status") == "4":
            games.append((sid, g))
print("seasons", sids, "games", len(games), file=sys.stderr)
def work(x):
    sid, g = x
    try:
        r = h.summary(g["game_id"])
    except Exception as e:
        return None
    return {"date": g["date_played"].replace("-", ""), "home": h._teams.get(str(g["home_team"])), "away": h._teams.get(str(g["visiting_team"])),
            "gid": g["game_id"], "h": r.get("home"), "a": r.get("away")}
with ThreadPoolExecutor(6) as ex:
    out = [r for r in ex.map(work, games) if r]
print("N", len(out))
print("JSON" + json.dumps(out, ensure_ascii=False, separators=(",", ":")))
