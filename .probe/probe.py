import requests, re, json
S = requests.Session()
S.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"})
H = {"x-fsign": "SW9D1eZo", "Referer": "https://www.flashscore.com/", "Origin": "https://www.flashscore.com"}
def g(u, h=None, n=600):
    try:
        r = S.get(u, headers=h or {}, timeout=25); print(f"\n### {u} {r.status_code} len={len(r.text)}"); print(r.text[:n]); return r.text
    except Exception as e:
        print("\n###", u, "ERR", e); return ""
mid = "W6vNeb2l"
for base in ["https://d.flashscore.com/x/feed/", "https://local-global.flashscore.ninja/2/x/feed/", "https://global.flashscore.ninja/2/x/feed/"]:
    for p in ["df_li_1_", "df_lis_1_", "df_lu_1_", "dc_1_", "df_mlu_1_"]:
        g(base + p + mid, H, 300)
html = g(f"https://www.flashscore.com/match/hockey/{mid}/", n=200)
print("feed refs:", sorted(set(re.findall(r'(df_[a-z]+_)', html)))[:50])
print("fsign:", re.findall(r'feed_sign["\':\s]+([A-Za-z0-9]+)', html)[:3])
for js in re.findall(r'src="([^"]+\.js[^"]*)"', html)[:15]:
    u = js if js.startswith("http") else "https://www.flashscore.com" + js
    try:
        t = S.get(u, timeout=25).text
        refs = sorted(set(re.findall(r'(df_[a-z]{2,4}_)', t)))
        if refs: print("JS", u[-60:], refs)
    except Exception as e: pass
# Liiga
t = g("https://liiga.fi/api/v2/games/2027/1", n=200)
try:
    d = json.loads(t); print("LIIGA keys", list(d), list(d.get("game", {})), list(d["game"]["homeTeam"]))
    print(json.dumps({k: d[k] for k in d if k != "game"}, ensure_ascii=False)[:1500])
except Exception as e: print("liiga parse", e)
g("https://liiga.fi/api/v2/schedule?tournament=runkosarja&week=1&season=2027", n=300)
g("https://liiga.fi/api/v2/games?tournament=runkosarja&season=2027", n=300)
# AHL game summary
t = g("https://lscluster.hockeytech.com/feed/index.php?feed=statviewfeed&view=gameSummary&game_id=1029308&key=50c2cd9b5e18e390&client_code=ahl&lang=en&site_id=0", n=300)
m = re.search(r'goalie', t or ""); print("AHL goalie mention", bool(m), (t or "")[t.find('"goalies"') : t.find('"goalies"') + 800] if t and '"goalies"' in t else "")
# SHL / DEL api hints
for u in ["https://www.shl.se/", "https://www.penny-del.org/"]:
    h = S.get(u, timeout=25).text
    print(u, sorted(set(re.findall(r'https?://[a-zA-Z0-9.\-]+/(?:api|sports-v2|data)[^"\'\s<>]{0,60}', h)))[:20], sorted(set(re.findall(r'"/api/[^"]{0,60}"', h)))[:20])
g("https://www.shl.se/api/sports-v2/game-schedule?seasonUuid=&seriesUuid=&gameTypeUuid=&gamePlace=all&played=all", n=300)
g("https://www.penny-del.org/api/v2/live-ticker", n=200)
g("https://www.asiaicehockey.com/", n=200)
