"""KBL 데이터 소스 구조 확인용 임시 프로브 (작업 후 삭제)"""
import json
import requests

S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
    "Referer": "https://m.sports.naver.com/basketball/schedule/index",
    "Origin": "https://m.sports.naver.com",
})
B = "https://api-gw.sports.naver.com/schedule/games"
GID = "202511013560470150"


def get(url, params=None):
    r = S.get(url, params=params, timeout=20)
    print(f"\n### {url} {params} -> {r.status_code}")
    try:
        return r.json()
    except Exception:
        print(r.text[:300])


def walk(o, p="", depth=0, maxd=7):
    if depth > maxd:
        return
    if isinstance(o, dict):
        for k, v in o.items():
            ex = "" if isinstance(v, (dict, list)) else repr(v)[:50]
            print(f"{p}.{k} [{type(v).__name__}] {ex}")
            walk(v, p + "." + k, depth + 1, maxd)
    elif isinstance(o, list) and o:
        print(f"{p}[] len={len(o)}")
        walk(o[0], p + "[0]", depth + 1, maxd)


g = get(f"{B}/{GID}")
walk(g)
rec = get(f"{B}/{GID}/record")
walk(rec)

# 현재 시즌 / 지난 시즌 범위
for fr, to in (("2025-09-20", "2025-10-10"), ("2026-03-25", "2026-05-31"), ("2026-09-25", "2026-10-31")):
    j = get(B, {"fields": "basic", "categoryId": "kbl", "fromDate": fr, "toDate": to, "size": 500}) or {}
    gs = (j.get("result") or {}).get("games", [])
    print("count", len(gs), "first", gs[0]["gameDate"] if gs else None, "last", gs[-1]["gameDate"] if gs else None)
    for x in gs[:2] + gs[-3:]:
        print("  ", x.get("gameDate"), x.get("homeTeamName"), x.get("awayTeamName"),
              x.get("statusCode"), x.get("homeTeamScore"), x.get("awayTeamScore"),
              {k: x.get(k) for k in x if k not in ("homeTeamEmblemUrl", "awayTeamEmblemUrl")} if x is gs[0] else "")
