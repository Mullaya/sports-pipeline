import requests
import json
import time
from itertools import permutations

class KBOCollector:

    BASE_URL = "https://www.koreabaseball.com"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.koreabaseball.com",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }

    TEAM_CODES = {
        "HH": "한화", "OB": "두산", "LG": "LG",
        "SS": "삼성", "SK": "SSG", "KT": "KT",
        "NC": "NC", "HT": "KIA", "LT": "롯데",
        "WO": "키움"
    }

    def get_game_ids(self, date: str) -> list:
        """KBO 내부 JSON API로 당일 경기 목록 수집"""

        # KBO 내부 스케줄 API
        api_urls = [
            f"{self.BASE_URL}/ws/Schedule.asmx/GetScheduleList",
            f"{self.BASE_URL}/ws/game.asmx/GetScheduleList",
        ]

        payloads = [
            {"leagueId": "1", "seriesId": "0", "gameDate": date},
            {"leId": "1", "srId": "0", "gameDate": date},
            {"leagueId": "1", "seriesId": "0", "gameDate": date,
             "teamCode": "", "stadiumCode": ""},
        ]

        for url in api_urls:
            for payload in payloads:
                try:
                    resp = requests.post(
                        url,
                        data=payload,
                        headers=self.HEADERS,
                        timeout=10
                    )
                    text = resp.text.strip()

                    # XML 파싱
                    if "<game>" in text or "<Game>" in text:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(text, "lxml-xml")
                        games = soup.find_all("game") or soup.find_all("Game")
                        game_ids = []
                        for g in games:
                            gid = g.find("gameId") or g.find("GameId")
                            status = g.find("statusInfo") or g.find("StatusInfo")
                            if gid:
                                status_text = status.text if status else ""
                                print(f"    {gid.text} | {status_text}")
                                if "종료" in status_text:
                                    game_ids.append(gid.text)
                        if game_ids:
                            return game_ids

                    # JSON 파싱
                    if text.startswith("{") or text.startswith("["):
                        data = json.loads(text)
                        print(f"    JSON 응답: {str(data)[:200]}")

                except Exception as e:
                    print(f"    {url} 실패: {e}")
                    continue

        # 모든 API 실패 시 게임스케줄 페이지 파싱 시도
        return self._scrape_schedule_page(date)

    def _scrape_schedule_page(self, date: str) -> list:
        """KBO 경기일정 페이지 직접 파싱"""
        from bs4 import BeautifulSoup

        year = date[:4]
        month = date[4:6]
        day = date[6:8]

        urls = [
            f"{self.BASE_URL}/Schedule/Schedule.aspx",
            f"https://m.koreabaseball.com/Kbo/Schedule.aspx",
        ]

        for url in urls:
            try:
                headers = {**self.HEADERS,
                          "Content-Type": "text/html"}
                resp = requests.get(url, headers=headers, timeout=10)
                resp.encoding = "utf-8"
                soup = BeautifulSoup(resp.text, "html.parser")

                # gameId 패턴 찾기
                game_ids = []
                import re
                pattern = re.compile(
                    rf'{date}[A-Z]{{4}}\d'
                )
                text = resp.text
                found = pattern.findall(text)
                for gid in found:
                    if gid not in game_ids:
                        game_ids.append(gid)

                if game_ids:
                    print(f"  [KBO] 페이지 파싱으로 {len(game_ids)}개 발견: {game_ids}")
                    return game_ids

            except Exception as e:
                print(f"    스케줄 페이지 파싱 실패: {e}")

        # 마지막 수단: gameId 직접 생성 + 검증
        return self._brute_force_game_ids(date)

    def _brute_force_game_ids(self, date: str) -> list:
        """팀 조합으로 gameId 생성 후 KBO JSON API로 검증"""
        print(f"  [KBO] 브루트포스 방식으로 gameId 검색...")

        team_codes = list(self.TEAM_CODES.keys())
        found = []

        for away, home in permutations(team_codes, 2):
            game_id = f"{date}{away}{home}0"

            # KBO 게임 데이터 API
            api_url = f"{self.BASE_URL}/ws/Game.asmx/GetScoreBoardScroll"
            payload = {
                "leId": "1",
                "srId": "0",
                "seasonId": date[:4],
                "gameId": game_id
            }

            try:
                resp = requests.post(
                    api_url,
                    data=payload,
                    headers=self.HEADERS,
                    timeout=5
                )
                text = resp.text.strip()

                # 유효한 응답이면 경기 존재
                if len(text) > 100 and ("<" in text or "{" in text):
                    if "오류" not in text and "error" not in text.lower():
                        found.append(game_id)
                        print(f"    ✅ 경기 발견: {game_id}")

            except Exception:
                pass

            time.sleep(0.15)

        print(f"  [KBO] {len(found)}개 경기 발견")
        return found

    def get_boxscore(self, game_id: str) -> dict:
        """KBO 박스스코어 JSON API"""

        result = {
            "pitchers": {"home": [], "away": []},
            "batters": {"home": [], "away": []},
            "inning_scores": []
        }

        season_id = game_id[:4]

        payload_base = {
            "leId": "1",
            "srId": "0",
            "seasonId": season_id,
            "gameId": game_id
        }

        # 이닝별 득점
        try:
            resp = requests.post(
                f"{self.BASE_URL}/ws/Schedule.asmx/GetScoreBoardScroll",
                data=payload_base,
                headers=self.HEADERS,
                timeout=10
            )
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "lxml-xml")
            for i, inning in enumerate(soup.find_all("inning"), 1):
                home_s = inning.find("homeScore")
                away_s = inning.find("awayScore")
                result["inning_scores"].append({
                    "inning": i,
                    "home": int(home_s.text) if home_s and home_s.text.isdigit() else 0,
                    "away": int(away_s.text) if away_s and away_s.text.isdigit() else 0
                })
        except Exception as e:
            print(f"  ⚠️ 이닝 수집 오류: {e}")

        # 박스스코어 (투수/타자)
        try:
            resp = requests.post(
                f"{self.BASE_URL}/ws/Schedule.asmx/GetBoxScoreScroll",
                data=payload_base,
                headers=self.HEADERS,
                timeout=10
            )
            from bs4 import BeautifulSoup
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
                    "order": int(order.text) if order else 0,
                    "position": batter.find("position").text if batter.find("position") else "",
                    "ab": int(batter.find("ab").text) if batter.find("ab") else 0,
                    "h": int(batter.find("hit").text) if batter.find("hit") else 0,
                    "hr": int(batter.find("hr").text) if batter.find("hr") else 0,
                    "rbi": int(batter.find("rbi").text) if batter.find("rbi") else 0,
                    "bb": int(batter.find("bb").text) if batter.find("bb") else 0,
                    "k": int(batter.find("kk").text) if batter.find("kk") else 0,
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
                # gameId에서 팀 정보 추출
                away_code = game_id[8:10]
                home_code = game_id[10:12]
                away_team = self.TEAM_CODES.get(away_code, away_code)
                home_team = self.TEAM_CODES.get(home_code, home_code)

                # 스코어 수집
                score_resp = requests.post(
                    f"{self.BASE_URL}/ws/Schedule.asmx/GetScoreBoardScroll",
                    data={
                        "leId": "1", "srId": "0",
                        "seasonId": date[:4], "gameId": game_id
                    },
                    headers=self.HEADERS, timeout=10
                )
                from bs4 import BeautifulSoup
                score_soup = BeautifulSoup(score_resp.text, "lxml-xml")

                home_score = 0
                away_score = 0
                total_tag = score_soup.find("totalScore") or \
                            score_soup.find("TotalScore")
                if total_tag:
                    h = total_tag.find("home") or total_tag.find("homeScore")
                    a = total_tag.find("away") or total_tag.find("awayScore")
                    if h:
                        home_score = int(h.text) if h.text.isdigit() else 0
                    if a:
                        away_score = int(a.text) if a.text.isdigit() else 0

                boxscore = self.get_boxscore(game_id)

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
                    "home_score": str(home_score),
                    "away_score": str(away_score),
                    "stadium": "",
                    "status": "종료",
                    "total_runs": home_score + away_score,
                    "winner": home_team if home_score > away_score else away_team,
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
