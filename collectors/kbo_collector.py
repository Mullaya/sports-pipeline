import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import time

class KBOCollector:
    
    BASE_URL = "https://www.koreabaseball.com"
    SCHEDULE_URL = f"{BASE_URL}/ws/Schedule.asmx/GetScheduleList"
    BOXSCORE_URL = f"{BASE_URL}/ws/Game.asmx/GetBoxScore"
    
    HEADERS = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": "https://www.koreabaseball.com/Schedule/GameCenter/Main.aspx",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    def get_daily_schedule(self, date: str) -> list:
        payload = {
            "leagueId": "1",
            "seriesId": "0",
            "gameDate": date
        }
        
        resp = requests.post(
            self.SCHEDULE_URL,
            data=payload,
            headers=self.HEADERS,
            timeout=10
        )
        
        games = []
        soup = BeautifulSoup(resp.text, "lxml-xml")
        
        for game in soup.find_all("game"):
            game_id = game.find("gameId")
            if not game_id:
                continue
            games.append({
                "game_id": game_id.text,
                "home_team": game.find("homeTeamName").text,
                "away_team": game.find("awayTeamName").text,
                "home_score": game.find("homeScore").text,
                "away_score": game.find("awayScore").text,
                "stadium": game.find("stadiumName").text,
                "status": game.find("statusInfo").text
            })
        
        return games

    def get_boxscore(self, game_id: str) -> dict:
        payload = {
            "gameId": game_id,
            "leagueId": "1"
        }
        
        resp = requests.post(
            self.BOXSCORE_URL,
            data=payload,
            headers=self.HEADERS,
            timeout=10
        )
        
        soup = BeautifulSoup(resp.text, "lxml-xml")
        
        pitchers = {"home": [], "away": []}
        for pitcher in soup.find_all("pitcher"):
            team_type = "home" if pitcher.find("teamType").text == "H" else "away"
            is_starter = pitcher.find("startYn")
            pitchers[team_type].append({
                "name": pitcher.find("playerName").text,
                "result": pitcher.find("pitchResult").text if pitcher.find("pitchResult") else "",
                "ip": pitcher.find("inning").text if pitcher.find("inning") else "0",
                "h": pitcher.find("hit").text if pitcher.find("hit") else "0",
                "bb": pitcher.find("bb").text if pitcher.find("bb") else "0",
                "k": pitcher.find("kk").text if pitcher.find("kk") else "0",
                "er": pitcher.find("er").text if pitcher.find("er") else "0",
                "era": pitcher.find("era").text if pitcher.find("era") else "0",
                "is_starter": is_starter.text == "Y" if is_starter else False
            })
        
        return {"pitchers": pitchers}

    def collect_daily(self, date: str) -> dict:
        print(f"[KBO] {date} 수집 시작")
        
        games = self.get_daily_schedule(date)
        result = {
            "date": date,
            "league": "KBO",
            "games": []
        }
        
        for game in games:
            if game["status"] != "종료":
                continue
            
            time.sleep(0.5)
            
            try:
                boxscore = self.get_boxscore(game["game_id"])
            except Exception as e:
                print(f"  ⚠️ 박스스코어 오류 {game['game_id']}: {e}")
                boxscore = {"pitchers": {"home": [], "away": []}}
            
            home_score = int(game["home_score"]) if game["home_score"] else 0
            away_score = int(game["away_score"]) if game["away_score"] else 0
            total_runs = home_score + away_score
            
            home_starter = next(
                (p for p in boxscore["pitchers"]["home"] if p["is_starter"]), {}
            )
            away_starter = next(
                (p for p in boxscore["pitchers"]["away"] if p["is_starter"]), {}
            )
            
            game_data = {
                **game,
                "total_runs": total_runs,
                "winner": game["home_team"] if home_score > away_score else game["away_team"],
                "home_starter": home_starter,
                "away_starter": away_starter,
                "summary": self._make_summary(game, home_starter, away_starter, total_runs)
            }
            
            result["games"].append(game_data)
            print(f"  ✅ {game['away_team']} vs {game['home_team']} {away_score}-{home_score}")
        
        return result

    def _make_summary(self, game, home_starter, away_starter, total_runs) -> str:
        return (
            f"[KBO] {game['home_team']} vs {game['away_team']}\n"
            f"선발: {home_starter.get('name','?')}(홈) vs {away_starter.get('name','?')}(원정)\n"
            f"결과: {game['home_team']} {game['home_score']}-{game['away_score']} {game['away_team']}\n"
            f"승자: {game['home_team'] if int(game['home_score'] or 0) > int(game['away_score'] or 0) else game['away_team']}\n"
            f"홈선발: {home_starter.get('ip','?')}이닝 {home_starter.get('er','?')}자책 {home_starter.get('k','?')}K\n"
            f"원정선발: {away_starter.get('ip','?')}이닝 {away_starter.get('er','?')}자책 {away_starter.get('k','?')}K\n"
            f"총득점: {total_runs}\n"
            f"구장: {game['stadium']}"
        )
