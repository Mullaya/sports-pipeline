"""KBL 데이터 소스 구조 확인용 임시 프로브 (작업 후 삭제)"""
import json
import requests

S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://m.sports.naver.com/",
    "Origin": "https://m.sports.naver.com",
})


def show(label, url, params=None, n=3000):
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


sched = show("naver schedule", "https://api-gw.sports.naver.com/schedule/games",
             {"fields": "basic,schedule", "upperCategoryId": "basketball",
              "categoryId": "kbl", "fromDate": "2025-10-03", "toDate": "2025-10-05", "size": 50})

gid = None
try:
    gid = sched["result"]["games"][0]["gameId"]
except Exception:
    pass
print("GAME_ID", gid)
if gid:
    show("naver game", f"https://api-gw.sports.naver.com/schedule/games/{gid}", n=4000)
    rec = show("naver record", f"https://api-gw.sports.naver.com/schedule/games/{gid}/record", n=200)
    if rec:
        def walk(o, p="", depth=0):
            if depth > 5:
                return
            if isinstance(o, dict):
                for k, v in o.items():
                    t = type(v).__name__
                    ex = "" if isinstance(v, (dict, list)) else repr(v)[:40]
                    print(f"{p}.{k} [{t}] {ex}")
                    walk(v, p + "." + k, depth + 1)
            elif isinstance(o, list) and o:
                print(f"{p}[] len={len(o)}")
                walk(o[0], p + "[0]", depth + 1)
        walk(rec)

# 시즌 범위 확인
show("naver season range", "https://api-gw.sports.naver.com/schedule/games",
     {"fields": "basic", "upperCategoryId": "basketball", "categoryId": "kbl",
      "fromDate": "2026-04-01", "toDate": "2026-05-31", "size": 500}, n=1500)
