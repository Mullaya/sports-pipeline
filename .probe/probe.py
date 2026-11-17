import requests, re
S = requests.Session()
S.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"})
FEED = "https://global.flashscore.ninja/2/x/feed/"
H = {"x-fsign": "SW9D1eZo", "Referer": "https://www.flashscore.com/", "Origin": "https://www.flashscore.com"}

def feed(name):
    try:
        r = S.get(FEED + name, headers=H, timeout=25)
        t = r.text
        print(f"\n=== {name} HTTP {r.status_code} len={len(t)}")
        print(t[:1200].replace("~", "~\n"))
        return t
    except Exception as e:
        print(name, "ERR", e)

# 하키 라인업: 예전 정상(10/24 LIIGA) vs 최근 빈 값(11/15 LIIGA), AHL, ALH
for mid in ["xh92vrFN", "W6vNeb2l", "vPe0FZE8", "SjkNbxqQ"]:
    feed(f"df_li_1_{mid}")
# 하키 선수 스탯 후보 피드
for p in ["df_ps_1_", "df_pls_1_", "df_lis_1_"]:
    feed(p + "W6vNeb2l")
# 농구 선수 박스스코어 후보 (B리그, WKBL)
for mid in ["KWS7pWXr", "AizgjXx2"]:
    for p in ["df_li_1_", "df_ps_1_", "df_pls_1_"]:
        feed(p + mid)

# 공식 소스 접근성
for u in ["https://liiga.fi/api/v2/games/2026/1", "https://www.wkbl.or.kr/game/result.asp",
          "https://www.bleague.jp/game_detail/?ScheduleKey=1", "https://lscluster.hockeytech.com/feed/index.php?feed=modulekit&view=scorebar&key=50c2cd9b5e18e390&client_code=ahl&numberofdaysback=2&numberofdaysahead=0",
          "https://www.shl.se/", "https://www.penny-del.org/"]:
    try:
        r = S.get(u, timeout=25); print("\n###", u, r.status_code, len(r.text)); print(r.text[:500])
    except Exception as e:
        print("\n###", u, "ERR", e)
