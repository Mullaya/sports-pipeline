import re,requests,json,html
UA={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36","Accept":"*/*"}
S=requests.Session(); S.headers.update(UA)
print("===== DEL /spiele")
t=S.get("https://www.penny-del.org/spiele",timeout=30).text
links=sorted(set(re.findall(r'href="([^"]*(?:spiel|game|match|ticker|report)[^"]*)"',t)))
print("LINKS",len(links),links[:40])
print("DATAATTR",sorted(set(re.findall(r'(data-[a-z\-]+)="',t)))[:60])
for m in re.finditer(r'(?:type=\d+|eID=\w+|ajax|json|api)[^"\' ]{0,120}',t): pass
print("AJAX",sorted(set(re.findall(r'["\']([^"\']*(?:type=\d{3,}|eID=\w+|\.json)[^"\']*)["\']',t)))[:40])
i=t.find('game'); 
idx=[m.start() for m in re.finditer(r'class="[^"]*game[^"]*"',t)][:3]
for k in idx: print("SNIP",re.sub(r'\s+',' ',t[k-200:k+1500]))
print("\n===== FLASHSCORE")
r=S.get("https://www.flashscore.com/hockey/czech-republic/extraliga/results/",timeout=30); t=r.text
for key in ("initialFeeds","cjs.","fsign","feed_sign","x-fsign","~AA÷"):
    j=t.find(key); print("KEY",key,j, t[j-80:j+300].replace("\n"," ") if j>=0 else "")
m=re.search(r"~AA÷(.{0,1200})",t)
print("FEEDSAMPLE", m.group(0)[:1200] if m else None)
print("count matches", t.count("~AA÷"))
