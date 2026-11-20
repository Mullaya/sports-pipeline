"""호주 NBL 일별 경기 수집기 (ESPN 공개 API, NBA 수집기와 같은 스키마)

수집 단위: KST 날짜(YYYYMMDD). NBL 경기는 호주 저녁 = KST 오후~저녁이라 ESPN 날짜와 일치.
스코어·쿼터 득점·연장, ESPN 마감 라인(있을 때), 팀/선수 박스스코어 포함.
"""
from collectors.nba_collector import NBACollector


class NBLCollector(NBACollector):
    api = "https://site.api.espn.com/apis/site/v2/sports/basketball/nbl"
    league = "NBL"
