import requests
from bs4 import BeautifulSoup
import time

class KBOCollector:

    BASE_URL = "https://www.statiz.co.kr"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.statiz.co.kr"
    }

    def get_game_ids(self, date: str) -> list:
        """
        STATIZ에서 날짜별 경기 목록 수집
        date: YYYYMMDD
        """
        year = date[:4]
        month = date[4:6]
        day = date[6:8]

        url = f"{self.BASE_URL}/schedule/?year={year}&month={month}"

        try:
            resp = requests.get(url, headers=self.HEADERS, timeout=15)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")

            game_ids = []
            target_date = f"{year}.{month}.{day}"

            # 날짜별 경기 링크 파싱
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "boxscore" in href or "gameId" in href.lower():
                    game_id = href.split("=")[-1]
                    if date in game_id or date in href:
                        if game_id not in game_ids:
                            game_ids.append(game_id)

            # 날짜 텍스트로 찾기
            if not game_ids:
                for td in soup.find_all("td"):
                    if target_date in td.text or f"{month}/{day}" in td.text:
                        for a in td.find_all("a", href=True):
                            href = a["href"]
                            if game_ids not in href:
                                game_ids.append(href)

            print(f"  [KBO] STATIZ gameId {len(game_ids)}개: {game_ids[:3]}")
            return game_ids

        except Exception as e:
            print(f"  ❌ STATIZ 스케줄 수집 실패: {e}")
            return []

    def get_game_result(self, game_id: str) -> dict:
        """STATIZ 박스스코어 수집"""

        # game_id가 URL이면 그대로, 아니면 조합
        if game_id.startswith("http"):
            url = game_id
        elif game_id.startswith("/"):
            url = f"{self.BASE_URL}{game_id}"
        else:
            url = f"{self.BASE_URL}/schedule/boxscore/?gameId={game_id}"

        try:
            resp = requests.get(url, headers=self.HEADERS, timeout=15)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")
        except Exception as e:
            print(f"  ❌ 박스스코어 수집 실패: {e}")
            return {}

        return self._parse_boxscore(soup, game_id)

    def _parse_boxscore(self, soup, game_id: str) -> dict:
        try:
            # 팀명 파싱
            team_tags = soup.find_all("div", class_="team-name") or \
                        soup.find_all("td", class_="team")

            away_team = ""
            home_team = ""

            # 스코어보드 테이블
            score_table = soup.find("table", class_="box-score") or \
                         soup.find("table", id="tblScore") or \
                         soup.find("table")

            away_score = 0
            home_score = 0
            inning_scores = []

            if score_table:
                rows = score_table.find_all("tr")
                if len(rows) >= 3:
                    # 팀명 추출
                    away_row = rows[1]
                    home_row = rows[2]

                    away_cells = away_row.find_all("td")
                    home_cells = home_row.find_all("td")

                    if away_cells:
                        away_team = away_cells[0].text.strip()
                    if home_cells:
                        home_team = home_cells[0].text.strip()

                    # 이닝별 득점
                    num_innings = len(away_cells) - 4  # 팀명, R, H, E 제외
                    for i in range(1, num_innings + 1):
                        if i < len(away_cells) and i < len(home_cells):
                            av = away_cells[i].text.strip()
                            hv = home_cells[i].text.strip()
                            inning_scores.append({
                                "inning": i,
                                "away": int(av) if av.isdigit() else 0,
                                "home": int(hv) if hv.isdigit() else 0
                            })

                    # 총득점 (R 컬럼)
                    if len(away_cells) >= 3:
                        r_val = away_cells[-3].text.strip()
                        away_score = int(r_val) if r_val.isdigit() else 0
                    if len(home_cells) >= 3:
                        r_val = home_cells[-3].text.strip()
                        home_score = int(r_val) if r_val.isdigit() else 0

            pitchers = self._parse_pitchers(soup)
            batters = self._parse_batters(soup)

            return {
                "game_id": str(game_id),
                "date": "",
                "home_team": home_team,
                "away_team": away_team,
                "home_score": str(home_score),
                "away_score": str(away_score),
                "stadium": "",
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

        except Exception as e:
            print(f"  ⚠️ 박스스코어 파싱 오류: {e}")
            return {}

    def _parse_pitchers(self, soup) -> dict:
        pitchers = {"home": [], "away": []}
        try:
            tables = soup.find_all("table")
            pitcher_tables = []

            for t in tables:
                headers = [h.text.strip() for h in t.find_all("th")]
                if ("이닝" in headers or "IP" in headers) and \
                   ("자책" in headers or "ER" in headers):
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

                    pitchers[side].append({
                        "name": name,
                        "is_starter": is_first,
                        "result": cells[1].text.strip() if len(cells) > 1 else "",
                        "ip": cells[2].text.strip() if len(cells) > 2 else "0",
                        "h": cells[4].text.strip() if len(cells) > 4 else "0",
                        "hr": cells[5].text.strip() if len(cells) > 5 else "0",
                        "bb": cells[6].text.strip() if len(cells) > 6 else "0",
                        "k": cells[7].text.strip() if len(cells) > 7 else "0",
                        "er": cells[8].text.strip() if len(cells) > 8 else "0",
                        "era": cells[9].text.strip() if len(cells) > 9 else "0.00",
                        "pitches": cells[10].text.strip() if len(cells) > 10 else "0"
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
                if ("타수" in headers or "AB" in headers) and \
                   ("안타" in headers or "H" in headers):
                    batter_tables.append(t)

            sides = ["away", "home"]
            for idx, table in enumerate(batter_tables[:2]):
                side = sides[idx]
                rows = table.find_all("tr")[1:]

                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) < 4:
                        continue
                    name = cells[1].text.strip() if len(cells) > 1 else ""
                    if not name:
                        continue

                    order = cells[0].text.strip()
                    pos = cells[2].text.strip() if len(cells) > 2 else ""
                    ab = cells[3].text.strip() if len(cells) > 3 else "0"
                    h = cells[5].text.strip() if len(cells) > 5 else "0"
                    hr = cells[6].text.strip() if len(cells) > 6 else "0"
                    rbi = cells[7].text.strip() if len(cells) > 7 else "0"
                    bb = cells[8].text.strip() if len(cells) > 8 else "0"
                    k = cells[9].text.strip() if len(cells) > 9 else "0"
                    avg = cells[10].text.strip() if len(cells) > 10 else ".000"

                    batters[side].append({
                        "name": name,
                        "order": int(order) if order.isdigit() else 0,
                        "position": pos,
                        "ab": int(ab) if ab.isdigit() else 0,
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
                    game_data["date"] = date
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
        h_st = game.get("home_starter", {})
        a_st = game.get("away_starter", {})
        return (
            f"[KBO] {game['home_team']} vs {game['away_team']}\n"
            f"선발: {h_st.get('name','?')}(홈) vs {a_st.get('name','?')}(원정)\n"
            f"결과: {game['home_team']} {game['home_score']}-"
            f"{game['away_score']} {game['away_team']}\n"
            f"승자: {game['winner']}\n"
            f"총득점: {game['total_runs']}"
        )
