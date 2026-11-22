"""멕시코 퍼시픽리그(LMP, Liga Mexicana del Pacífico) 수집기 — MLB StatsAPI sportId=17, leagueId=132

ABL 수집기와 같은 스키마. 파일 날짜 = 멕시코 태평양 현지 날짜(America/Mazatlan, MLB 파일과 같은 '미국식 전날' 기준).
시즌 = 10월~1월(정규 R: 전·후반기 2 vuelta, 포스트시즌 D/L/W), 예고 선발은 StatsAPI에 없음.

Usage:
  python collectors/lmp_statsapi.py season 2025      # 전체 시즌 -> data/LMP/historical
  python collectors/lmp_statsapi.py range 2026-11-01 2026-11-30
"""
import json
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

try:
    from collectors.abl_statsapi import fetch
except ImportError:                       # 스크립트 직접 실행
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from abl_statsapi import fetch

LEAGUE_ID = 132
TZ = ZoneInfo("America/Mazatlan")


def lmp_fetch(**params):
    return fetch(league_id=LEAGUE_ID, tz=TZ, **params)


class LMPCollector:
    """main.py 일별 수집용: 멕시코 현지 날짜 d에 시작한 종료 경기만 반환"""
    def collect_daily(self, d: str) -> dict:
        day = datetime.strptime(d, "%Y%m%d")
        gs = lmp_fetch(startDate=(day - timedelta(days=1)).strftime("%Y-%m-%d"),
                       endDate=(day + timedelta(days=1)).strftime("%Y-%m-%d"))
        gs = [g for g in gs if g["date_local"] == d and g["total_runs"] is not None]
        return {"date": d, "league": "LMP", "games": sorted(gs, key=lambda x: x["start_utc"])}


def write(games, kind, root="data/LMP"):
    by = {}
    for g in games:
        if g["total_runs"] is None:
            continue
        by.setdefault(g["date_local"], []).append(g)
    os.makedirs(f"{root}/{kind}", exist_ok=True)
    for d, gs in sorted(by.items()):
        with open(f"{root}/{kind}/{d} lmp.json", "w", encoding="utf-8") as f:
            json.dump({"date": d, "league": "LMP", "games": sorted(gs, key=lambda x: x["start_utc"])},
                      f, ensure_ascii=False, indent=2)
    return len(by)


if __name__ == "__main__":
    mode = sys.argv[1]
    gs = lmp_fetch(season=sys.argv[2]) if mode == "season" else lmp_fetch(startDate=sys.argv[2], endDate=sys.argv[3])
    print("days", write(gs, "historical"), "games", len(gs))
