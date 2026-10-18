import requests,json,re
from datetime import datetime,timedelta,timezone
UA={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36","Accept":"*/*"}
S=requests.Session(); S.headers.update(UA)
def J(u,**k):
    try:
        r=S.get(u,timeout=25,**k); return r.status_code, (r.json() if 'json' in r.headers.get('content-type','') or r.text[:1] in '{[' else r.text[:300])
    except Exception as e: return "ERR",str(e)
def show(tag,obj,n=900): print(f"\n### {tag}\n", json.dumps(obj,ensure_ascii=False)[:n] if not isinstance(obj,str) else obj[:n])
kst=datetime.now(timezone.utc)+timedelta(hours=9); today=kst.strftime("%Y-%m-%d"); us=(kst-timedelta(hours=14)).strftime("%Y-%m-%d")
# NHL
sc,d=J(f"https://api-web.nhle.com/v1/schedule/{us}")
g=None
if sc==200:
    games=[x for w in d.get("gameWeek",[]) for x in w.get("games",[])]
    show("NHL schedule",[ (x["id"],x["startTimeUTC"],x["awayTeam"]["abbrev"],x["homeTeam"]["abbrev"],x.get("gameState")) for x in games[:6]],600)
    up=[x for x in games if x.get("gameState") in ("FUT","PRE")]
    if up:
        gid=up[0]["id"]; sc2,l=J(f"https://api-web.nhle.com/v1/gamecenter/{gid}/landing")
        show("NHL landing keys",list(l.keys()) if isinstance(l,dict) else l)
        if isinstance(l,dict): show("NHL matchup",l.get("matchup",{}),1500)
else: show("NHL",d)
# NBA ESPN
sc,d=J(f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={(kst+timedelta(days=1)).strftime('%Y%m%d')}")
ev=d.get("events",[]) if isinstance(d,dict) else []
show("NBA scoreboard",[(e["id"],e["date"],e["shortName"],e["status"]["type"]["name"]) for e in ev[:5]] or d,500)
if ev:
    sc,s=J(f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={ev[0]['id']}")
    show("NBA summary keys",list(s.keys()) if isinstance(s,dict) else s)
    if isinstance(s,dict): show("NBA injuries",s.get("injuries",[])[:1],1200)
# MLB
sc,d=J(f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={us}&hydrate=probablePitcher,lineups")
gs=[g for dt in d.get("dates",[]) for g in dt.get("games",[])] if isinstance(d,dict) else []
for g in gs[:2]: show("MLB game",{"pk":g["gamePk"],"date":g["gameDate"],"away":g["teams"]["away"]["team"]["name"],"pp_away":g["teams"]["away"].get("probablePitcher",{}).get("fullName"),"pp_home":g["teams"]["home"].get("probablePitcher",{}).get("fullName"),"lineups":{k:len(v) for k,v in (g.get("lineups") or {}).items()}},500)
# Naver KBL / KOVO
H={"Referer":"https://m.sports.naver.com/","Origin":"https://m.sports.naver.com"}
for cat in ("kbl","kovo","wkovo"):
    sc,d=J(f"https://api-gw.sports.naver.com/schedule/games?fields=basic%2Csupercategoryid%2CcategoryName%2Cstadium%2CstatusNum%2CgameOnAir%2ChasVideo%2Ctitle%2CspecialMatchInfo%2CroundCode%2CseriesOutcome%2CseriesGameNo%2ChomeStarterName%2CawayStarterName%2CwinPitcherName%2ClosePitcherName%2ChomeCurrentPitcherName%2CawayCurrentPitcherName%2CbroadChannel&categoryId={cat}&fromDate={today}&toDate={(kst+timedelta(days=2)).strftime('%Y-%m-%d')}&size=50",headers=H)
    games=(d.get("result") or {}).get("games",[]) if isinstance(d,dict) else []
    show(f"naver {cat}",[(x.get("gameId"),x.get("gameDateTime"),x.get("homeTeamName"),x.get("awayTeamName"),x.get("statusCode")) for x in games[:4]] or d,500)
    if games:
        gid=games[0]["gameId"]
        for path in (f"schedule/games/{gid}",f"schedule/games/{gid}/preview",f"schedule/games/{gid}/lineup",f"schedule/games/{gid}/record"):
            sc,x=J(f"https://api-gw.sports.naver.com/{path}",headers=H)
            show(f"naver {cat} {path} {sc}", (list(((x or {}).get('result') or {}).keys()) if isinstance(x,dict) else x),400)
# Flashscore daily feeds
FH={"x-fsign":"SW9D1eZo","Referer":"https://www.flashscore.com/","Origin":"https://www.flashscore.com"}
for sport,name in ((1,"soccer"),(4,"hockey"),(3,"basketball"),(12,"volleyball"),(6,"baseball")):
    t=S.get(f"https://global.flashscore.ninja/2/x/feed/f_{sport}_1_9_en_1",headers=FH,timeout=25).text
    tours=re.findall(r"ZA÷([^¬]+)¬ZEE÷(\w+)",t)
    want=[z for z in tours if any(k in z[0] for k in ("ENGLAND: Premier","SPAIN: LaLiga","GERMANY: Bundesliga","ITALY: Serie A","FRANCE: Ligue 1","NETHERLANDS: Eredivisie","SOUTH KOREA","Champions League","GERMANY: DEL","CZECH REPUBLIC: Extraliga","RUSSIA: KHL","USA: NHL","USA: NBA","USA: MLB","KOREA","JAPAN"))]
    print(f"\n### FS {name} +1day total tours {len(tours)} matches {t.count('~AA÷')}", want[:14])
# Flashscore upcoming match lineup / h2h
t=S.get("https://global.flashscore.ninja/2/x/feed/f_4_0_9_en_1",headers=FH,timeout=25).text
blk=None
for b in t.split("~ZA÷"):
    if b.startswith("GERMANY: DEL¬") or b.startswith("CZECH REPUBLIC: Extraliga¬"): blk=b; break
if blk:
    ids=re.findall(r"AA÷(\w+)¬AD÷(\d+)¬(?:ADE÷\d+¬)?AB÷(\d)",blk); print("\nFS DEL/CZE today",ids[:5])
    for mid,ad,ab in ids[:1]:
        li=S.get(f"https://global.flashscore.ninja/2/x/feed/df_li_1_{mid}",headers=FH,timeout=20).text
        print("lineup len",len(li), li[:300])
        hh=S.get(f"https://global.flashscore.ninja/2/x/feed/df_hh_1_{mid}",headers=FH,timeout=20).text
        print("h2h len",len(hh), hh[:900])
