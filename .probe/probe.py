import requests, re
S = requests.Session(); S.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124.0"})
def g(u, n=0):
    r = S.get(u, timeout=30)
    if "wkbl" in u: r.encoding = r.apparent_encoding
    print(f"\n### {u} {r.status_code} len={len(r.text)}")
    if n: print(r.text[:n])
    return r.text
t = g("https://www.wkbl.or.kr/game/result.asp")
print("links", sorted(set(re.findall(r'(?:href|location\.href)\s*=\s*["\']([^"\']*(?:result|game|record|box)[^"\']*)', t)))[:40])
print("asp", sorted(set(re.findall(r'["\'](/[a-z_/0-9]+\.asp[^"\']*)', t)))[:40])
print("params", sorted(set(re.findall(r'(?:season_gu|game_no|gun|game_type)[=:][^&"\'<> ]{0,10}', t)))[:30])
t = g("https://www.bleague.jp/schedule/?tab=1&year=2026&event=2&club=&setuFrom=1&setuTo=10")
keys = sorted(set(re.findall(r'ScheduleKey=(\d+)', t))); print("bl keys", keys[:10], len(keys))
if keys:
    h = g(f"https://www.bleague.jp/game_detail/?ScheduleKey={keys[0]}&tab=4")
    for kw in ["BOX SCORE", "box-score", "boxscore", "PTS", "選手"]:
        j = h.find(kw); print("KW", kw, j, re.sub(r"\s+", " ", h[max(j-200,0):j+600]) if j > 0 else "")
    print("api", sorted(set(re.findall(r'https?://[a-z0-9.\-]*(?:bleague|b-league)[^"\'\s<>]{0,120}', h)))[:25])
