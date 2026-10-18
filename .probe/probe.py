import re,requests,time
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
def cnt(url,hdr=None):
    h={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml","Accept-Language":"en-US,en;q=0.9"}
    if hdr: h.update(hdr)
    t=requests.get(url,headers=h,timeout=30).text
    m=re.search(r'initialFeeds\["summary-results"\]\s*=\s*\{\s*data:\s*`(.*?)`',t,re.S)
    n=m.group(1).count("~AA÷") if m else -1
    ads=[int(x) for x in re.findall(r'AD÷(\d+)',m.group(1))] if m else []
    return n,len(t),(min(ads),max(ads)) if ads else None
for u in ["https://www.flashscore.com/hockey/germany/del-2025-2026/results/",
          "https://www.flashscore.de/eishockey/deutschland/del-2025-2026/ergebnisse/",
          "https://www.flashscore.co.uk/hockey/germany/del-2025-2026/results/",
          "https://www.livesport.cz/hokej/nemecko/del-2025-2026/vysledky/",
          "https://www.flashscore.com/hockey/czech-republic/extraliga-2025-2026/results/",
          "https://www.livesport.cz/hokej/cesko/extraliga-2025-2026/vysledky/"]:
    for i in range(2):
        try: print(cnt(u), u.split('/')[2], u.split('/')[-3]); time.sleep(1)
        except Exception as e: print("ERR",u,e)
print("UA variants")
for ua in ["Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile Safari/604.1","Googlebot/2.1 (+http://www.google.com/bot.html)"]:
    print(cnt("https://www.flashscore.com/hockey/germany/del-2025-2026/results/",{"User-Agent":ua}), ua[:20])
