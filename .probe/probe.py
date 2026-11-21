import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lmp_statsapi import lmp_fetch
out=[]
for s in (2023,2024,2025,2026): out+=lmp_fetch(season=s)
print("N",len(out))
print("JSON"+json.dumps(out,ensure_ascii=False,separators=(",",":")))
