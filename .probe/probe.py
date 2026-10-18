import re,requests
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
t=requests.get("https://www.flashscore.com/hockey/germany/del-2025-2026/results/",headers={"User-Agent":UA},timeout=30).text
pos=[m.start() for m in re.finditer("~AA÷",t)]
print("total AA",len(pos))
# group by containing script/feed key
keys=[(m.start(),m.group(0)) for m in re.finditer(r'initialFeeds\[[^\]]+\]|<script[^>]*>|var \w+\s*=|window\.\w+\s*=|"\w+"\s*:\s*`',t)]
import bisect
starts=[k[0] for k in keys]
groups={}
for p in pos:
    i=bisect.bisect(starts,p)-1
    k=keys[i] if i>=0 else (0,"?")
    groups.setdefault((k[0],k[1]),[]).append(p)
for (s,k),ps in sorted(groups.items()):
    print(k[:60], s, len(ps), "ctx:", t[s:s+300].replace("\n"," ")[:300])
