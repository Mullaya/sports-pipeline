import requests, re, html as H
S = requests.Session(); S.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124.0"})
r = S.get("https://www.wkbl.or.kr/game/result.asp", timeout=30); r.encoding = r.apparent_encoding; t = r.text
for m in re.finditer(r'<form.{0,600}', t, re.S): print("FORM", re.sub(r"\s+", " ", m.group(0))[:600])
for m in re.finditer(r'<select.{0,500}', t, re.S): print("SEL", re.sub(r"\s+", " ", m.group(0))[:400])
for m in re.finditer(r'function\s+\w+\([^)]*\)\s*\{.{0,300}', t, re.S): print("FN", re.sub(r"\s+", " ", m.group(0))[:300])
i = t.find("<table"); print("TABLE", re.sub(r"\s+", " ", t[i:i+1500]))
h = S.get("https://www.bleague.jp/game_detail/?ScheduleKey=506601&tab=4", timeout=30).text
for pat in [r"var\s+\w+\s*=\s*[\[{].{0,200}", r"JSON\.parse\(.{0,200}", r"window\.\w+\s*=\s*[\[{].{0,200}"]:
    for m in list(re.finditer(pat, h, re.S))[:6]: print("JS", re.sub(r"\s+", " ", m.group(0))[:250])
i = h.find('data-tab="boxscore"', h.find('data-tab="boxscore"') + 10)
j = h.find("<table", i); print("BOX at", i, j)
seg = h[j:j+6000]
print(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "|", seg))[:2500])
print("tables", h.count("<table"))
