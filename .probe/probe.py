import requests, json
S=requests.Session();S.headers.update({"User-Agent":"Mozilla/5.0"})
B="https://site.api.espn.com/apis/site/v2/sports/basketball/nbl"
for rng in ("20240901-20250331","20250901-20260430","20260901-20261120"):
    r=S.get(B+"/scoreboard",params={"dates":rng,"limit":1000},timeout=60).json()
    ev=r.get("events",[])
    import collections
    print(rng,len(ev),collections.Counter((e.get("season")or{}).get("type") for e in ev), collections.Counter(e["status"]["type"]["completed"] for e in ev))
    if ev: print(ev[-1]["date"], ev[-1]["name"])
r=S.get(B+"/scoreboard",params={"dates":"20261115"},timeout=60).json()
e=r["events"][0]; print(e["name"],e["date"])
s=S.get(B+"/summary",params={"event":e["id"]},timeout=60).json()
print(list(s), bool(s.get("pickcenter")), len((s.get("boxscore")or{}).get("players",[])))
if s.get("pickcenter"): print(s["pickcenter"][0].get("details"), s["pickcenter"][0].get("overUnder"))
