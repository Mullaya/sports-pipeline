import requests
from bs4 import BeautifulSoup
import time
import re

class NPBCollector:

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }

    def get_game_links(self, date: str) -> list:
        year = date[:4]
        url = f"https://npb.jp/bis/eng/{year}/games/gm{date}.html"

        try:
            resp = requests.get(url, headers=self.HEADERS, timeout=15)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")

            game_links = []
            pattern = re.compile(rf's{date}\d+\.html')

            for a in soup.find_all("a", href=True):
                href = a["href"]
                if pattern.search(href):
                    if href.startswith("http"):
                        full_url = href
                    elif "/bis/eng/" in href:
                        full_url = f"https://npb.jp{href}" if href.startswith("/") else f"https://npb.jp/{href}"
                    else:
                        full_url = f"https://npb.jp/bis/eng/{year}/games/{href}"
                    
                    if full_url not in game_links:
                        game_links.append(full_url)

            print(f"  [NPB] {len(game_links)}개 경기 링크 발견")
            return game_links

        except Exception as e:
            print(f"  ❌ NPB 스케줄 수집 실패: {e}")
            return []

    def get_game_result(self, game_url: str) -> dict:
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
            page_text = soup.get_text(separator='\n')

            # 1. 우천 취소 상태 검사
            if "Postponed" in page_text or "Cancelled" in page_text:
                return {"status": "우천취소"}

            title = soup.find("title")
            away_team = ""
            home_team = ""

            if title:
                title_text = title.text.strip()
                vs_match = re.search(r'(?:\)\s*|\|\s*)(.+?)\s+vs\s+(.+?)(?:\s*\||\s*\()', title_text)
                if vs_match:
                    away_team = vs_match.group(1).strip()
                    home_team = vs_match.group(2).strip()

            away_score = 0
            home_score = 0
            inning_scores = []

            tables = soup.find_all("table")
            scoreboard_table = None
            
            for t in tables:
                t_txt = t.text
                if "Innings" in t_txt and ("R" in t_txt or "Total" in t_txt):
                    scoreboard_table = t
                    break

            if not scoreboard_table and tables:
                scoreboard_table = tables[0]

            if scoreboard_table:
                rows = scoreboard_table.find_all("tr")
                if rows:
                    header_tds = [td.text.strip() for td in rows[0].find_all(["th", "td"]) if td.text.strip()]
                    
                    r_idx = None
                    for k in ["R", "Total", "Runs"]:
                        if k in header_tds:
                            r_idx = header_tds.index(k)
                            break

                    valid_rows = []
                    for row in rows[1:]:
                        tds = row.find_all(["th", "td"])
                        if tds:
                            first_token = tds[0].text.strip().replace('.', '')
                            if first_token not in ["Innings", "Teams", "Totals", "Total", "Team", "Linescore", ""]:
                                valid_rows.append(tds)

                    if len(valid_rows) >= 2:
                        away_tds = valid_rows[0]
                        home_tds = valid_rows[1]

                        if not away_team: away_team = away_tds[0].text.strip().replace('.', '')
                        if not home_team: home_team = home_tds[0].text.strip().replace('.', '')

                        away_r_cell = None
                        home_r_cell = None

                        # 💡 [인덱스 에러 방지 해결책] class 속성 우선 검색
                        for td in away_tds:
                            classes = td.get("class", [])
                            if "r" in classes or "total" in classes:
                                away_r_cell = td
                                break
                        for td in home_tds:
                            classes = td.get("class", [])
                            if "r" in classes or "total" in classes:
                                home_r_cell = td
                                break

                        # 💡 인덱스가 유효할 때만 r_idx 활용, 범위 넘어가면 셀 리스트에서 안전하게 역추적
                        if not away_r_cell and r_idx is not None and 0 <= r_idx < len(away_tds):
                            away_r_cell = away_tds[r_idx]
                        if not home_r_cell and r_idx is not None and 0 <= r_idx < len(home_tds):
                            home_r_cell = home_tds[r_idx]

                        # 최종 예비책: 숫자가 채워진 셀 중 뒤에서 3번째 셀 선택 (R, H, E 구조)
                        if not away_r_cell and len(away_tds) >= 4: away_r_cell = away_tds[-3]
                        if not home_r_cell and len(home_tds) >= 4: home_r_cell = home_tds[-3]

                        if away_r_cell:
                            txt = away_r_cell.text.strip()
                            away_score = int(txt) if txt.isdigit
