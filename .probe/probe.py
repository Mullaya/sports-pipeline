import requests, re
S = requests.Session(); S.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124.0"})
h = S.get("https://www.bleague.jp/game_detail/?ScheduleKey=506601&tab=4", timeout=30).text
for m in re.finditer(r'.{0,200}(?:\$\.ajax|\$\.get|fetch\(|\.json|api/|url\s*:).{0,250}', h):
    print("CTX", re.sub(r"\s+", " ", m.group(0))[:450])
srcs = re.findall(r'<script[^>]+src="([^"]+)"', h); print("SRC", srcs)
for s in srcs:
    if "game" in s.lower() or "detail" in s.lower() or "live" in s.lower():
        u = s if s.startswith("http") else "https://www.bleague.jp" + s
        t = S.get(u, timeout=30).text
        for m in list(re.finditer(r'.{0,150}(?:ajax|url\s*:|fetch\().{0,250}', t))[:8]:
            print("JS", s[-40:], re.sub(r"\s+", " ", m.group(0))[:400])
# WKBL: result 페이지 ajax
r = S.get("https://www.wkbl.or.kr/game/result.asp", timeout=30); r.encoding = "utf-8"; t = r.text
for m in re.finditer(r'.{0,150}(?:\$\.ajax|\.load\(|\$\.post|\$\.get|url\s*:|action=).{0,300}', t):
    print("WK", re.sub(r"\s+", " ", m.group(0))[:450])
