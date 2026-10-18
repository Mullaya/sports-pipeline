import re,requests,collections
UA={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
for slug in ["khl-2025-2026","khl"]:
    t=requests.get(f"https://www.flashscore.com/hockey/russia/{slug}/results/",headers=UA,timeout=30).text
    m=re.search(r'initialFeeds\["summary-results"\]\s*=\s*\{\s*data:\s*`(.*?)`',t,re.S)
    names=collections.Counter(re.findall(r'(?:AE|AF)÷([^¬]+)',m.group(1)))
    za=sorted(set(re.findall(r'ZA÷([^¬]+)',m.group(1))))
    print(slug,"seasonId",re.search(r"seasonId:\s*(\d+)",t).group(1),za); print(sorted(names))
