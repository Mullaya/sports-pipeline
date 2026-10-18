import re,requests,json,collections
UA={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36","Accept":"*/*"}
H={"x-fsign":"SW9D1eZo","Referer":"https://www.flashscore.com/","Origin":"https://www.flashscore.com"}
S=requests.Session(); S.headers.update(UA)
F="https://global.flashscore.ninja/2/x/feed/"
def parse(text):
    out=[]
    for blk in text.split("~"):
        d={}
        for kv in blk.split("¬"):
            if "÷" in kv: k,v=kv.split("÷",1); d[k]=v
        if "AA" in d: out.append(d)
    return out
t=S.get("https://www.flashscore.com/hockey/czech-republic/extraliga-2025-2026/results/",timeout=30).text
m=re.search(r'cjs\.initialFeeds\["summary-results"\]\s*=\s*\{(.{0,600})',t,re.S); print("INIT",m.group(1)[:600] if m else None)
print("ZEE/ZB",re.findall(r'ZEE÷(\w+)',t)[:2],re.findall(r'ZB÷(\d+)',t)[:2])
for m2 in re.finditer(r'(tr_\w+|"tr_"|feed[^"\']{0,40}tr)',t): pass
js=re.findall(r'(\w+_%s?_?\d*_?)',"")
# guess pagination feeds
for f in ["tr_4_62_QR1GYbvD_K0tmQWEr_1_9_en_1","tr_4_62_QR1GYbvD_K0tmQWEr_2_9_en_1","tr_4_62_QR1GYbvD_K0tmQWEr_3_9_en_1","tr_4_62_QR1GYbvD_K0tmQWEr_2_3_en_1"]:
    r=S.get(F+f,headers=H,timeout=20); ms=parse(r.text); print("PAGE",f,r.status_code,len(r.text),len(ms), [m.get('AD') for m in ms[:1]],[m.get('AD') for m in ms[-1:]])
for d in (-1,-2):
    r=S.get(F+f"f_4_{d}_9_en_1",headers=H,timeout=20); ms=parse(r.text)
    lg=collections.Counter()
    cur=None
    for blk in r.text.split("~"):
        if blk.startswith("ZA÷"): cur=blk.split("¬")[0][3:]
        if blk.startswith("AA÷"): lg[cur]+=1
    print("DAY",d,r.status_code,len(ms),[ (k,v) for k,v in lg.items() if any(x in k for x in ("CZECH","GERMANY","RUSSIA"))])
# key analysis on finished czech matches in initial page
ms=parse(t)
keys=collections.Counter(k for m in ms for k in m)
print("KEYS",sorted(keys.items()))
def i(x):
    try: return int(x)
    except: return None
for m in ms:
    if m.get("AB")!="3": continue
    per=sum(i(m.get(k)) or 0 for k in ("BA","BC","BE")),sum(i(m.get(k)) or 0 for k in ("BB","BD","BF"))
    if per!=(i(m.get("AG")),i(m.get("AH"))):
        print("NONREG",{k:m[k] for k in m if k in ("AA","AD","AE","AF","AG","AH","AS","AZ","AT","AU","BA","BB","BC","BD","BE","BF","BG","BH","BI","BJ","BK","BL","AC","CR","ER","AK","AL","AM","AN","AO")})
        break
print("SAMPLE REG",{k:v for k,v in [m for m in ms if m.get("AB")=="3"][0].items() if len(v)<40})
