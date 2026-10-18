import re,sys,requests
UA={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36","Accept-Language":"en"}
def get(u,**k):
    try:
        r=requests.get(u,headers=UA,timeout=25,**k); return r
    except Exception as e:
        print("ERR",u,e); return None
for u in ["https://www.penny-del.org/spielplan","https://www.penny-del.org/","https://www.hokej.cz/tipsport-extraliga/zapasy","https://www.hokej.cz/"]:
    r=get(u)
    if r is None: continue
    print("\n#####",u,r.status_code,len(r.text))
    t=r.text
    urls=set(re.findall(r'https?://[a-zA-Z0-9.\-]+(?:/[^\s"\'<>\\)]*)?',t))
    for x in sorted(urls):
        if any(k in x.lower() for k in ("api","json","stats","data","live","match","game","feed")): print("  U",x[:160])
    for x in sorted(set(re.findall(r'["\'](/[^"\']*(?:api|json|feed)[^"\']*)["\']',t)))[:40]: print("  P",x[:160])
    js=sorted(set(re.findall(r'src="([^"]+\.js[^"]*)"',t)))[:25]
    for j in js:
        ju=j if j.startswith("http") else requests.compat.urljoin(u,j)
        jr=get(ju)
        if not jr: continue
        hits=set(re.findall(r'["\'`](https?://[^"\'`\s]{5,140})["\'`]',jr.text))|set(re.findall(r'["\'`](/api[^"\'`\s]{1,120})["\'`]',jr.text))
        hits=[h for h in hits if any(k in h.lower() for k in ("api","json","feed","stats","live"))]
        if hits: print("  JS",ju[:100]); [print("     ",h) for h in sorted(hits)[:30]]
    nd=re.search(r'__NEXT_DATA__"[^>]*>(.{0,1500})',t,re.S)
    if nd: print("  NEXT_DATA",nd.group(1)[:1500])
