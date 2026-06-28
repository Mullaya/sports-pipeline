import requests
from bs4 import BeautifulSoup
import time

class KBOCollector:

    BASE_URL = "https://www.koreabaseball.com"
    MOBILE_URL = "https://m.koreabaseball.com"

    HEADERS = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": "https://www.koreabaseball.com/Schedule/Schedule.aspx",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    MOBILE_HEADERS = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15",
        "Referer": "https://m.koreabaseball.com"
    }

    TEAM_CODES = {
        "HH": "한화", "OB": "두산", "LG": "LG",
        "SS": "삼성", "SK": "SSG", "KT": "KT",
        "NC": "NC", "HT": "KIA", "LT": "롯데",
        "WO": "키움"
    }

    def get_game_ids(self, date: str) -> list:
        year = date[:4]
        month = date[4:6]
        day = date[6:8]

        date_formats = [
            date,
            f"{year}-{month}-{day}",
            f"{year}.{month}.{day}",
            f"{year}/{month}/{day}",
        ]

        for date_fmt in date_formats:
            payload = {
                "leagueId": "1",
                "seriesId": "0",
                "gameDate": date_fmt
            }

            try:
                resp = requests.post(
                    f"{self.BASE_URL}/ws/Schedule.asmx/GetScheduleList",
                    data=payload,
                    headers=self.HEADERS,
                    timeout=15
                )

                soup = BeautifulSoup(resp.text, "lxml-xml")
                all_games = soup.find_all("game")

                print(f"  [KBO] 날짜형식 {date_fmt} → {len(all_games)}개 경기 발견")

                game_ids = []
                for game in all_games:
                    game_id = game.find("gameId")
                    status = game.find("statusInfo")
                    status_text = status.text if status else ""
                    print(f"    gameId: {game_id.text if game_id else 'N/A'} | status: {status_text}")

                    if game_id and status and status.text == "종료":
                        game_ids.append(game_id.text)

                if game_ids:
                    print(f"  [KBO] gameId {len(game_ids)}개 수집: {game_ids}")
                    return game_ids

            except Exception as e:
                print(f"  ⚠️ {date_fmt} 실패: {e}")
                continue

        print(f"  [KBO] 모든 날짜 형식 실패")
        return []

    def get_game_result(self, game_id: str) -> dict:
        url = (
            f"{self.MOBILE_URL}/Kbo/Live/Record.aspx"
            f"?p_le_id=1&p_sr_id=0&p_g_id={game_id}"
        )

        try:
            resp = requests.get(url, headers=self.MOBILE_HEADERS, timeout=15)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")
        except Exception as e:
            print(f"  ❌ 경기 결과 수집 실패 {game_id}: {e}")
            return {}

        date = game_id[:8]
        away_code = game_id[8:10]
        home_code = game_id[10:12]

        away_team = self.TEAM_CODES.get(away_code, away_code)
        home_team = self.TEAM_CODES.get(home_code, home_code)

        home_score = 0
        away_score = 0

        score_table = soup.find("table", class_="tbl-score")
        if score_table:
            rows = score_table.find_all("tr")
            if len(rows) >= 3:
                try:
                    away_cells = rows[1].find_all("td")
                    home_cells = rows[2].find_all("td")
                    if len(away_cells) >= 3:
                        away_score = int(away_cells[-3].text.strip() or 0)
                    if len(home_cells) >= 3:
                        home_score = int(home_cells[-3].text.strip() or 0)
                except Exception:
                    pass

        inning_scores = self._parse_innings(soup)
        pitchers = self._parse_pitchers(soup)
        batters = self._parse_batters(soup)

        stadium = ""
        stadium_tag = soup.find("span", class_="stadium")
        if stadium_tag:
            stadium = stadium_tag.text.strip()

        return {
            "game_id": game_id,
            "date": date,
            "home_team": home_team,
            "away_team": away_team,
            "home_score": str(home_score),
            "away_score": str(away_score),
            "stadium": stadium,
            "status": "종료",
            "total_runs": home_score + away_score,
            "winner": home_team if home_score > away_score else away_team,
            "inning_scores": inning_scores,
            "home_pitchers": pitchers["home"],
            "away_pitchers": pitchers["away"],
            "home_batters": batters["home"],
            "away_batters": batters["away"],
            "home_starter": next(
                (p for p in pitchers["home"] if p.get("is_starter")), {}
            ),
            "away_starter": next(
                (p for p in pitchers["away"] if p.get("is_starter")), {}
            )
        }

    def _parse_innings(self, soup) -> list:
        inning_scores = []
        try:
            score_table = soup.find("table", class_="tbl-score")
            if not score_table:
                return []

            rows = score_table.find_all("tr")
            if len(rows) < 3:
                return []

            headers = rows[0].find_all(["th", "td"])
            num_innings = len(headers) - 4

            away_cells = rows[1].find_all("td")
            home_cells = rows[2].find_all("td")

            for i in range(min(num_innings, 12)):
                if i >= len(away_cells) or i >= len(home_cells):
                    break
                away_val = away_cells[i].text.strip()
                home_val = home_cells[i].text.strip()
                inning_scores.append({
                    "inning": i + 1,
                    "away": int(away_val) if away_val.isdigit() else 0,
                    "home": int(home_val) if home_val.isdigit() else 0
                })
        except Exception as e:
            print(f"  ⚠️ 이닝 파싱 오류: {e}")
        return inning_scores

    def _parse_pitchers(self, soup) -> dict:
        pitchers = {"home": [], "away": []}
        try:
            tables = soup.find_all("table")
            pitcher_tables = []

            for t in tables:
                headers = [h.text.strip() for h in t.find_all("th")]
                if "이닝" in headers and "자책" in headers:
                    pitcher_tables.append(t)

            sides = ["away", "home"]
            for idx, table in enumerate(pitcher_tables[:2]):
                side = sides[idx]
                rows = table.find_all("tr")[1:]
                is_first = True

                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) < 3:
                        continue

                    name = cells[0].text.strip()
                    if not name:
                        continue

                    result_text = cells[1].text.strip() if len(cells) > 1 else ""
                    ip = cells[2].text.strip() if len(cells) > 2 else "0"
                    h = cells[4].text.strip() if len(cells) > 4 else "0"
                    hr = cells[5].text.strip() if len(cells) > 5 else "0"
                    bb = cells[6].text.strip() if len(cells) > 6 else "0"
                    k = cells[7].text.strip() if len(cells) > 7 else "0"
                    er = cells[8].text.strip() if len(cells) > 8 else "0"
                    era = cells[9].text.strip() if len(cells) > 9 else "0.00"
                    pitches = cells[10].text.strip() if len(cells) > 10 else "0"

                    pitchers[side].append({
                        "name": name,
                        "is_starter": is_first,
                        "result": result_text,
                        "ip": ip,
                        "h": h,
                        "hr": hr,
                        "bb": bb,
                        "k": k,
                        "er": er,
                        "era": era,
                        "pitches": pitches
                    })
                    is_first = False

        except Exception as e:
            print(f"  ⚠️ 투수 파싱 오류: {e}")
        return pitchers

    def _parse_batters(self, soup) -> dict:
        batters = {"home": [], "away": []}
        try:
            tables = soup.find_all("table")
            batter_tables = []

            for t in tables:
                headers = [h.text.strip() for h in t.find_all("th")]
                if "타수" in headers and "안타" in headers:
                    batter_tables.append(t)

            sides = ["away", "home"]
            for idx, table in enumerate(batter_tables[:2]):
                side = sides[idx]
                rows = table.find_all("tr")[1:]

                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) < 4:
                        continue

                    order_text = cells[0].text.strip()
                    name = cells[1].text.strip() if len(cells) > 1 else ""
                    pos = cells[2].text.strip() if len(cells) > 2 else ""

                    if not name:
                        continue

                    ab = cells[3].text.strip() if len(cells) > 3 else "0"
                    runs = cells[4].text.strip() if len(cells) > 4 else "0"
                    h = cells[5].text.strip() if len(cells) > 5 else "0"
                    hr = cells[6].text.strip() if len(cells) > 6 else "0"
                    rbi = cells[7].text.strip() if len(cells) > 7 else "0"
                    bb = cells[8].text.strip() if len(cells) > 8 else "0"
                    k = cells[9].text.strip() if len(cells) > 9 else "0"
                    avg = cells[10].text.strip() if len(cells) > 10 else ".000"

                    batters[side].append({
                        "name": name,
                        "order": int(order_text) if order_text.isdigit() else 0,
                        "position": pos,
                        "ab": int(ab) if ab.isdigit() else 0,
                        "runs": int(runs) if runs.isdigit() else 0,
                        "h": int(h) if h.isdigit() else 0,
                        "hr": int(hr) if hr.isdigit() else 0,
                        "rbi": int(rbi) if rbi.isdigit() else 0,
                        "bb": int(bb) if bb.isdigit() else 0,
                        "k": int(k) if k.isdigit() else 0,
                        "avg": avg
                    })

        except Exception as e:
            print(f"  ⚠️ 타자 파싱 오류: {e}")
        return batters

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
                game_data = self.get_game_result(game_id)
                if game_data:
                    game_data["summary"] = self._make_summary(game_data)
                    result["games"].append(game_data)
                    print(
                        f"  ✅ {game_data['away_team']} vs "
                        f"{game_data['home_team']} "
                        f"{game_data['away_score']}-{game_data['home_score']}"
                    )
            except Exception as e:
                print(f"  ❌ {game_id} 오류: {e}")

        return result

    def _make_summary(self, game) -> str:
        h_starter = game.get("home_starter", {})
        a_starter = game.get("away_starter", {})
        return (
            f"[KBO] {game['home_team']} vs {game['away_team']}\n"
            f"선발: {h_starter.get('name','?')}(홈) vs "
            f"{a_starter.get('name','?')}(원정)\n"
            f"결과: {game['home_team']} {game['home_score']}-"
            f"{game['away_score']} {game['away_team']}\n"
            f"승자: {game['winner']}\n"
            f"총득점: {game['total_runs']}"
                    )
