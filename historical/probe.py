import requests,time
from collectors.flashscore_hockey_collector import FEED, FSIGN, SITE
s=requests.Session(); s.headers.update({"User-Agent":"Mozilla/5.0","x-fsign":FSIGN,"Referer":SITE+"/","Origin":SITE})
mid="xhZu26Yr"
for c in ["df_ps_1_","df_li_1_","df_lu_1_","df_pl_1_","df_lsp_1_","df_psm_1_","df_ls_1_","df_tps_1_"]:
    try:
        r=s.get(FEED+c+mid,timeout=20); print("FEED",c,r.status_code,len(r.text)); print(r.text[:900].replace("¬","|")); print("----")
    except Exception as e: print("FEED",c,"ERR",e)
for to in (60,):
    try:
        t=time.time(); r=requests.get("https://api-gw.sports.naver.com/schedule/games",params={"fields":"basic","upperCategoryId":"basketball","categoryId":"kbl","fromDate":"2026-11-06","toDate":"2026-11-06"},headers={"User-Agent":"Mozilla/5.0","Referer":"https://m.sports.naver.com/"},timeout=to); print("NAVER",r.status_code,round(time.time()-t,1),r.text[:200])
    except Exception as e: print("NAVER ERR",e)
