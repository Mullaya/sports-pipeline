import requests,json
H={"User-Agent":"Mozilla/5.0 Chrome/124","Origin":"https://www.kovo.co.kr","Referer":"https://www.kovo.co.kr/","X-Service-Name":"user","Accept-Language":"ko"}
A="https://user-api.kovo.co.kr"
r=requests.get(A+"/stat/game-schedule",params={"seasonCode":"023","gcode":"001"},headers=H,timeout=20).json()
c=r["payload"]["content"]; print("N",len(c), r["payload"]["page"])
done=[x for x in c if x.get("gdate","")>="2026-11-01"]
print("KEYS",list(c[0].keys()))
for x in done[:6]: print("G",{k:x[k] for k in ["seasonCode","leagueCode","leagueName","round","gender","gnum","hcode","hname","acode","gdate","gstime","hspoint","aspoint","place"]})
x=[y for y in done if y.get("hspoint",0)+y.get("aspoint",0)>0][0]
p={"gcode":"001","seasonCode":x["seasonCode"],"leagueCode":x["leagueCode"],"gender":x["gender"],"round":x["round"],"tcode":x["hcode"],"acode":x["acode"],"gdate":x["gdate"]}
d=requests.get(A+f"/stat/game-schedule/{x['gnum']}",params=p,headers=H,timeout=20).json()
pl=d.get("payload") or {}
print("DKEYS",list(pl.keys()))
print("GAME",json.dumps(pl.get("game"),ensure_ascii=False)[:1500])
print("PLAYER",len(pl.get("player") or []),json.dumps((pl.get("player") or [None])[:2],ensure_ascii=False)[:2000])
print("TEAM",json.dumps(pl.get("team"),ensure_ascii=False)[:2000])
