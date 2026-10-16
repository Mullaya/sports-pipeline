"""임시 프로브: 네이버 배구 일정 API 누락 원인 확인"""
import json, requests
H = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
     "Referer": "https://m.sports.naver.com/volleyball/schedule/index", "Origin": "https://m.sports.naver.com"}
API = "https://api-gw.sports.naver.com/schedule/games"
def get(url, **p):
    r = requests.get(url, params=p, headers=H, timeout=20)
    try: j = r.json()
    except Exception: j = {"raw": r.text[:300]}
    return r.status_code, j
def lst(**p):
    c, j = get(API, **p)
    gs = (j.get("result") or {}).get("games") or []
    print(">>", p, c, len(gs), "| keys:", list((j.get("result") or {}).keys()))
    for g in gs: print("   ", g.get("gameId"), g.get("categoryId"), g.get("gameDate"), g.get("statusCode"), g.get("homeTeamName"), g.get("awayTeamName"))
    return j
for frm, to in [("2025-10-18", "2025-10-20"), ("2025-11-01", "2025-11-03")]:
    lst(fields="basic", categoryId="kovo", fromDate=frm, toDate=to, size=100)
    lst(fields="basic", categoryId="wkovo", fromDate=frm, toDate=to, size=100)
    lst(fields="basic", upperCategoryId="kvolleyball", fromDate=frm, toDate=to, size=100)
    lst(fields="basic,schedule", upperCategoryId="kvolleyball", categoryId="kovo", fromDate=frm, toDate=to, size=100)
    lst(fields="basic", superCategoryId="volleyball", fromDate=frm, toDate=to, size=100)
    lst(fields="all", categoryId="kovo", fromDate=frm, toDate=to, size=100)
    lst(fields="basic", categoryId="kovo", fromDate=frm, toDate=frm, size=100)
for gid in ["20251018022M1", "20251019022M2", "20251018022F1"]:
    c, j = get(f"{API}/{gid}")
    g = (j.get("result") or {}).get("game") or {}
    print("GAME", gid, c, g.get("categoryId"), g.get("gameDate"), g.get("statusCode"), g.get("homeTeamName"), g.get("awayTeamName"), g.get("roundCode"))
# 범위 조회 한 번에 시즌 전체 (페이지 여부 확인)
j = lst(fields="basic", categoryId="kovo", fromDate="2025-10-18", toDate="2025-11-30", size=500)
print("SEASONLIST", json.dumps({k: v for k, v in (j.get("result") or {}).items() if k != "games"}, ensure_ascii=False)[:800])
