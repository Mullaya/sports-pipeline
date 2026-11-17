import requests, re, json, collections as C
S = requests.Session(); S.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124.0"})
lid = re.sub(r"\D", "", S.get("http://b-league.s3.amazonaws.com/web_json/v2_genius_contexts/506601/latestid", timeout=30).text)
d = S.get(f"http://b-league.s3.amazonaws.com/web_json/v2_genius_contexts/506601/{lid}.json", timeout=30).json()
print("PeriodCategory", C.Counter(x["PeriodCategory"] for x in d["HomeBoxscores"]))
print("Game", json.dumps({k: v for k, v in d["Game"].items() if not k.startswith(("Sub", "Commission", "Referee"))}, ensure_ascii=False)[:1500])
tot = [x for x in d["HomeBoxscores"] if x["PeriodCategory"] == max(y["PeriodCategory"] for y in d["HomeBoxscores"])]
print("TOT sample", json.dumps(tot[:2], ensure_ascii=False)[:900])
t = S.get("https://www.bleague.jp/schedule/?tab=1&year=2026&event=2&club=&setuFrom=1&setuTo=10", timeout=30).text
i = t.find("function getQuery"); print("GQ", re.sub(r"\s+", " ", t[i:i+900]))
for q in ["data_format=json&tab=1&year=2026&mon=11&day=16&event=2&club=&ha=&fb=&index=1",
          "data_format=json&tab=1&year=2026&mon=11&day=16&event=2&index=0"]:
    r = S.get("https://www.bleague.jp/schedule/?" + q, timeout=30); print("\nQ", q, r.status_code, len(r.text))
    try:
        j = r.json(); print(list(j)); s = json.dumps(j, ensure_ascii=False); print(sorted(set(re.findall(r'ScheduleKey=(\d+)', s)))[:20])
    except Exception: print(r.text[:300])
