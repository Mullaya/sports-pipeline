import sys,re,collections
sys.path.insert(0,'.')
from datetime import datetime,timezone
import collectors.flashscore_hockey_collector as F
from collectors.flashscore_hockey_collector import FlashscoreHockeyCollector, _records
for lg in ("DEL","CZE"):
  for y in (2025,2026):
    c=FlashscoreHockeyCollector(lg)
    html=c._get(f"{F.SITE}/{c.cfg['path']}-{y}-{y+1}/results/")
    feeds=re.findall(r'initialFeeds\["([^"]+)"\]\s*=\s*\{\s*data:\s*`(.*?)`',html,re.S)
    for name,data in feeds:
        rs=_records(data); fin=[r for r in rs if r.get("AB")=="3"]
        mon=collections.Counter(datetime.fromtimestamp(int(r["AD"]),timezone.utc).strftime("%Y%m") for r in fin)
        print(lg,y,"FEED",name,len(rs),"finished",len(fin),dict(sorted(mon.items())), sorted(set(r["ZA"] for r in rs)))
    print("allEventsCount",re.findall(r'allEventsCount:\s*(\d+)',html))
    recs=c.season_matches(y,y+1)
    fin=[r for r in recs.values() if r.get("AB")=="3"]
    mon=collections.Counter(datetime.fromtimestamp(int(r["AD"]),timezone.utc).strftime("%Y%m") for r in fin)
    print(lg,y,"COLLECTOR total",len(recs),"finished",len(fin),dict(sorted(mon.items())))
    print()
