import requests, json
S = requests.Session(); S.headers.update({"User-Agent": "Mozilla/5.0"})
out = []
for season in (2023, 2024, 2025, 2026):
    r = S.get(f"https://statsapi.mlb.com/api/v1/schedule?sportId=17&leagueId=595&season={season}&hydrate=linescore,decisions,probablePitcher", timeout=60).json()
    for d in r.get("dates", []):
        for g in d["games"]:
            a, h = g["teams"]["away"], g["teams"]["home"]
            ls = g.get("linescore", {})
            out.append([season, g["gamePk"], g["gameDate"], g.get("gameType"), g["status"]["detailedState"],
                        a["team"]["name"], h["team"]["name"], a.get("score"), h.get("score"),
                        ls.get("currentInning"), (g.get("decisions") or {}).get("winner", {}).get("fullName"),
                        a.get("probablePitcher", {}).get("fullName"), h.get("probablePitcher", {}).get("fullName"),
                        g.get("venue", {}).get("name")])
print("JSON" + json.dumps(out, ensure_ascii=False))
