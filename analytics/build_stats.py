import os
import json
import requests
import base64
from collections import defaultdict
from datetime import datetime

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPOSITORY")

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# MLB 팀 디비전 매핑
DIVISIONS = {
    "MLB_AL_East": [
        "New York Yankees", "Boston Red Sox", "Tampa Bay Rays",
        "Toronto Blue Jays", "Baltimore Orioles"
    ],
    "MLB_AL_Central": [
        "Chicago White Sox", "Cleveland Guardians", "Detroit Tigers",
        "Kansas City Royals", "Minnesota Twins"
    ],
    "MLB_AL_West": [
        "Houston Astros", "Los Angeles Angels", "Athletics",
        "Seattle Mariners", "Texas Rangers"
    ],
    "MLB_NL_East": [
        "Atlanta Braves", "Miami Marlins", "New York Mets",
        "Philadelphia Phillies", "Washington Nationals"
    ],
    "MLB_NL_Central": [
        "Chicago Cubs", "Cincinnati Reds", "Milwaukee Brewers",
        "Pittsburgh Pirates", "St. Louis Cardinals"
    ],
    "MLB_NL_West": [
        "Arizona Diamondbacks", "Colorado Rockies", "Los Angeles Dodgers",
        "San Diego Padres", "San Francisco Giants"
    ]
}

def get_team_division(team_name: str) -> str:
    for div, teams in DIVISIONS.items():
        for t in teams:
            if t.lower() in team_name.lower() or team_name.lower() in t.lower():
                return div
    return "MLB_AL_East"  # 기본값

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

