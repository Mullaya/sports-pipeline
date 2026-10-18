import re,requests,json
UA={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36","Accept":"*/*"}
def show(u,n=500,**k):
    try:
        r=requests.get(u,headers={**UA,**k.pop('h',{})},timeout=25,**k)
        ct=r.headers.get('content-type','')
        print(f"\n### {r.status_code} {ct[:30]} {len(r.text)} {u}")
        print("   ",r.text[:n].replace("\n"," "))
        return r
    except Exception as e: print("\n### ERR",u,e)
r=show("https://www.penny-del.org/",0)
if r is not None:
    hrefs=sorted(set(re.findall(r'href="([^"#]+)"',r.text)))
    print("HREFS",[h for h in hrefs if h.startswith('/') and len(h)<60][:80])
    print("DATA",sorted(set(re.findall(r'data-[a-z\-]+="(https?://[^"]+|/[^"]{3,100})"',r.text)))[:40])
for u in ["https://www.penny-del.org/api/v1/games","https://api.del.org/","https://www.penny-del.org/statistik","https://www.penny-del.org/spiele"]: show(u,300)
# Sofascore
show("https://api.sofascore.com/api/v1/sport/ice-hockey/scheduled-events/2026-10-17",400)
show("https://www.sofascore.com/api/v1/sport/ice-hockey/scheduled-events/2026-10-17",400)
# TheSportsDB
show("https://www.thesportsdb.com/api/v1/json/3/eventsday.php?d=2026-10-17&s=Ice_Hockey",600)
# Livesport / flashscore
show("https://www.livesport.cz/hokej/cesko/extraliga/vysledky/",300)
show("https://www.flashscore.com/hockey/czech-republic/extraliga/results/",300)
# Czech others
for u in ["https://www.tipsportextraliga.cz/","https://www.hokej.cz/api/","https://www.eliteprospects.com/league/czechia/games","https://www.eurohockey.com/league/schedule/40-czech-extraliga.html?season=2026","https://sport.ceskatelevize.cz/","https://www.isport.cz/hokej/extraliga/"]: show(u,300)
