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

            # 스코어보드 테이블 타겟팅
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
                try:
                    rows = scoreboard_table.find_all("tr")
                    if rows:
                        header_tds = [td.text.strip() for td in rows[0].find_all(["th", "td"]) if td.text.strip()]
                        
                        r_idx = -3
                        for k in ["R", "Total", "Runs"]:
                            if k in header_tds:
                                r_idx = header_tds.index(k)
                                break

                        # 팀 행 필터링 진행
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

                            # class 속성 기반으로 r 찾기 시도
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

                            # 💡 [핵심 수정] 인덱스 유효성 검증 단계를 거쳐 안전하게 셀 바인딩 (Index Error 원천 차단)
                            if not away_r_cell:
                                if 0 <= r_idx < len(away_tds):
                                    away_r_cell = away_tds[r_idx]
                                elif len(away_tds) >= 4:
                                    away_r_cell = away_tds[-3]

                            if not home_r_cell:
                                if 0 <= r_idx < len(home_tds):
                                    home_r_cell = home_tds[r_idx]
                                elif len(home_tds) >= 4:
                                    home_r_cell = home_tds[-3]

                            if away_r_cell:
                                txt = away_r_cell.text.strip()
                                away_score = int(txt) if txt.isdigit() else 0
                            if home_r_cell:
                                txt = home_r_cell.text.strip()
                                home_score = int(txt) if txt.isdigit() else 0

                            # 이닝 스코어 파싱
                            try:
                                away_r_idx = away_tds.index(away_r_cell) if away_r_cell else len(away_tds) - 3
                                inning_tds_away = away_tds[1:away_r_idx]
                                inning_tds_home = home_tds[1:away_r_idx]

                                for i in range(len(inning_tds_away)):
                                    a_txt = inning_tds_away[i].text.strip()
                                    h_txt = inning_tds_home[i].text.strip() if i < len(inning_tds_home) else "0"

                                    a_inn = int(a_txt) if a_txt.isdigit() else 0
                                    h_inn = int(h_txt) if h_txt.isdigit() else 0

                                    inning_scores.append({"inning": i + 1, "away": a_inn, "home": h_inn})
                            except:
                                pass
                except:
                    pass

            if not inning_scores and away_score == 0 and home_score == 0:
                return {"status": "우천취소"}

            if not inning_scores:
                inning_scores = [{"inning": 1, "away": away_score, "home": home_score}]

            # 투수/타자 정보 스크랩
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
                    
                    if "games" not in result:
                        result["games"] = []
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
