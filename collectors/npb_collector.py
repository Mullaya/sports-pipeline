import requests
from bs4 import BeautifulSoup
import time

class NPBCollector:

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ja-JP,ja;q=0.9"
    }

    TEAM_MAP = {
        "Giants": "요미우리", "BayStars": "DeNA", "Tigers": "한신",
        "Carp": "히로시마", "Swallows": "야쿠르트", "Dragons": "주니치",
        "Hawks": "소프트뱅크", "Marines": "롯데", "Eagles": "라쿠텐",
        "Lions": "세이부", "Fighters": "닛폰햄", "Buffaloes": "오릭스"
    }

    def collect_daily(self, date: str) -> dict:
        print(f"[NPB] {date} 수집 시작")

        year = date[:4]
        month = date[4:6]
        day = date[6:8]

        url = f"https://npb.jp/scores/{year}/{month}{day}/"

        result = {
            "date": date,
            "league": "NPB",
            "games": []
        }

        try:
            resp = requests.get(url, headers=self.HEADERS, timeout=15)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")
        except Exception as e:
            print(f"  ❌ NPB 페이지 접근 실패: {e}")
            return result

        # NPB 실제 구조: div.scoreBoard 또는 section
        score_tables = soup.find_all("table", class_=lambda x: x and "score" in x.lower())

        if not score_tables:
            # 대안: div 기반 파싱
            score_tables = soup.find_all("div", class_=lambda x: x and "score" in x.lower())

        if not score_tables:
            # 전체 테이블에서 경기 결과 찾기
            all_tables = soup.find_all("table")
            score_tables = [t for t in all_tables if t.find("td")]

        for table in score_tables:
            game_data = self._parse_table(table, date)
            if game_data:
                result["games"].append(game_data)
                print(f"  ✅ {game_data['away_team']} vs {game_data['home_team']} "
                      f"{game_data['away_score']}-{game_data['home_score']}")

        # 파싱 실패시 대안: JSON API 시도
        if not result["games"]:
            result = self._try_json_api(date, result)

        return result

    def _parse_table(self, table, date: str) -> dict:
        try:
            rows = table.find_all("tr")
            if len(rows) < 2:
                return None

            # 팀명 행
            team_cells = []
            for row in rows:
                cells = row.find_all(["th", "td"])
                for cell in cells:
                    text = cell.text.strip()
                    if len(text) > 1 and not text.isdigit():
                        team_cells.append(text)

            if len(team_cells) < 2:
                return None

            # 점수 행
            score_cells = []
            for row in rows:
                cells = row.find_all("td")
                for cell in cells:
                    text = cell.text.strip()
                    if text.isdigit():
                        score_cells.append(int(text))

            if len(score_cells) < 2:
                return None

            away_team = team_cells[0]
            home_team = team_cells[1] if len(team_cells) > 1 else "홈팀"
            away_score = score_cells[-2] if len(score_cells) >= 2 else 0
            home_score = score_cells[-1] if len(score_cells) >= 1 else 0
            total_runs = home_score + away_score

            if total_runs == 0 and away_score == 0:
                return None

            return {
                "date": date,
                "home_team": home_team,
                "away_team": away_team,
                "home_score": home_score,
                "away_score": away_score,
                "total_runs": total_runs,
                "winner": home_team if home_score > away_score else away_team,
                "home_starter": "미상",
                "away_starter": "미상",
                "win_pitcher": "",
                "lose_pitcher": "",
                "summary": self._make_summary(
                    home_team, away_team,
                    home_score, away_score,
                    "미상", "미상", total_runs
                )
            }

        except Exception as e:
            print(f"  ⚠️ NPB 파싱 오류: {e}")
            return None

    def _try_json_api(self, date: str, result: dict) -> dict:
        # NPB 대안 소스: livescore
        try:
            url = f"https://www.livescores.com/baseball/japan-npb/"
            resp = requests.get(url, headers=self.HEADERS, timeout=10)
            # 기본 구조만 반환
            print(f"  ⚠️ NPB 대안 소스 시도 - 파싱 필요")
        except Exception as e:
            print(f"  ❌ NPB 대안 소스 실패: {e}")

        return result

    def _make_summary(self, home, away, hs, as_, h_st, a_st, total) -> str:
        return (
            f"[NPB] {home} vs {away}\n"
            f"선발: {h_st}(홈) vs {a_st}(원정)\n"
            f"결과: {home} {hs}-{as_} {away}\n"
            f"승자: {home if hs > as_ else away}\n"
            f"총득점: {total}"
        )
