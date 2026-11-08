import requests,re,json
t=requests.get("https://www.kbl.or.kr/assets/index-DIiXqPJC.js",timeout=30).text
i=t.find("getTeamCodeByDomain="); print("CTX",t[i:i+500])
A="https://api.kbl.or.kr"
base={"User-Agent":"Mozilla/5.0 Chrome/124","Origin":"https://www.kbl.or.kr","Referer":"https://www.kbl.or.kr/","Channel":"WEB","lang":"ko","X-Requested-With":"XMLHttpRequest"}
ok=None
for tc in ["XX","KBL","","00","10"]:
    h=dict(base,TeamCode=tc)
    r=requests.get(A+"/match/list?fromDate=20261106&toDate=20261106&tcodeList=all",headers=h,timeout=15)
    print("LIST",repr(tc),r.status_code,r.text[:600])
    if r.status_code==200 and ok is None: ok=(h,r.json())
if ok:
    h,data=ok; g=data[0] if isinstance(data,list) else data; print("GAMEKEYS",list(g.keys()) if isinstance(g,dict) else g)
    gk=g.get("gmkey") or g.get("gmKey")
    for p in [f"/match/{gk}/player-stat",f"/match/{gk}/team-record",f"/match/{gk}"]:
        r=requests.get(A+p,headers=h,timeout=15); print("DET",p,r.status_code,r.text[:1500])
