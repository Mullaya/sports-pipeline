import os
import json
import requests
from collections import defaultdict
from datetime import datetime

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPOSITORY")

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

def list_files(path: str) -> list:
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code == 200:
        return resp.json()
    return []

def fetch_json(download_url: str) -> dict:
    resp = requests.get(download_url, headers=HEADERS)
    if resp.status_code == 200:
        return resp.json()
    return {}

def build_mlb_stats():
    print("MLB 집계 시작...")

    pitcher_stats = defaultdict(lambda: {
        "name": "",
        "team": "",
        "games": 0,
        "starts": 0,
        "wins": 0,
        "losses": 0,
        "total_ip": 0.0,
        "total_er": 0,
        "total_h": 0,
        "total_bb": 0,
        "total_k": 0,
        "total_pitches": 0,
        "era": 0.0,
        "whip": 0.0,
        "k9": 0.0,
        "bb9": 0.0,
        "last5": [],
        "last10": [],
        "home_er": 0, "home_ip": 0.0, "home_games": 0,
        "away_er": 0, "away_ip": 0.0, "away_games": 0,
        "vs_teams": defaultdict(lambda: {"games": 0, "er": 0, "ip": 0.0})
    })

    batter_stats = defaultdict(lambda: {
        "name": "",
        "team": "",
        "games": 0,
        "total_ab": 0,
        "total_h": 0,
        "total_hr": 0,
        "total_rbi": 0,
        "total_bb": 0,
        "total_k": 0,
        "avg": 0.0,
        "obp": 0.0,
        "slg": 0.0,
        "last10_h": 0,
        "last10_ab": 0,
        "last10": []
    })

    team_stats = defaultdict(lambda: {
        "team": "",
        "games": 0,
        "wins": 0,
        "losses": 0,
        "total_runs": 0,
        "total_allowed": 0,
        "last10": [],
        "home_wins": 0, "home_losses": 0,
        "away_wins": 0, "away_losses": 0,
        "run_diff": 0
    })

    # daily 폴더 파일 목록
    files = list_files("data/MLB/daily")
    files += list_files("data/MLB/historical")
    print(f"  총 {len(files)}개 파일 처리")

    for f in sorted(files, key=lambda x: x["name"]):
        if not f["name"].endswith(".json"):
            continue

        data = fetch_json(f["download_url"])
        if not data or not data.get("games"):
            continue

        date = data.get("date", "")

        for game in data["games"]:
            home = game.get("home_team", "")
            away = game.get("away_team", "")
            home_score = int(game.get("home_score", 0))
            away_score = int(game.get("away_score", 0))

            # 팀 승패
            for team, runs_for, runs_against, is_home in [
                (home, home_score, away_score, True),
                (away, away_score, home_score, False)
            ]:
                ts = team_stats[team]
                ts["team"] = team
                ts["games"] += 1
                ts["total_runs"] += runs_for
                ts["total_allowed"] += runs_against
                ts["run_diff"] = ts["total_runs"] - ts["total_allowed"]

                won = runs_for > runs_against
                if won:
                    ts["wins"] += 1
                    if is_home:
                        ts["home_wins"] += 1
                    else:
                        ts["away_wins"] += 1
                else:
                    ts["losses"] += 1
                    if is_home:
                        ts["home_losses"] += 1
                    else:
                        ts["away_losses"] += 1

                ts["last10"].append({
                    "date": date,
                    "opponent": away if is_home else home,
                    "runs": runs_for,
                    "allowed": runs_against,
                    "result": "W" if won else "L"
                })
                ts["last10"] = ts["last10"][-10:]

            # 투수
            for side, team, opponent in [
                ("home_pitchers", home, away),
                ("away_pitchers", away, home)
            ]:
                is_home_side = side == "home_pitchers"
                for p in game.get(side, []):
                    name = p.get("name", "")
                    if not name:
                        continue

                    key = f"{team}_{name}"
                    ps = pitcher_stats[key]
                    ps["name"] = name
                    ps["team"] = team

                    # IP 파싱 (예: "6.2" → 6.667)
                    ip_str = str(p.get("ip", "0"))
                    try:
                        if "." in ip_str:
                            parts = ip_str.split(".")
                            ip = int(parts[0]) + int(parts[1]) / 3
                        else:
                            ip = float(ip_str)
                    except Exception:
                        ip = 0.0

                    er = int(p.get("er", 0))
                    h = int(p.get("h", 0))
                    bb = int(p.get("bb", 0))
                    k = int(p.get("k", 0))
                    pitches = int(p.get("pitches", 0))
                    is_starter = p.get("is_starter", False)

                    ps["games"] += 1
                    if is_starter:
                        ps["starts"] += 1
                    ps["total_ip"] += ip
                    ps["total_er"] += er
                    ps["total_h"] += h
                    ps["total_bb"] += bb
                    ps["total_k"] += k
                    ps["total_pitches"] += pitches

                    result = p.get("result", "")
                    if "W" in result:
                        ps["wins"] += 1
                    elif "L" in result:
                        ps["losses"] += 1

                    # 홈/원정 분리
                    if is_home_side:
                        ps["home_er"] += er
                        ps["home_ip"] += ip
                        ps["home_games"] += 1
                    else:
                        ps["away_er"] += er
                        ps["away_ip"] += ip
                        ps["away_games"] += 1

                    # 상대팀별
                    vs = ps["vs_teams"][opponent]
                    vs["games"] += 1
                    vs["er"] += er
                    vs["ip"] += ip

                    # 최근 기록
                    ps["last10"].append({
                        "date": date,
                        "opponent": opponent,
                        "is_starter": is_starter,
                        "ip": round(ip, 2),
                        "er": er,
                        "h": h,
                        "bb": bb,
                        "k": k,
                        "pitches": pitches
                    })
                    ps["last10"] = ps["last10"][-10:]
                    ps["last5"] = ps["last10"][-5:]

            # 타자
            for side, team, opponent in [
                ("home_batters", home, away),
                ("away_batters", away, home)
            ]:
                for b in game.get(side, []):
                    name = b.get("name", "")
                    if not name:
                        continue

                    key = f"{team}_{name}"
                    bs = batter_stats[key]
                    bs["name"] = name
                    bs["team"] = team

                    ab = int(b.get("ab", 0))
                    h = int(b.get("h", 0))
                    hr = int(b.get("hr", 0))
                    rbi = int(b.get("rbi", 0))
                    bb = int(b.get("bb", 0))
                    k = int(b.get("k", 0))

                    bs["games"] += 1
                    bs["total_ab"] += ab
                    bs["total_h"] += h
                    bs["total_hr"] += hr
                    bs["total_rbi"] += rbi
                    bs["total_bb"] += bb
                    bs["total_k"] += k
                    bs["last10_ab"] += ab
                    bs["last10_h"] += h

                    bs["last10"].append({
                        "date": date,
                        "opponent": opponent,
                        "ab": ab,
                        "h": h,
                        "hr": hr,
                        "rbi": rbi,
                        "bb": bb,
                        "k": k
                    })
                    bs["last10"] = bs["last10"][-10:]

    # ERA/WHIP 계산
    for key, ps in pitcher_stats.items():
        ip = ps["total_ip"]
        if ip > 0:
            ps["era"] = round((ps["total_er"] * 9) / ip, 2)
            ps["whip"] = round((ps["total_h"] + ps["total_bb"]) / ip, 2)
            ps["k9"] = round((ps["total_k"] * 9) / ip, 2)
            ps["bb9"] = round((ps["total_bb"] * 9) / ip, 2)
        if ps["home_ip"] > 0:
            ps["home_era"] = round((ps["home_er"] * 9) / ps["home_ip"], 2)
        if ps["away_ip"] > 0:
            ps["away_era"] = round((ps["away_er"] * 9) / ps["away_ip"], 2)

        # vs_teams ERA
        for opp, vs in ps["vs_teams"].items():
            if vs["ip"] > 0:
                vs["era"] = round((vs["er"] * 9) / vs["ip"], 2)

        ps["vs_teams"] = dict(ps["vs_teams"])

    # AVG 계산
    for key, bs in batter_stats.items():
        if bs["total_ab"] > 0:
            bs["avg"] = round(bs["total_h"] / bs["total_ab"], 3)
        if bs["last10_ab"] > 0:
            bs["last10_avg"] = round(bs["last10_h"] / bs["last10_ab"], 3)

    # 팀 승률 계산
    for team, ts in team_stats.items():
        g = ts["games"]
        if g > 0:
            ts["win_pct"] = round(ts["wins"] / g, 3)
            ts["rpg"] = round(ts["total_runs"] / g, 2)
            ts["rapg"] = round(ts["total_allowed"] / g, 2)

    print(f"  투수: {len(pitcher_stats)}명")
    print(f"  타자: {len(batter_stats)}명")
    print(f"  팀: {len(team_stats)}팀")

    return {
        "pitchers": dict(pitcher_stats),
        "batters": dict(batter_stats),
        "teams": dict(team_stats)
    }

def upload_stats(stats: dict, league: str):
    import base64

    path = f"analytics/{league}_stats.json"
    content = json.dumps(stats, ensure_ascii=False, indent=2)
    content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    # 기존 SHA 확인
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    resp = requests.get(url, headers=HEADERS)
    sha = resp.json().get("sha") if resp.status_code == 200 else None

    payload = {
        "message": f"[{league}] 통계 집계 업데이트 {datetime.now().strftime('%Y%m%d')}",
        "content": content_b64,
        "branch": "main"
    }
    if sha:
        payload["sha"] = sha

    resp = requests.put(url, headers=HEADERS, json=payload)
    if resp.status_code in [200, 201]:
        print(f"  ✅ {path} 업로드 완료")
    else:
        print(f"  ❌ 업로드 실패: {resp.status_code}")

if __name__ == "__main__":
    stats = build_mlb_stats()
    upload_stats(stats, "MLB")
    print("완료!")