def build_stats():
    print("MLB 전체 스탯 집계 시작...")

    # 디비전별 데이터 구조
    division_data = {div: {
        "teams": {},
        "pitchers": {},
        "batters": {}
    } for div in DIVISIONS}

    # 팀 초기화
    for div, teams in DIVISIONS.items():
        for team in teams:
            division_data[div]["teams"][team] = {
                "team": team,
                "games": 0,
                "wins": 0,
                "losses": 0,
                "total_runs": 0,
                "total_allowed": 0,
                "win_pct": 0.0,
                "rpg": 0.0,
                "rapg": 0.0,
                "run_diff": 0,
                "home_wins": 0,
                "home_losses": 0,
                "away_wins": 0,
                "away_losses": 0,
                "last10": []
            }

    # 파일 목록
    all_files = []
    for path in ["data/MLB/daily", "data/MLB/historical"]:
        files = list_files(path)
        all_files.extend(files)

    all_files = sorted(all_files, key=lambda x: x["name"])
    print(f"  총 {len(all_files)}개 파일 처리 중...")

    processed = 0
    for f in all_files:
        if not f["name"].endswith(".json"):
            continue

        data = fetch_json(f["download_url"])
        if not data or not data.get("games"):
            continue

        date = data.get("date", "")
        processed += 1

        for game in data["games"]:
            home = game.get("home_team", "")
            away = game.get("away_team", "")
            home_score = int(game.get("home_score", 0))
            away_score = int(game.get("away_score", 0))

            # 팀 승패 기록
            for team, runs_for, runs_against, is_home in [
                (home, home_score, away_score, True),
                (away, away_score, home_score, False)
            ]:
                div = get_team_division(team)
                # 정확한 팀명 매핑
                matched_team = None
                for t in DIVISIONS[div]:
                    if t.lower() in team.lower() or team.lower() in t.lower():
                        matched_team = t
                        break
                if not matched_team:
                    matched_team = team

                if matched_team not in division_data[div]["teams"]:
                    division_data[div]["teams"][matched_team] = {
                        "team": matched_team,
                        "games": 0, "wins": 0, "losses": 0,
                        "total_runs": 0, "total_allowed": 0,
                        "win_pct": 0.0, "rpg": 0.0, "rapg": 0.0,
                        "run_diff": 0, "home_wins": 0, "home_losses": 0,
                        "away_wins": 0, "away_losses": 0, "last10": []
                    }

                ts = division_data[div]["teams"][matched_team]
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

            # 투수 기록
            for side, team, opponent in [
                ("home_pitchers", home, away),
                ("away_pitchers", away, home)
            ]:
                div = get_team_division(team)
                is_home_side = side == "home_pitchers"

                for p in game.get(side, []):
                    name = p.get("name", "")
                    if not name:
                        continue

                    key = name
                    pitchers = division_data[div]["pitchers"]

                    if key not in pitchers:
                        pitchers[key] = {
                            "name": name,
                            "team": team,
                            "games": 0,
                            "starts": 0,
                            "wins": 0,
                            "losses": 0,
                            "total_ip": 0.0,
                            "total_er": 0,
                            "total_h": 0,
                            "total_bb": 0,
                            "total_k": 0,
                            "total_hr": 0,
                            "total_pitches": 0,
                            "era": 0.0,
                            "whip": 0.0,
                            "k9": 0.0,
                            "bb9": 0.0,
                            "hr9": 0.0,
                            "home_ip": 0.0,
                            "home_er": 0,
                            "home_era": 0.0,
                            "away_ip": 0.0,
                            "away_er": 0,
                            "away_era": 0.0,
                            "last5": [],
                            "last10": [],
                            "vs_teams": {}
                        }

                    ps = pitchers[key]
                    ps["team"] = team

                    # IP 파싱
                    ip_str = str(p.get("ip", "0"))
                    try:
                        if "." in ip_str:
                            parts = ip_str.split(".")
                            ip = int(parts[0]) + int(parts[1]) / 3
                        else:
                            ip = float(ip_str)
                    except Exception:
                        ip = 0.0

                    er = int(p.get("er", 0) or 0)
                    h = int(p.get("h", 0) or 0)
                    bb = int(p.get("bb", 0) or 0)
                    k = int(p.get("k", 0) or 0)
                    hr = int(p.get("hr", 0) or 0)
                    pitches = int(p.get("pitches", 0) or 0)
                    is_starter = p.get("is_starter", False)

                    ps["games"] += 1
                    if is_starter:
                        ps["starts"] += 1
                    ps["total_ip"] += ip
                    ps["total_er"] += er
                    ps["total_h"] += h
                    ps["total_bb"] += bb
                    ps["total_k"] += k
                    ps["total_hr"] += hr
                    ps["total_pitches"] += pitches

                    result = p.get("result", "")
                    if result and "W" in str(result):
                        ps["wins"] += 1
                    elif result and "L" in str(result):
                        ps["losses"] += 1

                    if is_home_side:
                        ps["home_ip"] += ip
                        ps["home_er"] += er
                    else:
                        ps["away_ip"] += ip
                        ps["away_er"] += er

                    # 상대팀별
                    if opponent not in ps["vs_teams"]:
                        ps["vs_teams"][opponent] = {
                            "games": 0, "er": 0, "ip": 0.0, "era": 0.0
                        }
                    vs = ps["vs_teams"][opponent]
                    vs["games"] += 1
                    vs["er"] += er
                    vs["ip"] += ip

                    ps["last10"].append({
                        "date": date,
                        "opponent": opponent,
                        "is_starter": is_starter,
                        "ip": round(ip, 2),
                        "er": er,
                        "h": h,
                        "bb": bb,
                        "k": k,
                        "hr": hr,
                        "pitches": pitches
                    })
                    ps["last10"] = ps["last10"][-10:]
                    ps["last5"] = ps["last10"][-5:]

            # 타자 기록
            for side, team, opponent in [
                ("home_batters", home, away),
                ("away_batters", away, home)
            ]:
                div = get_team_division(team)

                for b in game.get(side, []):
                    name = b.get("name", "")
                    if not name:
                        continue

                    key = name
                    batters = division_data[div]["batters"]

                    if key not in batters:
                        batters[key] = {
                            "name": name,
                            "team": team,
                            "games": 0,
                            "total_ab": 0,
                            "total_h": 0,
                            "total_hr": 0,
                            "total_rbi": 0,
                            "total_bb": 0,
                            "total_k": 0,
                            "avg": 0.0,
                            "obp": 0.0,
                            "last10": [],
                            "last10_ab": 0,
                            "last10_h": 0,
                            "last10_avg": 0.0
                        }

                    bs = batters[key]
                    bs["team"] = team

                    ab = int(b.get("ab", 0) or 0)
                    h = int(b.get("h", 0) or 0)
                    hr = int(b.get("hr", 0) or 0)
                    rbi = int(b.get("rbi", 0) or 0)
                    bb = int(b.get("bb", 0) or 0)
                    k = int(b.get("k", 0) or 0)

                    bs["games"] += 1
                    bs["total_ab"] += ab
                    bs["total_h"] += h
                    bs["total_hr"] += hr
                    bs["total_rbi"] += rbi
                    bs["total_bb"] += bb
                    bs["total_k"] += k

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

                    # 최근 10경기 타율
                    recent = bs["last10"]
                    r_ab = sum(g["ab"] for g in recent)
                    r_h = sum(g["h"] for g in recent)
                    bs["last10_ab"] = r_ab
                    bs["last10_h"] = r_h

        if processed % 50 == 0:
            print(f"  {processed}개 파일 처리 완료...")

    # 최종 계산
    for div, data in division_data.items():
        # 팀 승률/득점
        for team, ts in data["teams"].items():
            g = ts["games"]
            if g > 0:
                ts["win_pct"] = round(ts["wins"] / g, 3)
                ts["rpg"] = round(ts["total_runs"] / g, 2)
                ts["rapg"] = round(ts["total_allowed"] / g, 2)

        # 투수 ERA/WHIP
        for name, ps in data["pitchers"].items():
            ip = ps["total_ip"]
            if ip > 0:
                ps["era"] = round((ps["total_er"] * 9) / ip, 2)
                ps["whip"] = round((ps["total_h"] + ps["total_bb"]) / ip, 2)
                ps["k9"] = round((ps["total_k"] * 9) / ip, 2)
                ps["bb9"] = round((ps["total_bb"] * 9) / ip, 2)
                ps["hr9"] = round((ps["total_hr"] * 9) / ip, 2)
            if ps["home_ip"] > 0:
                ps["home_era"] = round((ps["home_er"] * 9) / ps["home_ip"], 2)
            if ps["away_ip"] > 0:
                ps["away_era"] = round((ps["away_er"] * 9) / ps["away_ip"], 2)
            for opp, vs in ps["vs_teams"].items():
                if vs["ip"] > 0:
                    vs["era"] = round((vs["er"] * 9) / vs["ip"], 2)
            ps["total_ip"] = round(ps["total_ip"], 1)

        # 타자 타율
        for name, bs in data["batters"].items():
            if bs["total_ab"] > 0:
                bs["avg"] = round(bs["total_h"] / bs["total_ab"], 3)
                bs["k_pct"] = round(bs["total_k"] / bs["total_ab"], 3)
            if bs["last10_ab"] > 0:
                bs["last10_avg"] = round(bs["last10_h"] / bs["last10_ab"], 3)

    print(f"\n총 {processed}개 파일 처리 완료")
    return division_data

def upload_file(content_str: str, path: str, message: str):
    content_b64 = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    resp = requests.get(url, headers=HEADERS)
    sha = resp.json().get("sha") if resp.status_code == 200 else None

    payload = {
        "message": message,
        "content": content_b64,
        "branch": "main"
    }
    if sha:
        payload["sha"] = sha

    resp = requests.put(url, headers=HEADERS, json=payload)
    if resp.status_code in [200, 201]:
        size_kb = len(content_str) / 1024
        print(f"  ✅ {path} ({size_kb:.1f}KB) 업로드 완료")
    else:
        print(f"  ❌ {path} 업로드 실패: {resp.status_code}")

if __name__ == "__main__":
    division_data = build_stats()
    date_str = datetime.now().strftime("%Y%m%d")

    for div, data in division_data.items():
        content = json.dumps(data, ensure_ascii=False, indent=2)
        upload_file(
            content,
            f"analytics/{div}.json",
            f"[MLB] {div} 스탯 업데이트 {date_str}"
        )

    print("\n✅ 전체 집계 완료!")
