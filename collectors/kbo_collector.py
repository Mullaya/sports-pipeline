import requests
import json
import time

class KBOCollector:

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://sports.naver.com/kbaseball/schedule/index"
    }

    def get_daily_schedule(self, date: str) -> list:
        # YYYYMMDD → YYYY.MM.DD
        fmt = f"{date[:4]}.{date[4:6]}.{date[6:8]}"

        api_url = (
            f"https://sports.naver.com/kbaseball/schedule/index"
            f"?date={fmt}"
        )

        # 네이버 스포츠 경기 목록 API
        schedule_api = (
            f"https://api-gw.sports.naver.com/schedule/games"
            f"?sports=kbo&date={date}&fields=basic,superMatch"
        )

        try:
            resp = requests.get(schedule_api, headers=self.HEADERS, timeout=10)
            data = resp.json()
            games_raw = data.get("result", {}).get("games", [])
        except Exception:
            # 대안 API
            try:
                alt_url = (
                    f"https://sports.news.naver.com/kbaseball/schedule/index"
                    f"?category=kbo&date={date}"
                )
                resp = requests.get(alt_url, headers=self.HEADERS, timeout=10)
                data = resp.json()
                games_raw = data.get("result", {}).get("games", [])
            except Exception as e:
                print(f"  ❌ KBO 스케줄 조회 실패: {e}")
                return []

        games = []
        for game in games_raw:
            status = game.get("statusCode", "")
            if status not in ["FINAL", "POSTPONED_FINAL"]:
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
        # 네이버 스포츠 박스스코어 API
        apis = [
            f"https://api-gw.sports.naver.com/game/{game_id}/record?fields=pitchers,batters,innings",
            f"https://sports.news.naver.com/kbaseball/record/index.nhn?gameId={game_id}"
        ]

        for api_url in apis:
            try:
                resp = requests.get(api_url, headers=self.HEADERS, timeout=10)
                data = resp.json()
                result = data.get("result", {})

                if result:
                    return self._parse_boxscore(result)
            except Exception:
                continue

        return {"pitchers": {"home": [], "away": []},
                "batters": {"home": [], "away": []},
                "inning_scores": []}

    def _parse_boxscore(self, result: dict) -> dict:
        pitchers = {"home": [], "away": []}
        batters = {"home": [], "away": []}
        inning_scores = []

        # 이닝별 득점
        for inning in result.get("innings", []):
            inning_scores.append({
                "inning": inning.get("num", 0),
                "home": inning.get("homeScore", 0),
                "away": inning.get("awayScore", 0)
            })

        # 투수
        for side in ["home", "away"]:
            for p in result.get(f"{side}Pitchers", []):
                pitchers[side].append({
                    "name": p.get("playerName", ""),
                    "is_starter": p.get("startYn", "N") == "Y",
                    "result": p.get("pitchResult", ""),
                    "ip": p.get("inning", "0"),
                    "h": str(p.get("hit", 0)),
                    "bb": str(p.get("baseOnBall", 0)),
                    "k": str(p.get("strikeOut", 0)),
                    "er": str(p.get("earnedRun", 0)),
                    "era": str(p.get("era", "0.00")),
                    "pitches": p.get("pitchCount", 0)
                })

        # 타자
        for side in ["home", "away"]:
            for order, b in enumerate(result.get(f"{side}Batters", []), 1):
                batters[side].append({
                    "name": b.get("playerName", ""),
                    "order": order,
                    "position": b.get("position", ""),
                    "ab": b.get("ab", 0),
                    "h": b.get("hit", 0),
                    "hr": b.get("hr", 0),
                    "rbi": b.get("rbi", 0),
                    "bb": b.get("baseOnBall", 0),
                    "k": b.get("strikeOut", 0),
                    "avg": str(b.get("avg", ".000"))
                })

        return {
            "pitchers": pitchers,
            "batters": batters,
            "inning_scores": inning_scores
        }

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
                boxscore = {
                    "pitchers": {"home": [], "away": []},
                    "batters": {"home": [], "away": []},
                    "inning_scores": []
                }

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
                "inning_scores": boxscore["inning_scores"],
                "home_pitchers": boxscore["pitchers"]["home"],
                "away_pitchers": boxscore["pitchers"]["away"],
                "home_batters": boxscore["batters"]["home"],
                "away_batters": boxscore["batters"]["away"],
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
