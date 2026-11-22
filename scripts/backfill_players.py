"""저장된 B리그·WKBL 일별/과거 파일에 선수 박스스코어 채우기 (각 리그 공식 소스)

실행: python scripts/backfill_players.py [BLEAGUE] [WKBL]   (인자 없으면 둘 다)
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from collectors.bleague_official import BLeagueBox  # noqa: E402
from collectors.wkbl_official import WKBLBox  # noqa: E402

SOURCES = {"BLEAGUE": BLeagueBox, "WKBL": WKBLBox}


def run(league: str):
    box = SOURCES[league]()
    total = filled = 0
    for f in sorted(glob.glob(os.path.join(ROOT, "data", league, "*", "*.json"))):
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        games = [g for g in d.get("games", []) if not g.get("home_players")]
        total += len(d.get("games", []))
        if not games:
            continue
        date = d.get("date") or os.path.basename(f)[:8]
        try:
            n = box.fill(date, games)
        except Exception as e:
            print(f"  {date}: 실패 {e}")
            continue
        filled += n
        if n < len(games):
            print(f"  {date}: {n}/{len(games)}경기만 매칭")
        if n:
            with open(f, "w", encoding="utf-8") as fh:
                json.dump(d, fh, ensure_ascii=False, indent=2)
    print(f"[{league}] 경기 {total} / 선수 기록 채움 {filled}")


if __name__ == "__main__":
    for lg in [a.upper() for a in sys.argv[1:]] or list(SOURCES):
        run(lg)
