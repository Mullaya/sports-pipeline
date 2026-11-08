import requests,re,json
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36","Origin":"https://www.kbl.or.kr","Referer":"https://www.kbl.or.kr/"}
t=requests.get("https://www.kbl.or.kr/assets/index-DIiXqPJC.js",headers=H,timeout=30).text
for key in ['"/match/list"','/player-stat`','/team-record`','"/match/list/today"','api.kbl.or.kr"','"/match/year"']:
    for m in list(re.finditer(re.escape(key),t))[:2]:
        print("CTX",key,t[max(0,m.start()-350):m.end()+250].replace("\n"," "))
A="https://api.kbl.or.kr"
for path,params in [("/match/list",{"fromDate":"20261106","toDate":"20261106"}),("/match/list",{"fromDate":"2026-11-06","toDate":"2026-11-06"}),("/match/list/today",{}),("/match/year",{})]:
    try:
        r=requests.get(A+path,params=params,headers=H,timeout=15); print("API",path,params,r.status_code,r.text[:700])
    except Exception as e: print("API ERR",path,e)
