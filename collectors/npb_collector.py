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

            # 💡 [구조 변경 1] 텍스트에 진짜 취소 단어가 있는 경우만 먼저 리턴
            if "Postponed" in page_text or "Cancelled" in page_text:
                return {"status": "우천취소"}

            title = soup.find("title")
            away_team = ""
            home_team = ""

            if title:
                title_text = title.text.strip()
                vs_match = re.search(r'\)\s+(.+?)\s+vs\s+(.+?)(?:\s*\|)', title_text)
                if vs_match:
                    away_team = vs_match.group(1).strip()
                    home_team = vs_match.group(2).strip()

            away_score = 0
            home_score = 0
            inning_scores = []

            # HTML Table 파싱 구조
            tables = soup.find_all("table")
            scoreboard_table = None
            
            for t in tables:
                if "Innings" in t.text and ("R" in t.text or "Total" in t.text):
                    scoreboard_table = t
                    break

            # 💡 [구조 변경 2] 테이블이 비어 있더라도, 섣불리 취소 처리하지 않고 타이틀 기반으로 점수 먼저 복구 시도
            if scoreboard_table:
                rows = scoreboard_table.find_all("tr")
                header_tds = [td.text.strip() for td in rows[0].find_all(["th", "td"]) if td.text.strip()]
                
                r_idx = -3
                if "R" in header_tds:
                    r_idx = header_tds.index("R")
                elif "Total" in header_tds:
                    r_idx = header_tds.index("Total")

                team_rows = []
                for row in rows[1:]:
                    tds = [td.text.strip().replace('.', '') for td in row.find_all(["th", "td"])]
                    if tds and tds[0] not in ["Innings", "Teams", "Totals", "Total", ""]:
                        team_rows.append(tds)

                if len(team_rows) >= 2:
                    away_row = team_rows[0]
                    home_row = team_rows[1]

                    if not away_team: away_team = away_row[0]
                    if not home_team: home_team = home_row[0]

                    try: away_score = int(away_row[r_idx])
                    except: away_score = int(away_row[-3]) if len(away_row) >= 4 else 0
                        
                    try: home_score = int(home_row[r_idx])
                    except: home_score = int(home_row[-3]) if len(home_row) >= 4 else 0

                    actual_r_idx = r_idx if r_idx > 0 else len(away_row) + r_idx
                    inning_count = actual_r_idx - 1

                    for i in range(inning_count):
                        a_inn = 0
                        h_inn = 0
                        if i + 1 < len(away_row):
                            token = away_row[i + 1]
                            a_inn = int(token) if token.isdigit() else 0
                        if i + 1 < len(home_row):
                            token = home_row[i + 1]
                            h_inn = int(token) if token.isdigit() else 0

                        inning_scores.append({"inning": i + 1, "away": a_inn, "home": h_inn})

            # 테이블 파싱 안 됐을 시 타이틀 기반 강력 백업
            if not inning_scores and title and away_team and home_team:
                title_score_match = re.search(rf'{away_team}\s+(\d+)\s+vs\s+{home_team}\s+(\d+)', title.text)
                if title_score_match:
                    away_score = int(title_score_match.group(1))
                    home_score = int(title_score_match.group(2))
                    inning_scores = [{"inning": 1, "away": away_score, "home": home_score}]

            # 💡 [구조 변경 3] 여기까지 왔는데도 이닝 기록이 없다면 테이블도 타이틀 점수도 없는 빈 취소 페이지로 최종 판단
            if not inning_scores:
                return {"status": "우천취소"}

            # 세부 스펙(투수, 타자) 파싱 중 에러가 나더라도 전체 게임 정보는 유지되도록 예외격리
            wp, lp, stadium = "", "", ""
            try:
                wp_match = re.search(r'WP\s*:\s*([^\n\(]+)', page_text)
                lp_match = re.search(r'LP\s*:\s*([^\n\(]+)', page_text)
                if wp_match: wp = wp_match.group(1).strip().rstrip(',').replace('.', '')
                if lp_match: lp = lp_match.group(1).strip().rstrip(',').replace('.', '')

                lines = [l.strip() for l in page_text.split('\n') if l.strip()]
                for line in lines:
                    if any(k in line for k in [
                        'Dome', 'Stadium', 'Field', 'Koshien', 'Jingu', 'FIELD', 'MAZDA', 
                        'ZoZo', 'PayPay', 'Marine', 'Belluna', 'CON', 'Yokohama', 'Osaka', 
                        'Sapporo', 'ES CON', 'ZOZO', 'Vantelin', 'Mazda', 'Meiji', 'Mobile'
                    ]):
                        if len(line) < 60 and not line.startswith('http'):
                            stadium = line.strip().replace('.', '')
                            break
            except:
                pass

            pitchers = self._parse_pitchers(soup)
            batters = self._parse_batters(soup)
            game_id = game_url.split("/")[-1].replace(".html", "")

            return {
                "game_id": game_id,
                "url": game_url,
                "home_team": home_team if home_team else "Home",
                "away_team": away_team if away_team else "Away",
                "home_score": str(home_score),
                "away_score": str(away_score),
                "stadium": stadium[:60],
                "status": "종료",
                "total_runs": home_score + away_score,
                "winner": home_team if home_score > away_score else away_team,
                "inning_scores": inning_scores,
                "win_pitcher": wp,
                "lose_pitcher": lp,
                "home_pitchers": pitchers["home"],
                "away_pitchers": pitchers["away"],
                "home_batters": batters["home"],
                "away_batters": batters["away"],
                "home_starter": next((p for p in pitchers["home"] if p.get("is_starter")), {}),
                "away_starter": next((p for p in pitchers["away"] if p.get("is_starter")), {})
            }

        except Exception as e:
            # 💡 최상단 예외에 걸리더라도, 데이터 유실 로그만 남기고 전체 시스템을 죽이지 않음
            print(f"  ⚠️ NPB 파싱 내부 오류 무시: {e}")
            return {}

    def _parse_pitchers(self, soup) -> dict:
        pitchers = {"home": [], "away": []}
        try:
            tables = soup.find_all("table")
            pitcher_tables = []
            for t in tables:
                headers = [h.text.strip() for h in t.find_all("th")]
                if "IP" in headers and "ER" in headers:
                    pitcher_tables.append(t)

            sides = ["away", "home"]
            for idx, table in enumerate(pitcher_tables[:2]):
                side = sides[idx]
                rows = table.find_all("tr")[1:]
                is_first = True

                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) < 3: continue
                    name = cells[0].text.strip().replace('.', '')
                    if not name or name in ["Totals", "Total"]: continue

                    pitchers[side].append({
                        "name": name,
                        "is_starter": is_first,
                        "result": "",
                        "ip": cells[1].text.strip() if len(cells) > 1 else "0",
                        "bf": cells[2].text.strip() if len(cells) > 2 else "0",
                        "h": cells[3].text.strip() if len(cells) > 3 else "0",
                        "bb": cells[4].text.strip() if len(cells) > 4 else "0",
                        "hb": cells[5].text.strip() if len(cells) > 5 else "0",
                        "k": cells[6].text.strip() if len(cells) > 6 else "0",
                        "er": cells[7].text.strip() if len(cells) > 7 else "0",
                    })
                    is_first = False
        except:
            pass
        return pitchers

    def _parse_batters(self, soup) -> dict:
        batters = {"home": [], "away": []}
        try:
            tables = soup.find_all("table")
            batter_tables = []
            for t in tables:
                headers = [h.text.strip() for h in t.find_all("th")]
                if "AB" in headers and "RBI" in headers:
                    batter_tables.append(t)

            sides = ["away", "home"]
            for idx, table in enumerate(batter_tables[:2]):
                side = sides[idx]
                rows = table.find_all("tr")[1:]

                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) < 3: continue
                    name = cells[0].text.strip().replace('.', '')
                    if not name or name in ["Totals", "Total"]: continue

                    ab = cells[1].text.strip() if len(cells) > 1 else "0"
                    h = cells[2].text.strip() if len(cells) > 2 else "0"
                    rbi = cells[3].text.strip() if len(cells) > 3 else "0"
                    bb = cells[4].text.strip() if len(cells) > 4 else "0"
                    k = cells[6].text.strip() if len(cells) > 6 else "0"

                    batters[side].append({
                        "name": name,
                        "ab": int(ab) if ab.isdigit() else 0,
                        "h": int(h) if h.isdigit() else 0,
                        "rbi": int(rbi) if rbi.isdigit() else 0,
                        "bb": int(bb) if bb.isdigit() else 0,
                        "k": int(k) if k.isdigit() else 0,
                    })
        except:
            pass
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
                
                if game_data and game_data.get("status") == "우천취소":
                    print(f"  🌧️ 우천 취소(데이터 없음): {link.split('/')[-1]}")
                elif game_data:
                    game_data["date"] = date
                    game_data["summary"] = self._make_summary(game_data)
                    result["games"].append(game_data)
                    print(
                        f"  ✅ {game_data['away_team']} vs "
                        f"{game_data['home_team']} "
                        f"{game_data['away_score']}-{game_data['home_score']}"
                    )
                else:
                    print(f"  ⚠️ 시스템 파싱 에러 제외: {link.split('/')[-1]}")
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
