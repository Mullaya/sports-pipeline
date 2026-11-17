import requests, re
S = requests.Session(); S.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124.0"})
def get(u, **kw):
    r = S.get(u, timeout=30, **kw); r.encoding = "utf-8"; return r.text
t = get("https://www.wkbl.or.kr/game/result.asp?season_gu=047&gun=1&game_type=01&game_no=14&viewType=2")
print(len(t), "tables", t.count("<table"))
for m in re.finditer(r'(?:\$\.ajax|\.load\(|url\s*:|\$\.post|\$\.get)[^;]{0,300}', t): print("AJ", re.sub(r"\s+", " ", m.group(0))[:300])
body = t[t.find('id="contents"'):] if 'id="contents"' in t else t[t.find('<body'):]
txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "|", body))
i = txt.find("득점"); print("TXT", txt[max(0,i-1500):i+3000])
for m in list(re.finditer(r'<table[^>]*>', t))[:8]: print("TB", m.group(0), re.sub(r"\s+"," ",re.sub(r"<[^>]+>","|",t[m.end():m.end()+600]))[:300])
