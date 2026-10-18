import re,requests
UA={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36","Accept":"*/*"}
S=requests.Session(); S.headers.update(UA)
t=S.get("https://www.flashscore.com/hockey/czech-republic/extraliga-2025-2026/results/",timeout=30).text
srcs=sorted(set(re.findall(r'src="(https://static\.flashscore\.com/[^"]+\.js[^"]*)"',t)))
print("SRCS",srcs)
m=re.search(r'cjs\.initialFeeds\["summary-results"\]\s*=\s*\{(.*?)\};',t,re.S)
if m: print("INITMETA",re.sub(r'data:\s*`.*?`','data:<...>',m.group(1),flags=re.S)[:800])
for k in ("seasonId","tournament_id","tournamentStageId","tournamentId","countryId","sport_id","project_id","\"tz\"","geoIp"):
    for mm in re.finditer(re.escape(k)+r'[^,;\n]{0,80}',t): print("CFG",mm.group(0)); break
for s in srcs:
    js=S.get(s,timeout=30).text
    for mm in re.finditer(r'.{0,160}["\'`]tr_.{0,200}',js): print("\nJS",s.split('/')[-1][:40],mm.group(0)); 
    for mm in re.finditer(r'.{0,120}summary-results.{0,200}',js): print("\nSR",s.split('/')[-1][:40],mm.group(0)[:330])
