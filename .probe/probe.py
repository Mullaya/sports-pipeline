import requests, re, json
S = requests.Session()
S.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"})
det = S.get("https://static.flashscore.com/res/_fs/build/detail.ToPma-I.js", timeout=30).text
files = sorted(set(re.findall(r'/res/_fs/build/[A-Za-z]*[Ll]ineup[A-Za-z]*\.[A-Za-z0-9_\-]+\.js', det)))
print("lineup js", files)
for m in re.finditer(r'.{150}_hash.{250}', det): print("DET hash ctx:", m.group(0)); 
for f in files + ["/res/_fs/build/" + x for x in re.findall(r'"/res/_fs/build/([A-Za-z]*(?:Player|Stat)[A-Za-z]*\.[A-Za-z0-9_\-]+\.js)"', det)][:6]:
    t = S.get("https://static.flashscore.com" + f, timeout=30).text
    print("\n##", f, len(t))
    for m in re.finditer(r'.{120}(?:_hash|pq_graphql|hash:|"hash").{200}', t): print("  ctx:", m.group(0))
    print("  ids:", sorted(set(re.findall(r'"([a-z]{2,6}[a-z0-9]{0,4})"\s*[,)]\s*', t)))[:40])
core = S.get("https://static.flashscore.com/x/js/core_2_2324000000.js", timeout=30).text
for m in re.finditer(r'.{200}pq_graphql.{200}', core): print("CORE:", m.group(0))
d = S.get("https://liiga.fi/api/v2/games/2027/2701526", timeout=30).json()
print("LIIGA game keys", list(d["game"]), list(d["game"]["homeTeam"]))
print(json.dumps(d["game"]["homeTeam"], ensure_ascii=False)[:200])
for k in d["game"]:
    if "goal" in k.lower() or "stat" in k.lower(): print(k, str(d["game"][k])[:400])
