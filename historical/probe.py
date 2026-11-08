import requests,json,re
H={"User-Agent":"Mozilla/5.0 Chrome/124","Origin":"https://www.kovo.co.kr","Referer":"https://www.kovo.co.kr/","X-Service-Name":"user","Accept-Language":"ko"}
A="https://user-api.kovo.co.kr"
base={"gcode":"001","seasonCode":"023"}
vars=[base, dict(base,leagueCode="201",gender="1",round=1,tcode="1004",acode="1002",gdate="2026-11-01"),
      dict(base,leagueCode="201",gender="1",round="1",tcode="1004",acode="1002",gdate="20261101"),
      dict(base,leagueCode="201",gender="1")]
for v in vars:
    r=requests.get(A+"/stat/game-schedule/3",params=v,headers=H,timeout=20); print("V",v,r.status_code,r.text[:700])
t=requests.get("https://www.kovo.co.kr/assets/index-DVULM5Z7.js",headers=H,timeout=30).text
for k in ["gameScheduleDetail(","CZ({","CZ("]:
    for m in list(re.finditer(re.escape(k),t))[:3]:
        print("CTX",k,t[max(0,m.start()-500):m.end()+300].replace("\n"," "))
