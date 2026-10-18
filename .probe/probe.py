import re,requests,json
UA={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36","Accept":"*/*"}
S=requests.Session(); S.headers.update(UA)
def clean(t): 
    t=re.sub(r'<script.*?</script>|<style.*?</style>','',t,flags=re.S); t=re.sub(r'<[^>]+>',' ',t); return re.sub(r'\s+',' ',t)
print("===== DEL detail")
r=S.get("https://www.penny-del.org/statistik/spieldetails/04102026_eisbaeren-berlin_gg_nuernberg-ice-tigers_4425",timeout=30); t=r.text
print(r.status_code,len(t))
c=clean(t); k=c.find("Eisbären"); print("TEXT",c[max(0,c.find("Spieldetails")-100):][:3500])
print("JSONish",sorted(set(re.findall(r'["\']([^"\']*(?:type=\d{3,}|eID=\w+|\.json|/api/)[^"\']*)["\']',t)))[:30])
print("SCRIPTS",[s[:300] for s in re.findall(r'<script[^>]*>(.*?)</script>',t,re.S) if len(s)>50 and 'cookie' not in s.lower()][:4])
print("\n===== DEL season list")
for u in ["https://www.penny-del.org/spiele?season=2025","https://www.penny-del.org/statistik/saison-2025-26/hauptrunde/spielplan","https://www.penny-del.org/statistik/archiv"]:
    r=S.get(u,timeout=30); ids=re.findall(r'spieldetails/(\d{8})_[^"]*_(\d+)"',r.text)
    print(u,r.status_code,len(ids),ids[:3],ids[-3:])
    if 'archiv' in u: print("  ARCH LINKS",sorted(set(re.findall(r'href="(/statistik/[^"]*2025-26[^"]*)"',r.text)))[:30])
print("\n===== FLASHSCORE detail feeds")
H={"x-fsign":"SW9D1eZo","Referer":"https://www.flashscore.com/","Origin":"https://www.flashscore.com"}
mid="rw8II4aD"
for host in ["https://local-global.flashscore.ninja/2","https://global.flashscore.ninja/2","https://d.flashscore.com"]:
    for feed in ["df_st_1_","df_sui_1_","df_li_1_"]:
        try:
            r=S.get(f"{host}/x/feed/{feed}{mid}",headers=H,timeout=20); print(host,feed,r.status_code,len(r.text),r.text[:700].replace("\n"," "))
        except Exception as e: print(host,feed,"ERR",e)
print("\n===== FLASHSCORE last season page")
for u in ["https://www.flashscore.com/hockey/czech-republic/extraliga-2025-2026/results/","https://www.flashscore.com/hockey/germany/del-2025-2026/results/","https://www.flashscore.com/hockey/germany/del/results/"]:
    r=S.get(u,timeout=30); t=r.text
    print(u,r.status_code,"matches",t.count("~AA÷"), "first",re.findall(r'AD÷(\d+)',t)[:1],"last",re.findall(r'AD÷(\d+)',t)[-1:])
    m=re.search(r'cjs\.initialFeeds\["summary-results"\]\s*=\s*\{.*?allEventsCount:\s*(\d+)',t,re.S); print("  allEventsCount",m.group(1) if m else None)
    m=re.search(r'(seasonId|tournament_stage_id|tournamentStage)[^,;]{0,80}',t); print("  ",m.group(0) if m else None)
