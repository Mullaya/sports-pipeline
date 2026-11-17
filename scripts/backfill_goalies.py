"""저장된 일별/과거 하키 파일의 빈 골리 기록을 공식 소스로 채운다 (Flashscore 라인업 피드 중단 대응)

실행: python scripts/backfill_goalies.py LIIGA AHL [--force]
  --force : 기존 골리 기록도 공식 소스로 교체 (LIIGA는 선수 ID 체계를 통일하려고 기본 적용)
결과는 data/{LEAGUE}/{daily,historical}/*.json 을 제자리에서 수정한다.
LIIGA는 교체 전 Flashscore 선발과 공식 API 선발 이름이 같은지 비교해 일치율을 출력한다(검증용).
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from collectors.flashscore_hockey_collector import FlashscoreHockeyCollector  # noqa: E402


def last_name(n: str) -> str:
    return (n or "").split(" ")[0].lower()


def run(league: str, force: bool):
    col = FlashscoreHockeyCollector(league)
    files = sorted(glob.glob(os.path.join(ROOT, "data", league, "historical", "*.json")) +
                   glob.glob(os.path.join(ROOT, "data", league, "daily", "*.json")))
    total = filled = missing = same = compared = 0
    for f in files:
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        changed = False
        for g in d.get("games", []):
            if g.get("game_type") in ("EXHIB",):
                continue
            total += 1
            had = g.get("home_goalies") and g.get("away_goalies")
            if had and not force:
                continue
            old = {s: (g.get(f"{s}_goalies") or [{}])[0].get("name") for s in ("home", "away")}
            keep = {s: g.get(f"{s}_goalies") for s in ("home", "away")}
            g["home_goalies"], g["away_goalies"] = [], []
            if col.fill_goalies(g):
                filled += 1
                changed = True
                for s in ("home", "away"):
                    new = (g.get(f"{s}_goalies") or [{}])[0].get("name")
                    if old[s] and new:
                        compared += 1
                        same += last_name(old[s]) == last_name(new)
            else:
                g["home_goalies"], g["away_goalies"] = keep["home"] or [], keep["away"] or []
                missing += 1
                print(f"  매칭 실패 {os.path.basename(f)} {g['away_team']} @ {g['home_team']}")
        if changed:
            with open(f, "w", encoding="utf-8") as fh:
                json.dump(d, fh, ensure_ascii=False, indent=2)
    print(f"[{league}] 경기 {total} / 채움 {filled} / 실패 {missing}"
          + (f" / 기존 선발과 일치 {same}/{compared}" if compared else ""))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    for lg in args or ["LIIGA", "AHL"]:
        run(lg.upper(), force="--force" in sys.argv or lg.upper() == "LIIGA")
