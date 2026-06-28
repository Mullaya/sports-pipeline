import requests
from bs4 import BeautifulSoup
import time
from itertools import permutations

class KBOCollector:

    BASE_URL = "https://www.koreabaseball.com"

    HEADERS = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": "https://www.koreabaseball.com/Schedule/GameCenter/Main.aspx",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    TEAM_CODES = {
        "HH": "한화", "OB": "두산", "LG": "LG",
        "SS": "삼성", "SK": "SSG", "KT": "KT",
        "NC": "NC", "HT": "KIA", "LT": "롯데",
        "WO": "키움"
    }

    def get_game_ids(self, date: str) -> list:
        team_codes = list(self.TEAM_CODES.keys())
        found = []

        for away, home in permutations(team_codes, 2):
            game_id = f"{date}{away}{home}0"
            payload = {
                "leId": "1",
                "srId": "0",
                "seasonId": date[:4],
                "gameId": game_id
            }

            try:
                resp = requests.post(
                    f"{self.BASE_URL}/ws/Schedule.asmx/GetScoreBoardScroll",
                    data=payload,
                    headers=self.HEADERS,
                    timeout=5
                )
                text = resp.text.strip()

                if "<ScoreBoard>" in text or "<scoreboard>" in text.lower():
                    found.append(game_id)
                    print(f"    ✅ {game_id}")

            except Exception:
                pass

            time.sleep(0.1)

        print(f"  [KBO] {len(found)}개 경기 발견")
        return found

    def get_boxscore(self, game_id: str) -> dict:
        result = {
            "pitchers": {"home": [], "away": []},
            "batters": {"home": [], "away": []},
            "inning_scores": []
        }

        payload = {
            "leId": "1",
            "srId": "0",
            "seasonId": game_id[:4],
            "gameId": game_id
        }

        # 이닝별 득점
        try:
            resp = requests.post(
                f"{self.BASE_URL}/ws/Schedule.asmx/GetScoreBoardScroll",
                data=payload,
                headers=self.HEADERS,
                timeout=10
            )
            soup = BeautifulSoup(resp.text, "lxml-xml")

            for i, inning in enumerate(soup.find_all("inning"), 1):
                home_s = inning.find("homeScore")
                away_s = inning.find("awayScore")
                result["inning_scores"].append({
                    "inning": i,
                    "home": int(home_s.text) if home_s and home_s.text.isdigit() else 0,
                    "away": int(away_s.text) if away_s and away_s.text.isdigit() else 0
                })

            # 총득점
            total = soup.find("totalScore") or soup.find("TotalScore")
            home_score = 0
            away_score = 0
            if total:
                h = total.find("home") or total.find("homeScore")
                a = total.find("away") or total.find("awayScore")
                if h and h.text.isdigit():
                    home_score = int(h.text)
                if a and a.text.isdigit():
                    away_score = int(a.text)

            result["home_score"] = str(home_score)
            result["away_score"] = str(away_score)

        except Exception as e:
            print(f"  ⚠️ 이닝 수집 오류: {e}")

        # 박스스코어 (투수/타자)
        try:
            resp = requests.post(
                f"{self.BASE_URL}/ws/Schedule.asmx/GetBoxScoreScroll",
                data=payload,
                headers=self.HEADERS,
                timeout=10
            )
            soup = BeautifulSoup(resp.text, "lxml-xml")

            for pitcher in soup.find_all("pitcher"):
                team_type = pitcher.find("teamType")
                side = "home" if team_type and team_type.text == "H" else "away"
                start_yn = pitcher.find("startYn")
                name = pitcher.find("playerName")
                if not name:
                    continue

                result["pitchers"][side].append({
                    "name": name.text,
                    "is_starter": start_yn.text == "Y" if start_yn else False,
                    "result": pitcher.find("pitchResult").text if pitcher.find("pitchResult") else "",
                    "ip": pitcher.find("inning").text if pitcher.find("inning") else "0",
                    "h": pitcher.find("hit").text if pitcher.find("hit") else "0",
                    "hr": pitcher.find("hr").text if pitcher.find("hr") else "0",
                    "bb": pitcher.find("bb").text if pitcher.find("bb") else "0",
                    "k": pitcher.find("kk").text if pitcher.find("kk") else "0",
                    "er": pitcher.find("er").text if pitcher.find("er") else "0",
                    "era": pitcher.find("era").text if pitcher.find("era") else "0.00",
                    "pitches": pitcher.find("pitchCount").text if pitcher.find("pitchCount") else "0"
                })

            for batter in soup.find_all("batter"):
                team_type = batter.find("teamType")
                side = "home" if team_type and team_type.text == "H" else "away"
                name = batter.find("playerName")
                if not name:
                    continue
                order = batter.find("battingOrder")

                result["batters"][side].append({
                    "name": name.text,
                    "order": int(order.text) if order and order.text.isdigit() else 0,
                    "position": batter.find("position").text if batter.find("position") else "",
                    "ab": int(batter.find("ab").text) if batter.find("ab") and batter.find("ab").text.isdigit() else 0,
                    "h": int(batter.find("hit").text) if batter.find("hit") and batter.find("hit").text.isdigit() else 0,
                    "hr": int(batter.find("hr").text) if batter.find("hr") and batter.find("hr").text.isdigit() else 0,
                    "rbi": int(batter.find("rbi").text) if batter.find("rbi") and batter.find("rbi").text.isdigit() else 0,
                    "bb": int(batter.find("bb").text) if batter.find("bb") and batter.find("bb").text.isdigit() else 0,
                    "k": int(batter.find("kk").text) if batter.find("kk") and batter.find("kk").text.isdigit() else 0,
                    "avg": batter.find("avg").text if batter.find("avg") else ".000"
                })

        except Exception as e:
            print(f"  ⚠️ 박스스코어 오류: {e}")

        return result

    def collect_daily(self, date: str) -> dict:
        print(f"[KBO] {date} 수집 시작")

        result = {
            "date": date,
            "league": "KBO",
            "games": []
        }

        game_ids = self.get_game_ids(date)

        if not game_ids:
            print(f"  [KBO] 경기 없음")
            return result

        for game_id in game_ids:
            time.sleep(0.5)
            try:
                away_code = game_id[8:10]
                home_code = game_id[10:12]
                away_team = self.TEAM_CODES.get(away_code, away_code)
                home_team = self.TEAM_CODES.get(home_code, home_code)

                boxscore = self.get_boxscore(game_id)

                home_score = boxscore.get("home_score", "0")
                away_score = boxscore.get("away_score", "0")
                total_runs = int(home_score) + int(away_score)

                home_starter = next(
                    (p for p in boxscore["pitchers"]["home"] if p.get("is_starter")), {}
                )
                away_starter = next(
                    (p for p in boxscore["pitchers"]["away"] if p.get("is_starter")), {}
                )

                game_data = {
                    "game_id": game_id,
                    "date": date,
                    "home_team": home_team,
                    "away_team": away_team,
                    "home_score": home_score,
                    "away_score": away_score,
                    "stadium": "",
                    "status": "종료",
                    "total_runs": total_runs,
                    "winner": home_team if int(home_score) > int(away_score) else away_team,
                    "inning_scores": boxscore["inning_scores"],
                    "home_pitchers": boxscore["pitchers"]["home"],
                    "away_pitchers": boxscore["pitchers"]["away"],
                    "home_batters": boxscore["batters"]["home"],
                    "away_batters": boxscore["batters"]["away"],
                    "home_starter": home_starter,
                    "away_starter": away_starter,
                }
                game_data["summary"] = self._make_summary(game_data)
                result["games"].append(game_data)
                print(
                    f"  ✅ {away_team} vs {home_team} "
                    f"{away_score}-{home_score}"
                )

            except Exception as e:
                print(f"  ❌ {game_id}: {e}")

        return result

    def _make_summary(self, game) -> str:
        h_st = game.get("home_starter", {})
        a_st = game.get("away_starter", {})
        return (
            f"[KBO] {game['home_team']} vs {game['away_team']}\n"
            f"선발: {h_st.get('name','?')}(홈) vs "
            f"{a_st.get('name','?')}(원정)\n"
            f"결과: {game['home_team']} {game['home_score']}-"
            f"{game['away_score']} {game['away_team']}\n"
            f"승자: {game['winner']}\n"
            f"총득점: {game['total_runs']}"
                     )
