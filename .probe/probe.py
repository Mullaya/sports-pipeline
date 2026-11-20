import requests, json
S = requests.Session(); S.headers.update({"User-Agent": "Mozilla/5.0"})
sp = S.get("https://statsapi.mlb.com/api/v1/sports", timeout=30).json()["sports"]
abl = [s for s in sp if "austral" in (s.get("name","")+s.get("abbreviation","")).lower()]
print("ABL sports:", [(s["id"], s["name"], s.get("abbreviation")) for s in abl])
print("all ids:", [(s["id"], s.get("abbreviation")) for s in sp])
for s in abl[:2]:
    sid = s["id"]
    lg = S.get(f"https://statsapi.mlb.com/api/v1/league?sportId={sid}", timeout=30).json()
    print("leagues", [(l["id"], l["name"], l.get("season")) for l in lg.get("leagues", [])])
    for season in (2025, 2026):
        r = S.get(f"https://statsapi.mlb.com/api/v1/schedule?sportId={sid}&season={season}&gameType=R", timeout=30).json()
        gs = [g for d in r.get("dates", []) for g in d["games"]]
        print(season, "games", len(gs), gs[0]["gameDate"] if gs else None, gs[-1]["gameDate"] if gs else None)
        if gs:
            g = gs[-1]; print(json.dumps({k: g[k] for k in ("gamePk","gameDate","status","teams")})[:700])
    r = S.get(f"https://statsapi.mlb.com/api/v1/schedule?sportId={sid}&startDate=2026-11-13&endDate=2026-11-22&hydrate=probablePitcher,linescore", timeout=30).json()
    gs = [g for d in r.get("dates", []) for g in d["games"]]
    print("recent", len(gs))
    for g in gs[:4]:
        print(g["gameDate"], g["teams"]["away"]["team"]["name"], g["teams"]["away"].get("score"), "@", g["teams"]["home"]["team"]["name"], g["teams"]["home"].get("score"), g["status"]["detailedState"], g["teams"]["home"].get("probablePitcher",{}).get("fullName"))
    if gs:
        pk = [g for g in gs if g["status"]["abstractGameState"]=="Final"]
        if pk:
            b = S.get(f"https://statsapi.mlb.com/api/v1/game/{pk[0]['gamePk']}/boxscore", timeout=30).json()
            print("boxscore keys", list(b), list(b["teams"]["home"]), len(b["teams"]["home"].get("pitchers",[])))
