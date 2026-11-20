"""Australian Baseball League collector (MLB StatsAPI, sportId=17, leagueId=595).

Usage:
  python collectors/abl_statsapi.py daily            # yesterday..today (KST) -> data/ABL/daily
  python collectors/abl_statsapi.py season 2025      # full season -> data/ABL/historical
  python collectors/abl_statsapi.py range 2026-11-01 2026-11-30
Files: data/ABL/<daily|historical>/<YYYYMMDD> abl.json, date = KST local date of first pitch.
"""
import json, os, sys
from datetime import datetime, timedelta, timezone
import requests

API = "https://statsapi.mlb.com/api/v1"
SPORT, LEAGUE = 17, 595
KST = timezone(timedelta(hours=9))
HYDRATE = "linescore,decisions,probablePitcher,venue"


def _get(path, **params):
    r = requests.get(f"{API}/{path}", params=params, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return r.json()


def normalize(g):
    a, h = g["teams"]["away"], g["teams"]["home"]
    ls = g.get("linescore") or {}
    dt = datetime.fromisoformat(g["gameDate"].replace("Z", "+00:00"))
    innings = [{"inning": i.get("num"),
                "home": (i.get("home") or {}).get("runs"), "away": (i.get("away") or {}).get("runs"),
                "home_hits": (i.get("home") or {}).get("hits"), "away_hits": (i.get("away") or {}).get("hits")}
               for i in ls.get("innings", [])]
    hs, as_ = h.get("score"), a.get("score")
    dec = g.get("decisions") or {}
    final = g["status"]["abstractGameState"] == "Final"
    return {
        "game_id": g["gamePk"], "season": int(g.get("season") or dt.year), "game_type": g.get("gameType"),
        "status": g["status"]["detailedState"], "start_utc": g["gameDate"], "date_kst": dt.astimezone(KST).strftime("%Y%m%d"),
        "double_header": g.get("doubleHeader"), "game_number": g.get("gameNumber"),
        "scheduled_innings": ls.get("scheduledInnings", g.get("scheduledInnings")),
        "venue": (g.get("venue") or {}).get("name"),
        "home_team": h["team"]["name"], "away_team": a["team"]["name"],
        "home_score": hs if final else None, "away_score": as_ if final else None,
        "total_runs": (hs + as_) if final and hs is not None and as_ is not None else None,
        "winner": (h["team"]["name"] if hs > as_ else a["team"]["name"]) if final and hs is not None and as_ is not None and hs != as_ else None,
        "innings_played": ls.get("currentInning") if final else None,
        "home_hits": ((ls.get("teams") or {}).get("home") or {}).get("hits"),
        "away_hits": ((ls.get("teams") or {}).get("away") or {}).get("hits"),
        "home_errors": ((ls.get("teams") or {}).get("home") or {}).get("errors"),
        "away_errors": ((ls.get("teams") or {}).get("away") or {}).get("errors"),
        "home_probable": (h.get("probablePitcher") or {}).get("fullName"),
        "away_probable": (a.get("probablePitcher") or {}).get("fullName"),
        "winning_pitcher": (dec.get("winner") or {}).get("fullName"),
        "losing_pitcher": (dec.get("loser") or {}).get("fullName"),
        "inning_scores": innings,
    }


def fetch(**params):
    r = _get("schedule", sportId=SPORT, leagueId=LEAGUE, hydrate=HYDRATE, **params)
    return [normalize(g) for d in r.get("dates", []) for g in d["games"]]


class ABLCollector:
    """main.py 일별 수집용: KST 날짜 d에 시작한 경기만 반환."""
    def collect_daily(self, d: str) -> dict:
        day = datetime.strptime(d, "%Y%m%d")
        gs = fetch(startDate=(day - timedelta(days=1)).strftime("%Y-%m-%d"),
                   endDate=(day + timedelta(days=1)).strftime("%Y-%m-%d"))
        gs = [g for g in gs if g["date_kst"] == d and g["status"] not in ("Scheduled", "Pre-Game")]
        return {"date": d, "league": "ABL", "games": sorted(gs, key=lambda x: x["start_utc"])}


def write(games, kind, root="data/ABL"):
    by = {}
    for g in games:
        by.setdefault(g["date_kst"], []).append(g)
    os.makedirs(f"{root}/{kind}", exist_ok=True)
    for d, gs in sorted(by.items()):
        with open(f"{root}/{kind}/{d} abl.json", "w", encoding="utf-8") as f:
            json.dump({"date": d, "league": "ABL", "games": sorted(gs, key=lambda x: x["start_utc"])}, f, ensure_ascii=False, indent=2)
    return len(by)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "daily"
    if mode == "season":
        gs = fetch(season=sys.argv[2]); print("days", write(gs, "historical"), "games", len(gs))
    elif mode == "range":
        gs = fetch(startDate=sys.argv[2], endDate=sys.argv[3]); print("days", write(gs, "historical"), "games", len(gs))
    else:
        now = datetime.now(KST)
        gs = fetch(startDate=(now - timedelta(days=2)).strftime("%Y-%m-%d"), endDate=(now + timedelta(days=1)).strftime("%Y-%m-%d"))
        print("days", write(gs, "daily"), "games", len(gs))
