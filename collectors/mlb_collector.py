import statsapi
import time

class MLBCollector:

    def collect_daily(self, date: str) -> dict:
        print(f"[MLB] {date} 수집 시작")
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
                print(f"  ⚠️ 파싱 오류 {game.get('game_id')}: {e}")

        return result

    def _parse_game(self, game: dict) -> dict:
        home_score = game.get("home_score", 0)
        away_score = game.get("away_score", 0)
        total_runs = home_score + away_score
        game_id = game["game_id"]

        # 박스스코어 상세 수집
        try:
            box = statsapi.boxscore_data(game_id)
        except Exception:
            box = {}

        # 이닝별 득점
        inning_scores = self._get_inning_scores(game_id)

        # 투수 기록
        home_pitchers = self._get_pitchers(box, "home")
        away_pitchers = self._get_pitchers(box, "away")

        # 타자 기록
        home_batters = self._get_batters(box, "home")
        away_batters = self._get_batters(box, "away")

        return {
            "game_id": game_id,
            "home_team": game.get("home_name"),
            "away_team": game.get("away_name"),
            "home_score": home_score,
            "away_score": away_score,
            "total_runs": total_runs,
            "winner": game.get("home_name") if home_score > away_score else game.get("away_name"),
            "venue": game.get("venue_name", ""),
            "inning_scores": inning_scores,
            "home_pitchers": home_pitchers,
            "away_pitchers": away_pitchers,
            "home_batters": home_batters,
            "away_batters": away_batters,
            "summary": self._make_summary(game, home_pitchers, away_pitchers, total_runs)
        }

    def _get_inning_scores(self, game_id: int) -> list:
        try:
            linescore = statsapi.get("game_linescore", {"gamePk": game_id})
            innings = []
            for inning in linescore.get("innings", []):
                innings.append({
                    "inning": inning.get("num"),
                    "home": inning.get("home", {}).get("runs", 0),
                    "away": inning.get("away", {}).get("runs", 0),
                    "home_hits": inning.get("home", {}).get("hits", 0),
                    "away_hits": inning.get("away", {}).get("hits", 0)
                })
            return innings
        except Exception:
            return []

    def _get_pitchers(self, box: dict, side: str) -> list:
        pitchers = []
        try:
            pitcher_ids = box.get(side, {}).get("pitchers", [])
            players = box.get(side, {}).get("players", {})

            for pid in pitcher_ids:
                player = players.get(f"ID{pid}", {})
                info = player.get("person", {})
                stats = player.get("stats", {}).get("pitching", {})
                season = player.get("seasonStats", {}).get("pitching", {})

                pitchers.append({
                    "name": info.get("fullName", ""),
                    "is_starter": pid == pitcher_ids[0],
                    "result": player.get("stats", {}).get("pitching", {}).get("note", ""),
                    "ip": stats.get("inningsPitched", "0"),
                    "bf": stats.get("battersFaced", 0),
                    "h": stats.get("hits", 0),
                    "hr": stats.get("homeRuns", 0),
                    "bb": stats.get("baseOnBalls", 0),
                    "k": stats.get("strikeOuts", 0),
                    "er": stats.get("earnedRuns", 0),
                    "pitches": stats.get("pitchesThrown", 0),
                    "strikes": stats.get("strikes", 0),
                    "era": season.get("era", "0.00"),
                    "season_k": season.get("strikeOuts", 0),
                    "season_bb": season.get("baseOnBalls", 0),
                    "whip": season.get("whip", "0.00")
                })
        except Exception as e:
            print(f"  ⚠️ 투수 파싱 오류: {e}")
        return pitchers

    def _get_batters(self, box: dict, side: str) -> list:
        batters = []
        try:
            batter_ids = box.get(side, {}).get("batters", [])
            players = box.get(side, {}).get("players", {})

            for order, pid in enumerate(batter_ids, 1):
                player = players.get(f"ID{pid}", {})
                info = player.get("person", {})
                stats = player.get("stats", {}).get("batting", {})
                season = player.get("seasonStats", {}).get("batting", {})
                pos = player.get("position", {}).get("abbreviation", "")

                batters.append({
                    "name": info.get("fullName", ""),
                    "order": order,
                    "position": pos,
                    "ab": stats.get("atBats", 0),
                    "h": stats.get("hits", 0),
                    "hr": stats.get("homeRuns", 0),
                    "rbi": stats.get("rbi", 0),
                    "bb": stats.get("baseOnBalls", 0),
                    "k": stats.get("strikeOuts", 0),
                    "avg": season.get("avg", ".000"),
                    "ops": season.get("ops", ".000"),
                    "season_hr": season.get("homeRuns", 0),
                    "season_rbi": season.get("rbi", 0)
                })
        except Exception as e:
            print(f"  ⚠️ 타자 파싱 오류: {e}")
        return batters

    def _make_summary(self, game, home_pitchers, away_pitchers, total_runs) -> str:
        h_starter = next((p for p in home_pitchers if p["is_starter"]), {})
        a_starter = next((p for p in away_pitchers if p["is_starter"]), {})
        return (
            f"[MLB] {game.get('home_name')} vs {game.get('away_name')}\n"
            f"선발: {h_starter.get('name','?')}(홈) vs {a_starter.get('name','?')}(원정)\n"
            f"결과: {game.get('home_name')} {game.get('home_score')}-"
            f"{game.get('away_score')} {game.get('away_name')}\n"
            f"승자: {game.get('home_name') if game.get('home_score',0) > game.get('away_score',0) else game.get('away_name')}\n"
            f"홈선발: {h_starter.get('ip','?')}이닝 {h_starter.get('er','?')}자책 "
            f"{h_starter.get('k','?')}K {h_starter.get('pitches',0)}구\n"
            f"원정선발: {a_starter.get('ip','?')}이닝 {a_starter.get('er','?')}자책 "
            f"{a_starter.get('k','?')}K {a_starter.get('pitches',0)}구\n"
            f"총득점: {total_runs}\n"
            f"구장: {game.get('venue_name','')}"
        )
