import re,requests
UA={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36","Accept":"*/*"}
H={"x-fsign":"SW9D1eZo","Referer":"https://www.flashscore.com/","Origin":"https://www.flashscore.com"}
S=requests.Session(); S.headers.update(UA)
F="https://global.flashscore.ninja/2/x/feed/"
def ids(text): return re.findall(r'AA÷(\w+)¬AD÷(\d+)',text)
for name,url in [("CZE","https://www.flashscore.com/hockey/czech-republic/extraliga-2025-2026/results/"),("DEL","https://www.flashscore.com/hockey/germany/del-2025-2026/results/"),("DELcur","https://www.flashscore.com/hockey/germany/del/results/"),("KHLprev","https://www.flashscore.com/hockey/russia/khl-2025-2026/results/")]:
    t=S.get(url,timeout=30).text
    sid=re.search(r'seasonId:\s*(\d+)',t); tid=re.search(r'tournament_id":"(\w+)"',t); cid=re.search(r'countryId":"(\d+)"',t)
    sid,tid,cid=sid.group(1),tid.group(1),cid.group(1)
    init=ids(t); total=re.search(r'allEventsCount:\s*(\d+)',t)
    print(name,"season",sid,"tour",tid,"country",cid,"init",len(init),"all",total.group(1) if total else None)
    seen=set(i for i,_ in init)
    for proj in ("2","1"):
        got=0
        for page in range(1,8):
            f=f"tr_4_{cid}_{tid}_{sid}_{page}_0_en_{proj}"
            r=S.get(F+f,headers=H,timeout=20); x=ids(r.text)
            new=[i for i,_ in x if i not in seen]; seen.update(new); got+=len(new)
            print("   ",f,r.status_code,len(x),"new",len(new), (min(int(a) for _,a in x), max(int(a) for _,a in x)) if x else "")
            if not x: break
        if got: break
    print("  TOTAL unique",len(seen))
