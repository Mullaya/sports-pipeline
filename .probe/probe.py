import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from bleague_official import BLeagueBox
b = BLeagueBox()
for date in ["20261116", "20261115", "20251018", "20260412"]:
    print(date, "keys", b.keys_for_date(date))
    for o in b.games_on(date):
        hp = [p for p in o["home_players"] if not p["dnp"]]
        print("  ", o["key"], o["home_score"], o["away_score"], len(o["home_players"]), len(hp), hp[0] if hp else None)
