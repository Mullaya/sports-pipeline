import requests,re
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36","Origin":"https://www.kbl.or.kr","Referer":"https://www.kbl.or.kr/"}
t=requests.get("https://www.kbl.or.kr/assets/index-DIiXqPJC.js",headers=H,timeout=30).text
i=t.find("axios.interceptors.request.use"); print("CTX1",t[i:i+1800])
for k in ["getMatchList(","getPlayerStatByGmkey(","getTeamRecordByGmkey(","const get$3=","get$3=async","function getMobileAppHeaderData"]:
    for m in list(re.finditer(re.escape(k),t))[:3]:
        print("CTX",k,t[max(0,m.start()-200):m.end()+500])
