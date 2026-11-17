import requests, re
S = requests.Session(); S.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124.0"})
h = S.get("https://www.bleague.jp/game_detail/?ScheduleKey=506601&tab=4", timeout=30).text
src = [s for s in re.findall(r'<script[^>]+src="([^"]+)"', h) if "genius_game" in s][0]
t = S.get(src, timeout=30).text
for m in re.finditer(r'.{0,500}url_txt\s*=.{0,300}', t): print("URL", re.sub(r"\s+", " ", m.group(0))[:800])
i = h.find('url: "./"'); print("INLINE", re.sub(r"\s+", " ", h[i-1500:i+800]))
