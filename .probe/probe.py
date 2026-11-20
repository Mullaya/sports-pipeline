import requests, json
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0"})
B="https://lscluster.hockeytech.com/feed/index.php"
for key in ("f1aa699db3d81487","50c2cd9b5e18e390"):
    try:
        r=S.get(B,params={"feed":"modulekit","view":"seasons","key":key,"client_code":"ohl"},timeout=30)
        t=r.text.strip()
        print(key, r.status_code, t[:300])
    except Exception as e: print(key, e)
