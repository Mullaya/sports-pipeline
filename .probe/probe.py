import re,requests
UA={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36","Accept":"*/*"}
H={"x-fsign":"SW9D1eZo","Referer":"https://www.flashscore.com/","Origin":"https://www.flashscore.com"}
S=requests.Session(); S.headers.update(UA)
F="https://global.flashscore.ninja/2/x/feed/"
mid="rw8II4aD"
for f in ["df_ps_1_","df_pst_1_","df_lu_1_","dc_1_","df_ss_1_"]:
    r=S.get(F+f+mid,headers=H,timeout=20); print("\n##",f,r.status_code,len(r.text)); print(r.text[:1500])
r=S.get(F+"df_li_1_"+mid,headers=H,timeout=20)
blocks=r.text.split("~")
print("\n## LI blocks",len(blocks))
for b in blocks:
    if b.startswith(("LA","LB","LC","LD","LE","LF")) or "Goalkeeper" in b or "(G)" in b:
        print("  ",b[:260])
r=S.get(F+"df_sui_1_"+mid,headers=H,timeout=20)
print("\n## SUI tail", r.text[-1500:])
r=S.get(F+"dc_1_"+mid,headers=H,timeout=20); print("\n## dc",r.text[:800])
