import requests, re, json
S = requests.Session(); S.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124.0"})
for v in ["v2_genius_contexts", "v1_contexts"]:
    u = f"http://b-league.s3.amazonaws.com/web_json/{v}/506601/latestid"
    r = S.get(u, timeout=30); print("###", u, r.status_code, r.text[:200])
    if r.status_code == 200:
        lid = re.sub(r"\D", "", r.text) or "0"
        j = S.get(f"http://b-league.s3.amazonaws.com/web_json/{v}/506601/{lid}.json", timeout=30)
        print("json", j.status_code, len(j.text))
        try:
            d = j.json(); print("keys", list(d)[:60])
            for k, x in d.items():
                if isinstance(x, (list, dict)) and len(json.dumps(x)) > 200:
                    print("  ", k, type(x).__name__, json.dumps(x, ensure_ascii=False)[:700])
        except Exception as e: print(e, j.text[:300])
t = S.get("https://www.bleague.jp/schedule/?tab=1&year=2026&event=2&club=&setuFrom=1&setuTo=10", timeout=30).text
for m in list(re.finditer(r'.{0,200}(?:ajax|data_format|url\s*:).{0,300}', t))[:10]: print("SCH", re.sub(r"\s+", " ", m.group(0))[:500])
print(re.findall(r'ScheduleKey=\d+[^"]{0,40}', t)[:5])
print(re.sub(r"\s+"," ",t[t.find('506601')-1500:t.find('506601')+300]))
