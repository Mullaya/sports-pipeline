import requests
S=requests.Session();S.headers.update({"User-Agent":"Mozilla/5.0"})
r=S.get("https://api-web.nhle.com/v1/score/2026-11-19",timeout=30).json()
for g in r.get("games",[]):
    print("NHL",g["awayTeam"]["abbrev"],g["awayTeam"].get("score"),"@",g["homeTeam"]["abbrev"],g["homeTeam"].get("score"),g.get("gameOutcome",{}).get("lastPeriodType"))
r=S.get("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20261119",timeout=30).json()
for e in r.get("events",[]):
    c=e["competitions"][0]["competitors"];h=[x for x in c if x["homeAway"]=="home"][0];a=[x for x in c if x["homeAway"]=="away"][0]
    print("NBA",a["team"]["abbreviation"],a["score"],"@",h["team"]["abbreviation"],h["score"])
