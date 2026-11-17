import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from wkbl_official import WKBLBox, season_gu
b = WKBLBox()
g = [{"home_score": 68, "away_score": 67}]
print("fill", b.fill("20261116", g), g[0].get("official_key"), len(g[0].get("home_players", [])), g[0].get("home_players", [None])[0])
print("month 046 202601", b.month_games("046", "202601")[:5], len(b.month_games("046", "202601")))
gt, no = b.month_games("046", "202601")[0]
print("date", b.game_date("046", gt, no))
bx = b.boxscore("046", gt, no); print([(t, s, len(p)) for t, s, p in bx])
