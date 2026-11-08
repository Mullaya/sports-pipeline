import requests,json
H={"User-Agent":"Mozilla/5.0 Chrome/124","Origin":"https://www.kovo.co.kr","Referer":"https://www.kovo.co.kr/","X-Service-Name":"user","Accept-Language":"ko"}
A="https://user-api.kovo.co.kr"
d=requests.get(A+"/stat/game-schedule/3",params={"gcode":"001","seasonCode":"023","leagueCode":"201","gender":"1"},headers=H,timeout=20).json()["payload"]
print("PKEYS",list(d.keys()))
print("GAME",json.dumps(d["game"],ensure_ascii=False))
print("NPLAYER",len(d["player"]))
for p in d["player"][:3]: print("PLAYER",json.dumps(p,ensure_ascii=False))
print("TEAM",json.dumps(d["team"],ensure_ascii=False)[:3000])
print("RANK",json.dumps(d.get("ranking"),ensure_ascii=False)[:300])
