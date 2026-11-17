"""저장된 B리그 일별/과거 파일에 선수 박스스코어 채우기 (B.LEAGUE 공식 공개 JSON)

실행: python scripts/backfill_bleague_players.py
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from collectors.bleague_official import BLeagueBox  # noqa: E402

box = BLeagueBox()
total = filled = 0
for f in sorted(glob.glob(os.path.join(ROOT, "data", "BLEAGUE", "*", "*.json"))):
    with open(f, encoding="utf-8") as fh:
        d = json.load(fh)
    games = [g for g in d.get("games", []) if not g.get("home_players")]
    total += len(d.get("games", []))
    if not games:
        continue
    date = d.get("date") or os.path.basename(f)[:8]
    n = box.fill(date, games)
    filled += n
    if n < len(games):
        print(f"  {date}: {n}/{len(games)}경기만 매칭")
    if n:
        with open(f, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False, indent=2)
print(f"[BLEAGUE] 경기 {total} / 선수 기록 채움 {filled}")
