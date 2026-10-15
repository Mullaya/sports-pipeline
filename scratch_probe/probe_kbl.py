"""KBL 데이터 소스 구조 확인용 임시 프로브 (작업 후 삭제)"""
import json
import requests

S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
    "Referer": "https://m.sports.naver.com/basketball/schedule/index",
    "Origin": "https://m.sports.naver.com",
})
U = "https://api-gw.sports.naver.com/schedule/games"


def show(label, url, params=None, n=1500):
    print(f"\n===== {label} =====\n{url} {params}")
    try:
        r = S.get(url, params=params, timeout=20)
        print("status", r.status_code)
        try:
            j = r.json()
            print(json.dumps(j, ensure_ascii=False)[:n])
            return j
        except Exception:
            print(r.text[:800])
    except Exception as e:
        print("ERR", e)


for cat in ("kbl", "KBL"):
    for rng in (("2025-11-01", "2025-11-03"), ("2026-01-10", "2026-01-12")):
        show(f"{cat} {rng}", U, {"fields": "basic", "upperCategoryId": "basketball",
                                  "categoryId": cat, "fromDate": rng[0], "toDate": rng[1]})
show("no cat", U, {"fields": "basic", "upperCategoryId": "basketball",
                   "fromDate": "2025-11-01", "toDate": "2025-11-02"}, n=2500)
show("cat only", U, {"fields": "basic", "categoryId": "kbl",
                     "fromDate": "2025-11-01", "toDate": "2025-11-02"}, n=2500)
show("upcoming 2026", U, {"fields": "basic", "upperCategoryId": "basketball", "categoryId": "kbl",
                          "fromDate": "2026-10-01", "toDate": "2026-10-20"}, n=2500)

# KBL 공식 사이트 후보
for u in ("https://api.kbl.or.kr/match/list?fromDate=20251101&toDate=20251103",
          "https://www.kbl.or.kr/match/schedule?type=SCHEDULE&season_code=S43&month=11",
          "https://www.kbl.or.kr/"):
    show("kbl official", u, n=800)
