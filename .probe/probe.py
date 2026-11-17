import requests, json
S = requests.Session(); S.headers.update({"User-Agent": "Mozilla/5.0"})
d = S.get("https://liiga.fi/api/v2/games/2027/2701526", timeout=30).json()
ht = d["game"]["homeTeam"]
print("goalKeeperEvents", json.dumps(ht["goalKeeperEvents"], ensure_ascii=False)[:1200])
print("goalKeeperChanges", json.dumps(ht["goalKeeperChanges"], ensure_ascii=False)[:600])
L = S.get("https://liiga.fi/api/v2/games?tournament=runkosarja&season=2027", timeout=30).json()
print("liiga names", sorted({g["homeTeam"]["teamName"] for g in L}))
print("list has goalKeeperEvents?", "goalKeeperEvents" in L[0]["homeTeam"])
L26 = S.get("https://liiga.fi/api/v2/games?tournament=runkosarja&season=2026", timeout=30).json(); print("2026 games", len(L26), L26[0]["start"])
K = "key=50c2cd9b5e18e390&client_code=ahl"
s = S.get(f"https://lscluster.hockeytech.com/feed/index.php?feed=modulekit&view=seasons&{K}", timeout=30).json()
print("seasons", [(x["season_id"], x["season_name"]) for x in s["SiteKit"]["Seasons"]][:8])
sch = S.get(f"https://lscluster.hockeytech.com/feed/index.php?feed=modulekit&view=schedule&season_id=94&{K}", timeout=30).json()
gs = sch["SiteKit"]["Schedule"]; print("sched n", len(gs)); print(json.dumps(gs[0])[:900])
t = S.get(f"https://lscluster.hockeytech.com/feed/index.php?feed=statviewfeed&view=gameSummary&game_id=1029308&{K}&lang=en&site_id=0", timeout=30).text.strip()
j = json.loads(t[1:-1]); print("summary keys", list(j)); print("homeTeam", json.dumps(j.get("homeTeam", {}))[:300]); print("hg", json.dumps(j["homeTeam"].get("goalies"))[:300] if "homeTeam" in j else "")
