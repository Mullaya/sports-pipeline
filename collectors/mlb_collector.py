import statsapi
import time

class MLBCollector:

    def collect_daily(self, date: str) -> dict:
        print(f"[MLB] {date} 수집 시작")

        # YYYYMMDD → YYYY-MM-DD
        fmt_date = f"{date[:4]}-{date[4:6]}-{date[6:8]}"

        result = {
            "date": date,
            "league": "MLB",
            "games": []
        }

        try:
            schedule = statsapi.schedule(date=fmt_date)
        except Exception as e:
            print(f"  ❌ MLB 스케줄 조회 실패: {e}")
            return result

        for game in schedule:
            if game["status"] != "Final":
                continue

            time.sleep(0.3)

            try:
                game_data = self._parse_game(game)
                result["games"].append(game_data)
                print(f"  ✅ {game_data['away_team']} vs {game_data['home_team']} "
                      f"{game_data['away_score']}-{game_data['home_score']}")
            except Exception as e:
                print(f"  ⚠️ 파싱 오류 game_id {game.get('game_id')}: {e}")

        return result

    def _parse_game(self, game: dict) -> dict:
        home_score = game.get("home_score", 0)
        away_score = game.get("away_score", 0)
        total_runs = home_score + away_score

        home_starter = game.get("home_probable_pitcher", "미상")
        away_starter = game.get("away_probable_pitcher", "미상")

        # 박스스코어에서 선발 ERA 등 추가 수집
        try:
            box = statsapi.boxscore_data(game["game_id"])
            h_pitchers = box.get("home", {}).get("pitchers", [])
            a_pitchers = box.get("away", {}).get("pitchers", [])

            home_starter_stats = self._get_starter_stats(
                box, h_pitchers, "home"
            )
            away_starter_stats = self._get_starter_stats(
                box, a_pitchers, "away"
            )
        except Exception:
            home_starter_stats = {}
            away_starter_stats = {}

        return {
            "game_id": game.get("game_id"),
            "home_team": game.get("home_name"),
            "away_team": game.get("away_name"),
            "home_score": home_score,
            "away_score": away_score,
            "total_runs": total_runs,
            "winner": game.get("home_name") if home_score > away_score else game.get("away_name"),
            "venue": game.get("venue_name", ""),
            "home_starter": home_starter,
            "away_starter": away_starter,
            "home_starter_stats": home_starter_stats,
            "away_starter_stats": away_starter_stats,
            "summary": self._make_summary(
                game.get("home_name"), game.get("away_name"),
                home_score, away_score,
                home_starter, away_starter,
                total_runs, game.get("venue_name", "")
            )
        }

    def _get_starter_stats(self, box, pitchers, side) -> dict:
        if not pitchers:
            return {}
        starter_id = pitchers[0]
        players = box.get(side, {}).get("players", {})
        starter = players.get(f"ID{starter_id}", {})
        stats = starter.get("stats", {}).get("pitching", {})
        return {
            "name": starter.get("person", {}).get("fullName", "미상"),
            "ip": stats.get("inningsPitched", "0"),
            "h": stats.get("hits", 0),
            "bb": stats.get("baseOnBalls", 0),
            "k": stats.get("strikeOuts", 0),
            "er": stats.get("earnedRuns", 0),
            "era": stats.get("era", "0.00")
        }

    def _make_summary(self, home, away, hs, as_,
                      h_st, a_st, total, venue) -> str:
        return (
            f"[MLB] {home} vs {away}\n"
            f"선발: {h_st}(홈) vs {a_st}(원정)\n"
            f"결과: {home} {hs}-{as_} {away}\n"
            f"승자: {home if hs > as_ else away}\n"
            f"총득점: {total}\n"
            f"구장: {venue}"
        )
