import requests, json, collections
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0"})
lg=S.get("https://statsapi.mlb.com/api/v1/league?sportId=17",timeout=30).json()["leagues"]
print([(l["id"],l["name"]) for l in lg])
for l in lg:
    if "Pac" in l["name"] or "Mex" in l["name"]:
        lid=l["id"]
        for season in (2024,2025,2026):
            r=S.get(f"https://statsapi.mlb.com/api/v1/schedule?sportId=17&leagueId={lid}&season={season}&hydrate=probablePitcher,linescore",timeout=60).json()
            gs=[g for d in r.get("dates",[]) for g in d["games"]]
            fin=[g for g in gs if g["status"]["abstractGameState"]=="Final"]
            pp=sum(1 for g in gs if g["teams"]["home"].get("probablePitcher"))
            print(lid,l["name"],season,len(gs),"final",len(fin),"pp",pp,collections.Counter(g["gameType"] for g in gs), gs[0]["gameDate"] if gs else "", gs[-1]["gameDate"] if gs else "")
        r=S.get(f"https://statsapi.mlb.com/api/v1/schedule?sportId=17&leagueId={lid}&startDate=2026-11-18&endDate=2026-11-22&hydrate=probablePitcher,linescore",timeout=60).json()
        for d in r.get("dates",[]):
            for g in d["games"]:
                print(g["gameDate"],g["teams"]["away"]["team"]["name"],g["teams"]["away"].get("score"),"@",g["teams"]["home"]["team"]["name"],g["teams"]["home"].get("score"),g["status"]["detailedState"],"|",g["teams"]["away"].get("probablePitcher",{}).get("fullName"),"/",g["teams"]["home"].get("probablePitcher",{}).get("fullName"))
