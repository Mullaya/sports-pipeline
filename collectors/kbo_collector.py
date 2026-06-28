import requests
import json
import time
from datetime import datetime

class KBOCollector:

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://sports.naver.com/kbaseball/schedule/index"
    }

    def get_daily_schedule(self, date: str) -> list:
        # date: YYYYMMDD
        url = (
            "https://sports.naver.com/kbaseball/schedule/index"
            f"?date={date}"
        )

        resp = requests.get(url, headers=self.HEADERS, timeout=10)

        # 네이버 스포츠 JSON API
        api_url = (
            "https://api-gw.sports.naver.com/schedule/games"
            f"?sports=kbaseball&date={date}&fields=basic"
        )

        resp = requests.get(api_url, headers=self.HEADERS, timeout=10)
        data = resp.json()

        games = []
        for game in data.get("result", {}).get("games", []):
            if game.get("statusCode") != "FINAL":
                continue
            games.append({
                "game_id": game.get("gameId", ""),
                "home_team": game.get("homeTeamName", ""),
                "away_team": game.get("awayTeamName", ""),
                "home_score": str(game.get("homeTeamScore", 0)),
                "away_score": str(game.get("awayTeamScore", 0)),
                "stadium": game.get("stadiumName", ""),
                "status": "종료"
            })

        return games

    def get_boxscore(self, game_id: str) -> dict:
        api_url = (
            f"https://api-gw.sports.naver.com/schedule/games/{game_id}"
            f"/record?fields=pitchers"
        )

        resp = requests.get(api_url, headers=self.HEADERS, timeout=10)
        data = resp.json()

        pitchers = {"home": [], "away": []}

        result = data.get("result", {})
        for side in ["home", "away"]:
            for p in result.get(f"{side}Pitchers", []):
                pitchers[side].append({
                    "name": p.get("playerName", ""),
                    "result": p.get("pitchResult", ""),
                    "ip": p.get("inning", "0"),
                    "h": str(p.get("hit", 0)),
                    "bb": str(p.get("baseOnBall", 0)),
                    "k": str(p.get("strikeOut", 0)),
                    "er": str(p.get("earnedRun", 0)),
                    "era": str(p.get("era", "0.00")),
                    "is_starter": p.get("startYn", "N") == "Y"
                })

        return {"pitchers": pitchers}

    def collect_daily(self, date: str) -> dict:
        print(f"[KBO] {date} 수집 시작")

        games = self.get_daily_schedule(date)
        result = {
            "date": date,
            "league": "KBO",
            "games": []
        }

        for game in games:
            time.sleep(0.5)

            try:
                boxscore = self.get_boxscore(game["game_id"])
            except Exception as e:
                print(f"  ⚠️ 박스스코어 오류: {e}")
                boxscore = {"pitchers": {"home": [], "away": []}}

            home_score = int(game["home_score"] or 0)
            away_score = int(game["away_score"] or 0)
            total_runs = home_score + away_score

            home_starter = next(
                (p for p in boxscore["pitchers"]["home"] if p["is_starter"]), {}
            )
            away_starter = next(
                (p for p in boxscore["pitchers"]["away"] if p["is_starter"]), {}
            )

            game_data = {
                **game,
                "total_runs": total_runs,
                "winner": game["home_team"] if home_score > away_score else game["away_team"],
                "home_starter": home_starter,
                "away_starter": away_starter,
                "summary": self._make_summary(game, home_starter, away_starter, total_runs)
            }

            result["games"].append(game_data)
            print(f"  ✅ {game['away_team']} vs {game['home_team']} {away_score}-{home_score}")

        return result

    def _make_summary(self, game, home_starter, away_starter, total_runs) -> str:
        return (
            f"[KBO] {game['home_team']} vs {game['away_team']}\n"
            f"선발: {home_starter.get('name','?')}(홈) vs {away_starter.get('name','?')}(원정)\n"
            f"결과: {game['home_team']} {game['home_score']}-{game['away_score']} {game['away_team']}\n"
            f"승자: {game['home_team'] if int(game['home_score'] or 0) > int(game['away_score'] or 0) else game['away_team']}\n"
            f"홈선발: {home_starter.get('ip','?')}이닝 {home_starter.get('er','?')}자책 {home_starter.get('k','?')}K\n"
            f"원정선발: {away_starter.get('ip','?')}이닝 {away_starter.get('er','?')}자책 {away_starter.get('k','?')}K\n"
            f"총득점: {total_runs}\n"
            f"구장: {game['stadium']}"
        )
