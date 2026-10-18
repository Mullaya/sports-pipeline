import requests,re,collections
UA={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
FH={**UA,"x-fsign":"SW9D1eZo","Referer":"https://www.flashscore.com/","Origin":"https://www.flashscore.com"}
S=requests.Session()
names=collections.defaultdict(set); sample={}
for sport in (1,3,4,6,12):
    for off in (-1,0,1,2):
        t=S.get(f"https://global.flashscore.ninja/2/x/feed/f_{sport}_{off}_9_en_1",headers=FH,timeout=25).text
        for blk in t.split("~ZA÷")[1:]:
            za=blk.split("¬")[0]; zee=re.search(r"ZEE÷(\w+)",blk)
            if not any(k in za for k in ("USA: NHL","USA: NBA","USA: MLB","SOUTH KOREA","RUSSIA: KHL","JAPAN: NPB")): continue
            key=f"{sport}|{za}|{zee.group(1) if zee else ''}"
            for m in re.finditer(r"AA÷(\w+)¬AD÷(\d+)¬(?:ADE÷\d+¬)?AB÷(\d)",blk):
                sample.setdefault(key,[]).append(m.groups())
            for n in re.findall(r"(?:AE|AF)÷([^¬]+)",blk): names[key].add(n)
for k,v in sorted(names.items()): print(k, sorted(v))
# lineup structure samples
def groups(mid):
    t=S.get(f"https://global.flashscore.ninja/2/x/feed/df_li_1_{mid}",headers=FH,timeout=20).text
    g=[];cur=None
    for b in t.split("~"):
        if b.startswith("LB÷") or "¬LB÷" in b[:40]:
            lb=re.search(r"LB÷([^¬]*)",b).group(1); g.append(lb)
    return len(t), collections.Counter(g)
for k,v in sample.items():
    fin=[m for m in v if m[2] in ("1","3")][:1]
    for mid,ad,ab in fin: print("LINEUP",k.split('|')[1],mid,ab,groups(mid))
