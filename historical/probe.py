import requests,re
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}
for page in ["https://www.kovo.co.kr/"]:
    html=requests.get(page,headers=H,timeout=15).text; print("PAGE",page,len(html))
    js=re.findall(r'src="([^"]+\.js)"',html); print("JS",js)
    for j in js:
        u=j if j.startswith("http") else "https://www.kovo.co.kr"+("" if j.startswith("/") else "/")+j
        try: t=requests.get(u,headers=H,timeout=30).text
        except Exception as e: print("JSERR",u,e); continue
        print("JSLEN",u,len(t))
        seen=set()
        for m in re.findall(r'https?://[a-zA-Z0-9.\-]*(?:api|kovo)[a-zA-Z0-9.\-]*[^"\'\s`]{0,60}',t):
            if m not in seen: seen.add(m); print("HOST",m)
        for m in re.findall(r'["`](/[a-zA-Z0-9_\-/${}.]*(?:game|match|record|player|schedule|box|stat|result)[a-zA-Z0-9_\-/${}.?=&]*)["`]',t):
            if m not in seen: seen.add(m); print("PATH",m)
        i=t.find("baseURL"); print("BASE",t[max(0,i-200):i+400] if i>=0 else None)
