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
                    elif href.startswith("/"):
                        full_url = f"https://npb.jp{href}"
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
            title = soup.find("title")
            away_team = ""
            home_team = ""

            if title:
                title_text = title.text.strip()
                vs_match = re.search(r'\)\s+(.+?)\s+vs\s+(.+?)(?:\s*\|)', title_text)
                if vs_match:
                    away_team = vs_match.group(1).strip()
                    home_team = vs_match.group(2).strip()

            page_text = soup.get_text(separator='\n')
            lines = [l.strip() for l in page_text.split('\n') if l.strip()]

            away_score = 0
            home_score = 0
            inning_scores = []
            linescore_rows = []

            # 💡 [핵심 알고리즘 교체] 까다로운 통짜 정규식 대신, 쪼개서 분석하는 유연한 방식으로 변경
            for line in lines:
                if any(k in line for k in ["Innings", "Batting", "Pitching", "Totals", "vs"]):
                    continue
                
                # 라인 스코어 줄 특징: 하이픈 '-'이 들어가고 마침표 '.'가 여러 개 존재함
                if '-' in line and line.count('.') >= 4:
                    # 모든 공백을 없애고 마침표 기준으로 쪼갬
                    clean_line = line.replace(' ', '')
                    tokens = [t for t in clean_line.split('.') if t]
                    
                    # 하이픈을 기준으로 이닝 스코어와 총점 분리 시도
                    if '-' in tokens:
                        linescore_rows.append(tokens)

            # 정상적으로 두 팀의 스코어 라인이 검출되었을 때
            if len(linescore_rows) >= 2:
                for idx, tokens in enumerate(linescore_rows[:2]):
                    # 구조: [팀명, 1회, 2회, ..., '-', 총점R, 안타H, 실책E]
                    try:
                        dash_index = tokens.index('-')
                        # 팀명 분리
                        t_name = tokens[0]
                        # 이닝 리스트 추출
                        innings = tokens[1:dash_index]
                        # 총 득점(R) 추출
                        total_r = int(tokens[dash_index + 1])
                    except (ValueError, IndexError):
                        continue

                    for i, token in enumerate(innings):
                        r = int(token) if token.isdigit() else 0
                        
                        if idx == 0:
                            if len(inning_scores) <= i:
                                inning_scores.append({"inning": i+1, "away": r, "home": 0})
                            else:
                                inning_scores[i]["away"] = r
                        else:
                            if len(inning_scores) <= i:
                                inning_scores.append({"inning": i+1, "away": 0, "home": r})
                            else:
                                inning_scores[i]["home"] = r

                    if idx == 0:
                        away_score = total_r
                        if not away_team:
                            away_team = t_name
                    else:
                        home_score = total_r
                        if not home_team:
                            home_team = t_name

            # 만약 매칭이 안 됐다면 최소한 타이틀 스코어라도 찾아내는 서브 백업 로직
            if not inning_scores and title:
                # 타이틀 예시: "(Jun 21) Yomiuri 3 vs Chunichi 2 | NPB"
                title_score_match = re.search(rf'{away_team}\s+(\d+)\s+vs\s+{home_team}\s+(\d+)', title.text)
                if title_score_match:
                    away_score = int(title_score_match.group(1))
                    home_score = int(title_score_match.group(2))
                    inning_scores = [{"inning": 1, "away": away_score, "home": home_score}]

            if not inning_scores:
                return {}

            # 나머지 투수/타자/구장 파싱은 유지
            wp = ""
            lp = ""
            wp_match = re.search(r'WP\s*:\s*([^\n\(]+)', page_text)
            lp_match = re.search(r'LP\s*:\s*([^\n\(]+)', page_text)
            if wp_match:
                wp = wp_match.group(1).strip().rstrip(',').replace('.', '')
            if lp_match:
                lp = lp_match.group(1).strip().rstrip(',').replace('.', '')

            stadium = ""
            for line in lines:
                if any(k in line for k in [
                    'Dome', 'Stadium', 'Field', 'Koshien', 'Jingu', 'FIELD', 'MAZDA', 
                    'ZoZo', 'PayPay', 'Marine', 'Belluna', 'CON', 'Yokohama', 'Osaka', 
                    'Sapporo', 'ES CON', 'ZOZO', 'Vantelin', 'Mazda', 'Meiji', 'Mobile'
                ]):
                    if len(line) < 60 and not line.startswith('http'):
                        stadium = line.strip().replace('.', '')
                        break

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
            print(f"  ⚠️ NPB 파싱 오류: {e}")
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
                    if len(cells) < 3:
                        continue
                    name = cells[0].text.strip().replace('.', '')
                    if not name or name in ["Totals", "Total"]:
                        continue

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
                if "AB" in headers and "RBI" in headers:
                    batter_tables.append(t)

            sides = ["away", "home"]
            for idx, table in enumerate(batter_tables[:2]):
                side = sides[idx]
                rows = table.find_all("tr")[1:]

                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) < 3:
                        continue
                    name = cells[0].text.strip().replace('.', '')
                    if not name or name in ["Totals", "Total"]:
                        continue

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
                else:
                    print(f"  ⚠️ 우천취소 제외: {link.split('/')[-1]}")
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
