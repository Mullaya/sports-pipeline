import requests,re,json
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36","Origin":"https://www.kovo.co.kr","Referer":"https://www.kovo.co.kr/"}
t=requests.get("https://www.kovo.co.kr/assets/index-DVULM5Z7.js",headers=H,timeout=30).text
for k in ["user-api.kovo.co.kr",'"/stat/game-schedule"',"/stat/game-schedule/${e.gnum}?","/stat/season-list","interceptors.request.use"]:
    for m in list(re.finditer(re.escape(k),t))[:2]:
        print("CTX",k,t[max(0,m.start()-300):m.end()+500].replace("\n"," "))
A="https://user-api.kovo.co.kr"
for p in ["/stat/season-list","/stat/game-schedule?gender=M&month=11","/stat/game-schedule","/main/game/season"]:
    try:
        r=requests.get(A+p,headers=H,timeout=15); print("API",p,r.status_code,r.text[:800])
    except Exception as e: print("API ERR",p,e)
