import requests,time
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
U=["https://www.kbl.or.kr/","https://api.kbl.or.kr/","https://www.kbl.or.kr/match/schedule","https://api.kbl.or.kr/matches?fromDate=20261106&toDate=20261106",
"https://sports.daum.net/","https://sports.daum.net/schedule/kbl",
"https://m.sports.naver.com/basketball/schedule/index","https://sports.news.naver.com/","https://api-gw.sports.naver.com/",
"https://www.kovo.co.kr/","https://www.wkbl.or.kr/","https://www.livesport.com/","https://www.sofascore.com/api/v1/sport/basketball/scheduled-events/2026-11-06",
"https://api.sofascore.com/api/v1/sport/basketball/scheduled-events/2026-11-06","https://www.espn.com/"]
for u in U:
    t=time.time()
    try:
        r=requests.get(u,headers=H,timeout=15); print("URL",r.status_code,round(time.time()-t,1),len(r.text),u, r.text[:150].replace("\n"," "))
    except Exception as e: print("URL ERR",round(time.time()-t,1),u,str(e)[:80])
