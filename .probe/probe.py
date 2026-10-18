import sys,json,requests
from datetime import datetime,timedelta,timezone
sys.path.insert(0,'.')
API="https://khl.api.webcaster.pro/api/khl_mobile"
MSK=timezone(timedelta(hours=3))
S=requests.Session(); S.headers.update({"User-Agent":"sports-pipeline/1.0"})
def q(params): 
    r=S.get(f"{API}/events_v2.json",params=params,timeout=25); 
    try: d=r.json()
    except: d=r.text[:200]
    return r.status_code,d
for ds in ["20251010","20260115","20261016"]:
    day=datetime.strptime(ds,"%Y%m%d").replace(tzinfo=MSK); t0,t1=int(day.timestamp()),int((day+timedelta(days=1)).timestamp())
    sc,d=q([("locale","en"),("q[start_at_gt_time_from_unixtime]",t0-1),("q[start_at_lt_time_from_unixtime]",t1),("order_direction","asc"),("page",1)])
    evs=d if isinstance(d,list) else (d.get('events') or d.get('error') if isinstance(d,dict) else d)
    print(ds,sc,type(d).__name__, len(evs) if isinstance(evs,list) else evs)
    if isinstance(evs,list) and evs:
        e=evs[0].get('event',evs[0]); print("   ",e.get('id'),e.get('start_at'),e.get('game_state_key'),e.get('stage_id'),(e.get('team_a') or {}).get('name'))
# stages / seasons
for path,params in [("stages_v2.json",[("locale","en")]),("seasons.json",[("locale","en")]),("stages.json",[("locale","en")])]:
    r=S.get(f"{API}/{path}",params=params,timeout=25); print("\n",path,r.status_code,r.text[:1200])
for st in ["386","407"]:
    sc,d=q([("locale","en"),("q[stage_id_in][]",st),("order_direction","asc"),("page",1)])
    evs=d if isinstance(d,list) else []
    print("stage",st,sc,len(evs), [ (x.get('event',x).get('start_at'),x.get('event',x).get('game_state_key')) for x in evs[:2]])
