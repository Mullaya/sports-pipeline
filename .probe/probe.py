import requests, re
S = requests.Session(); S.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124.0"})
def get(u, **kw):
    r = S.get(u, timeout=30, **kw); r.encoding = "utf-8"; return r.text
for u in ["https://www.wkbl.or.kr/game/sch/schedule1.asp", "https://www.wkbl.or.kr/game/sch/schedule1.asp?gun=1&season_gu=046&ym=202611"]:
    t = get(u); print("\n###", u, len(t))
    print("links", sorted(set(re.findall(r'["\']([^"\']*(?:result|game_no|record)[^"\']*)["\']', t)))[:30])
    print("onclick", sorted(set(re.findall(r'onclick="([^"]{0,120})"', t)))[:20])
    i = t.find("<table"); print(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "|", t[i:i+2000]))[:1200])
t = get("https://www.wkbl.or.kr/game/result.asp")
i = t.find("contents"); print("RESULT body", re.sub(r"\s+", " ", re.sub(r"<(?!a |/a)[^>]+>", "|", t[t.find('<body'):]))[3000:7000])
