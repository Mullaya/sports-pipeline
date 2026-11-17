import requests, re, json
S = requests.Session()
S.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"})
H = {"x-fsign": "SW9D1eZo", "Referer": "https://www.flashscore.com/", "Origin": "https://www.flashscore.com"}
L = S.get("https://liiga.fi/api/v2/games?tournament=runkosarja&season=2027", timeout=30).json()
x = [g for g in L if g.get("ended")][-1] if any("ended" in g for g in L) else L[0]
print("LIIGA list keys", list(x)); print("homeTeam keys", list(x["homeTeam"]))
print(json.dumps({k: v for k, v in x.items() if k not in ("homeTeam", "awayTeam")}, ensure_ascii=False)[:800])
for u in [f"https://liiga.fi/api/v2/games/2027/{x['id']}", f"https://liiga.fi/api/v2/games/2027/{x['id']}/boxscore"]:
    t = S.get(u, timeout=30).text; print("\n###", u, len(t)); print(t[:300])
    try:
        d = json.loads(t); print("keys", list(d))
        if "homeTeamPlayers" in d and d["homeTeamPlayers"]:
            gk = [p for p in d["homeTeamPlayers"] if p.get("role") in ("GOALIE", "G") or "goalie" in json.dumps(p).lower()][:1]
            print("player keys", list(d["homeTeamPlayers"][0])); print("gk", json.dumps(gk, ensure_ascii=False)[:900])
    except Exception as e: print(e)
html = S.get("https://www.flashscore.com/match/hockey/W6vNeb2l/", timeout=30).text
for pat in [r"lsapp[^\"' ]{0,80}", r"pq_graphql[^\"' ]{0,120}", r"feed/[a-z_]{2,12}", r"_hash[^\"' ]{0,60}", r"https://[a-z0-9.\-]*ninja[^\"' ]{0,60}"]:
    print(pat, sorted(set(re.findall(pat, html)))[:15])
jss = re.findall(r'<script[^>]+src="([^"]+)"', html); print("scripts", len(jss), jss[:30])
for js in jss:
    u = js if js.startswith("http") else "https://www.flashscore.com" + js
    try: t = S.get(u, timeout=25).text
    except Exception: continue
    hits = sorted(set(re.findall(r'(df_[a-z]{2,4}_|pq_graphql|lineup[A-Za-z]*|_hash)', t)))
    if hits: print("JS", u[-70:], hits[:30]); 
    for m in re.finditer(r'.{80}(?:df_li|lineup)s?.{120}', t):
        print("   ctx:", m.group(0)[:200]); break
