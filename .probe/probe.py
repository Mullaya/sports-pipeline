import requests, json
S = requests.Session(); S.headers.update({"User-Agent": "Mozilla/5.0"})
lg = S.get("https://statsapi.mlb.com/api/v1/league?sportId=17", timeout=30).json().get("leagues", [])
print([(l["id"], l["name"], l.get("season")) for l in lg])
abl = [l for l in lg if "austral" in l["name"].lower()]
for l in abl:
    lid = l["id"]
    for season in (2024, 2025, 2026):
        r = S.get(f"https://statsapi.mlb.com/api/v1/schedule?sportId=17&leagueId={lid}&season={season}", timeout=30).json()
        gs = [g for d in r.get("dates", []) for g in d["games"]]
        fin = [g for g in gs if g["status"]["abstractGameState"] == "Final"]
        print(lid, season, "games", len(gs), "final", len(fin), gs[0]["gameDate"] if gs else None, gs[-1]["gameDate"] if gs else None)
    r = S.get(f"https://statsapi.mlb.com/api/v1/schedule?sportId=17&leagueId={lid}&startDate=2026-11-12&endDate=2026-11-23&hydrate=probablePitcher,linescore", timeout=30).json()
    gs = [g for d in r.get("dates", []) for g in d["games"]]
    for g in gs:
        print(g["gamePk"], g["gameDate"], g["gameType"], g["teams"]["away"]["team"]["name"], g["teams"]["away"].get("score"), "@", g["teams"]["home"]["team"]["name"], g["teams"]["home"].get("score"), g["status"]["detailedState"], "|PP", g["teams"]["away"].get("probablePitcher",{}).get("fullName"), "/", g["teams"]["home"].get("probablePitcher",{}).get("fullName"))
    fin = [g for g in gs if g["status"]["abstractGameState"] == "Final"]
    if fin:
        b = S.get(f"https://statsapi.mlb.com/api/v1/game/{fin[-1]['gamePk']}/boxscore", timeout=30).json()
        h = b["teams"]["home"]; print("box", list(h), "pitchers", h.get("pitchers")[:3], list(h["teamStats"]["batting"])[:10])
