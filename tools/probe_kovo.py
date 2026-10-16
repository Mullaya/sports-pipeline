"""임시 프로브: 네이버 배구 API 응답 구조 확인 (Actions에서만 실행)"""
import json, requests
H = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
     "Referer": "https://m.sports.naver.com/volleyball/schedule/index",
     "Origin": "https://m.sports.naver.com"}
API = "https://api-gw.sports.naver.com/schedule/games"
def get(url, **p):
    r = requests.get(url, params=p, headers=H, timeout=20)
    print(">>", r.url, r.status_code)
    try: return r.json()
    except Exception: print(r.text[:500]); return {}
def dump(x, n=6000): print(json.dumps(x, ensure_ascii=False)[:n])
for cat, frm, to in [("kovo","2025-10-18","2025-10-20"),("wkovo","2025-10-18","2025-10-20"),
                     ("wkovo","2026-10-14","2026-10-16"),("kovo","2026-03-20","2026-04-10")]:
    j = get(API, fields="basic", categoryId=cat, fromDate=frm, toDate=to, size=100)
    gs = (j.get("result") or {}).get("games") or []
    print(f"== {cat} {frm}~{to}: {len(gs)} games")
    for g in gs[:12]:
        print({k: g.get(k) for k in ("gameId","gameDate","statusCode","roundCode","homeTeamName","awayTeamName","homeTeamScore","awayTeamScore","categoryId")})
    if gs and cat != "kovo" or frm == "2025-10-18":
        done = [g for g in gs if g.get("statusCode") == "RESULT"]
        if done:
            gid = done[0]["gameId"]
            dump(gs[0], 3000)
            dump(get(f"{API}/{gid}"), 6000)
            rec = get(f"{API}/{gid}/record")
            dump(rec, 15000)
            if isinstance(rec.get("result"), dict):
                rd = rec["result"].get("recordData") or {}
                print("recordData keys:", list(rd.keys()))
                for k, v in rd.items():
                    if isinstance(v, list) and v: print(k, "first:", json.dumps(v[0], ensure_ascii=False)[:1500])
                    elif isinstance(v, dict): print(k, "dict:", json.dumps(v, ensure_ascii=False)[:1500])
            dump(get(f"{API}/{gid}/relay"), 1500)
