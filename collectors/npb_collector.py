import requests
from bs4 import BeautifulSoup
import time
import re

class NPBCollector:

    BASE_URL = "https://npb.jp/bis/eng/2026"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }

    def get_game_links(self, date: str) -> list:
        """날짜별 경기 링크 수집"""
        year = date[:4]
        month = date[4:6]
        day = date[6:8]

        url = f"https://npb.jp/bis/eng/{year}/games/gm{date}.html"

        try:
            resp = requests.get(url, headers=self.HEADERS, timeout=15)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")

            game_links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                # 개별 경기 링크 패턴: s2026XXXXXX.html
                if re.search(rf's{year}{month}{day}\d+\.html', href):
                    full_url = href if href.startswith("http") else \
                               f"https://npb.jp{href}" if href.startswith("/") else \
                               f"https://npb.jp/bis/eng/{year}/games/{href}"
                    if full_url not in game_links:
                        game_links.append(full_url)

            print(f"  [NPB] {len(game_links)}개 경기 링크 발견")
            return game_links

        except Exception as e:
            print(f"  ❌ NPB 스케줄 수집 실패: {e}")
            return []

    def get_game_result(self, game_url: str) -> dict:
        """개별 경기 박스스코어 수집"""
        try:
            resp = requests.get(game_url, headers=self.HEADERS, timeout=15)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")
        except Exception as e:
            print(f"  ❌ NPB 경기 수집 실패: {e}")
            return {}

        return self._parse_game(soup, game_url)

    def _parse_game(self, soup, game_url: str) -> dict:
        try:
            # 팀명과 스코어 파싱
            # NPB 영문 박스스코어 구조
            away_team = ""
            home_team = ""
            away_score = 0
            home_score = 0
            inning_scores = []

            # 라인스코어 테이블
            tables = soup.find_all("table")
            linescore_table = None

            for t in tables:
                text = t.get_text()
                if "R" in text and "H" in text and "E" in text:
                    rows = t.find_all("tr")
                    if len(rows) >= 2:
                        linescore_table = t
                        break

            if linescore_table:
                rows = linescore_table.find_all("tr")

                for row_idx, row in enumerate(rows[1:3]):  # 원정팀, 홈팀
                    cells = row.find_all(["td", "th"])
                    if not cells:
                        continue

                    # 팀명 (첫 번째 셀)
                    team_name = cells[0].text.strip()

                    # 이닝별 득점 파싱
                    inning_runs = []
                    total_r = 0

                    for cell in cells[1:]:
                        txt = cell.text.strip()
                        if txt == "R":
                            break
                        if txt.isdigit():
                            inning_runs.append(int(txt))

                    # R(총득점) 찾기
                    cell_texts = [c.text.strip() for c in cells]
                    try:
                        r_idx = cell_texts.index("R")
                        if r_idx + 1 < len(cell_texts):
                            r_val = cell_texts[r_idx + 1]
                            total_r = int(r_val) if r_val.isdigit() else sum(inning_runs)
                    except ValueError:
                        total_r = sum(inning_runs)

                    if row_idx == 0:
                        away_team = team_name
                        away_score = total_r
                        for i, r in enumerate(inning_runs):
                            if len(inning_scores) <= i:
                                inning_scores.append({"inning": i+1, "away": r, "home": 0})
                            else:
                                inning_scores[i]["away"] = r
                    else:
                        home_team = team_name
                        home_score = total_r
                        for i, r in enumerate(inning_runs):
                            if len(inning_scores) <= i:
                                inning_scores.append({"inning": i+1, "away": 0, "home": r})
                            else:
                                inning_scores[i]["home"] = r

            # 투수 기록
            pitchers = self._parse_pitchers(soup)

            # 타자 기록
            batters = self._parse_batters(soup)

            # 구장 정보
            stadium = ""
            stadium_tag = soup.find(string=re.compile(r'Dome|Stadium|Park|Field|Koshien|ZoZo|PayPay', re.I))
            if stadium_tag:
                stadium = stadium_tag.strip()

            game_id = game_url.split("/")[-1].replace(".html", "")

            return {
                "game_id": game_id,
                "url": game_url,
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

        except Exception as e:
            print(f"  ⚠️ NPB 파싱 오류: {e}")
            return {}

    def _parse_pitchers(self, soup) -> dict:
        pitchers = {"home": [], "away": []}
        try:
            tables = soup.find_all("table")
            pitcher_tables = []

            for t in tables:
                headers = [h.text.strip() for h in t.find_all("th")]
                if "IP" in headers or "ERA" in headers:
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
                    if not name or name == "Totals":
                        continue

                    pitchers[side].append({
                        "name": name,
                        "is_starter": is_first,
                        "result": cells[1].text.strip() if len(cells) > 1 else "",
                        "ip": cells[2].text.strip() if len(cells) > 2 else "0",
                        "bf": cells[3].text.strip() if len(cells) > 3 else "0",
                        "h": cells[4].text.strip() if len(cells) > 4 else "0",
                        "hr": cells[5].text.strip() if len(cells) > 5 else "0",
                        "bb": cells[6].text.strip() if len(cells) > 6 else "0",
                        "k": cells[7].text.strip() if len(cells) > 7 else "0",
                        "er": cells[8].text.strip() if len(cells) > 8 else "0",
                        "era": cells[9].text.strip() if len(cells) > 9 else "0.00"
                    })
                    is_first = False

        except Exception as e:
            print(f"  ⚠️ NPB 투수 파싱 오류: {e}")
        return pitchers

    def _parse_batters(self, soup) -> dict:
        batters = {"home": [], "away": []}
        try:
            tables = soup.find_all("table")
            batter_tables = []

            for t in tables:
                headers = [h.text.strip() for h in t.find_all("th")]
                if "AB" in headers and "H" in headers:
                    batter_tables.append(t)

            sides = ["away", "home"]
            for idx, table in enumerate(batter_tables[:2]):
                side = sides[idx]
                rows = table.find_all("tr")[1:]

                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) < 4:
                        continue
                    name = cells[0].text.strip()
                    if not name or name == "Totals":
                        continue

                    pos = cells[1].text.strip() if len(cells) > 1 else ""
                    ab = cells[2].text.strip() if len(cells) > 2 else "0"
                    r = cells[3].text.strip() if len(cells) > 3 else "0"
                    h = cells[4].text.strip() if len(cells) > 4 else "0"
                    rbi = cells[5].text.strip() if len(cells) > 5 else "0"
                    bb = cells[6].text.strip() if len(cells) > 6 else "0"
                    k = cells[7].text.strip() if len(cells) > 7 else "0"
                    avg = cells[8].text.strip() if len(cells) > 8 else ".000"

                    batters[side].append({
                        "name": name,
                        "position": pos,
                        "ab": int(ab) if ab.isdigit() else 0,
                        "runs": int(r) if r.isdigit() else 0,
                        "h": int(h) if h.isdigit() else 0,
                        "rbi": int(rbi) if rbi.isdigit() else 0,
                        "bb": int(bb) if bb.isdigit() else 0,
                        "k": int(k) if k.isdigit() else 0,
                        "avg": avg
                    })

        except Exception as e:
            print(f"  ⚠️ NPB 타자 파싱 오류: {e}")
        return batters

    def collect_daily(self, date: str) -> dict:
        print(f"[NPB] {date} 수집 시작")

        result = {
            "date": date,
            "league": "NPB",
            "games": []
        }

        game_links = self.get_game_links(date)

        if not game_links:
            print(f"  [NPB] 경기 없음")
            return result

        for link in game_links:
            time.sleep(0.5)
            try:
                game_data = self.get_game_result(link)
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
                print(f"  ❌ {link}: {e}")

        return result

    def _make_summary(self, game) -> str:
        h_st = game.get("home_starter", {})
        a_st = game.get("away_starter", {})
        return (
            f"[NPB] {game['home_team']} vs {game['away_team']}\n"
            f"선발: {h_st.get('name','?')}(홈) vs "
            f"{a_st.get('name','?')}(원정)\n"
            f"결과: {game['home_team']} {game['home_score']}-"
            f"{game['away_score']} {game['away_team']}\n"
            f"승자: {game['winner']}\n"
            f"총득점: {game['total_runs']}"
        )
