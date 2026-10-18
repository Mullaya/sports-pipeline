import requests
from datetime import datetime,timezone
API="https://khl.api.webcaster.pro/api/khl_mobile"
S=requests.Session(); S.headers.update({"User-Agent":"sports-pipeline/1.0"})
for p in ([("locale","en"),("season","2025")],[("locale","en"),("q[season_eq]","2025")],[("locale","en"),("tournament_id","1")],[("locale","en"),("q[id_in][]","407")]):
    r=S.get(f"{API}/stages.json",params=p,timeout=25); print("stages",p[1:],r.status_code,r.text[:400])
found=[]
for st in range(360,407):
    r=S.get(f"{API}/events_v2.json",params=[("locale","en"),("q[stage_id_in][]",st),("order_direction","asc"),("page",1)],timeout=25)
    try: ev=r.json()
    except: continue
    if isinstance(ev,list) and ev:
        e=[x.get('event',x) for x in ev]
        ts=[int(x.get('start_at') or 0)//1000 for x in e]
        d0=datetime.fromtimestamp(min(ts),timezone.utc).date(); d1=datetime.fromtimestamp(max(ts),timezone.utc).date()
        print("stage",st,len(ev),d0,d1,e[0].get('stage_type') or e[0].get('stage_name'),(e[0].get('team_a') or {}).get('name'))
