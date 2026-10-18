import sys,collections
sys.path.insert(0,'.')
from datetime import datetime,timezone
from collectors.flashscore_hockey_collector import FlashscoreHockeyCollector
for lg in ("DEL","CZE","KHL"):
  for y in (2025,2026):
    c=FlashscoreHockeyCollector(lg)
    recs=c.season_matches(y,y+1)
    fin=[r for r in recs.values() if r.get("AB")=="3"]
    mon=collections.Counter(datetime.fromtimestamp(int(r["AD"]),timezone.utc).strftime("%Y%m") for r in fin)
    print(lg,y,"total",len(recs),"finished",len(fin),dict(sorted(mon.items())))
# rerun
