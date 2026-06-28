import requests
from bs4 import BeautifulSoup
import time

class NPBCollector:

    BASE_URL = "https://npb.jp"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ja-JP,ja;q=0.9"
    }

    def get_daily_scores(self, date: str) -> dict:
        year = date[:4]
        month = date[4:6]
        day = date[6:8]

        url = f"{self.BASE_URL}/scores/{year}/{month}{day}/"

        resp = requests.get(url, headers=self.HEADERS, timeout=10)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        result = {
            "date": date,
            "league": "NPB",
            "games": []
        }

        game_boxes = soup.find_all("section", class_="bb-score")
        if not game_boxes:
            game_boxes = soup.find_all("div", class_="scoreBoard")

        for box in game_boxes:
            game_data = self._parse_game(box, date)
            if game_data:
                result["games"].append(game_data)
                print(f"  ✅ {game_data['away_team']} vs {game_data['home_team']} "
                      f"{game_data['away_score']}-{game_data['home_score']}")

        return result

    def _parse_game(self, box, date: str) -> dict:
        try:
            # 팀명
            teams = box.find_all("p", class_="bb-score__team")
            if len(teams) < 2:
                teams = box.find_all("td", class_="team")
            if len(teams) < 2:
                return None

            away_team = teams[0].text.strip()
            home_team = teams[1].text.strip()

            # 총득점
            scores = box.find_all("p", class_="bb-score__runs")
            if not scores or len(scores) < 2:
                scores = box.find_all("td", class_="runs")
            if len(scores) < 2:
                return None

            away_score = int(scores[0].text.strip())
            home_score = int(scores[1].text.strip())
            total_runs = home_score + away_score

            # 선발투수
            pitchers = box.find_all("dd", class_="bb-score__pitcher")
            away_starter = pitchers[0].text.strip() if len(pitchers) > 0 else "미상"
            home_starter = pitchers[1].text.strip() if len(pitchers) > 1 else "미상"

            # 승패투수
            win_p = box.find("span", class_="bb-score__win")
            lose_p = box.find("span", class_="bb-score__lose")
            win_pitcher = win_p.text.strip() if win_p else ""
            lose_pitcher = lose_p.text.strip() if lose_p else ""

            return {
                "date": date,
                "home_team": home_team,
                "away_team": away_team,
                "home_score": home_score,
                "away_score": away_score,
                "total_runs": total_runs,
                "winner": home_team if home_score > away_score else away_team,
                "home_starter": home_starter,
                "away_starter": away_starter,
                "win_pitcher": win_pitcher,
                "lose_pitcher": lose_pitcher,
                "summary": self._make_summary(
                    home_team, away_team,
                    home_score, away_score,
                    home_starter, away_starter,
                    total_runs
                )
            }

        except Exception as e:
            print(f"  ⚠️ NPB 파싱 오류: {e}")
            return None

    def collect_daily(self, date: str) -> dict:
        print(f"[NPB] {date} 수집 시작")
        data = self.get_daily_scores(date)
        return data

    def _make_summary(self, home, away, hs, as_, h_st, a_st, total) -> str:
        return (
            f"[NPB] {home} vs {away}\n"
            f"선발: {h_st}(홈) vs {a_st}(원정)\n"
            f"결과: {home} {hs}-{as_} {away}\n"
            f"승자: {home if hs > as_ else away}\n"
            f"총득점: {total}"
        )
