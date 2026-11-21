import requests, json
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0"})
B="https://lscluster.hockeytech.com/feed/index.php"; K={"key":"f1aa699db3d81487","client_code":"ohl"}
def j(**p):
    t=S.get(B,params={**p,**K},timeout=30).text.strip()
    if t.startswith("("): t=t[1:-1]
    return json.loads(t)
s=j(feed="modulekit",view="seasons")["SiteKit"]["Seasons"]
print([(x["season_id"],x["season_name"]) for x in s[:8]])
sc=j(feed="modulekit",view="schedule",season_id="88")["SiteKit"]["Schedule"]
g=[x for x in sc if x["date_played"]=="2026-11-15"][0]; print({k:g[k] for k in ("game_id","home_team","visiting_team","home_goal_count","visiting_goal_count")})
d=j(feed="statviewfeed",view="gameSummary",game_id=g["game_id"],lang="en",site_id="0")
for side in ("homeTeam","visitingTeam"):
    for gk in d[side]["goalies"]: print(side, gk.get("starting"), gk["info"].get("firstName"), gk["info"].get("lastName"), gk.get("stats"))
