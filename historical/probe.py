import requests,re
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}
html=requests.get("https://www.kbl.or.kr/match/schedule",headers=H,timeout=15).text
js=re.findall(r'src="([^"]+\.js)"',html); print("JS",js)
seen=set()
for j in js:
    u=j if j.startswith("http") else "https://www.kbl.or.kr"+j
    t=requests.get(u,headers=H,timeout=20).text
    print("JSLEN",u,len(t))
    for m in re.findall(r'["`](/[a-zA-Z0-9_\-/${}.]*(?:match|game|box|record|player|schedule|stat)[a-zA-Z0-9_\-/${}.]*)["`]',t):
        if m not in seen: seen.add(m); print("PATH",m)
    for m in re.findall(r'https?://[a-z0-9.\-]*kbl[a-z0-9.\-]*[^"\s`]*',t):
        if m not in seen: seen.add(m); print("HOST",m)
    # dynamic chunks
    for c in set(re.findall(r'"(js/[a-zA-Z0-9_\-.]+\.js)"',t))|set(re.findall(r'"([a-zA-Z0-9_\-]+\.[0-9a-f]{8}\.js)"',t)):
        print("CHUNK",c)
