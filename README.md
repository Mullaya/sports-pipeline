# sports-pipeline
KBO/NPB/MLB/NHL 등 자동 수집

- NHL: `collectors/nhl_collector.py` (api-web.nhle.com) → `data/NHL/daily/YYYYMMDD.json`
- NHL 집계: `analytics/build_nhl_stats.py` → `analytics/NHL_stats.json` (팀·골리·H2H·리더, 매 실행 재계산)
- 지난 시즌 백필: Historical Data Load 워크플로우에서 league=NHL


- V-리그: `collectors/kovo_collector.py` (네이버 스포츠 API, 남자 kovo / 여자 wkovo, 컵대회 포함) → `data/KOVO/daily/YYYYMMDD kovo.json`, `data/WKOVO/daily/YYYYMMDD wkovo.json`
- V-리그 집계: `analytics/build_kovo_stats.py` → `analytics/KOVO_stats.json`, `analytics/WKOVO_stats.json` (승점·세트/점수 득실률·세트당 공격/블로킹/서브/리시브/범실·세트 수 분포·총점·휴식일·컵대회 별도·리더·H2H)
- 지난 시즌 백필: Historical Data Load 워크플로우에서 league=KOVO / WKOVO

- KHL: `collectors/khl_collector.py` (KHL 모바일 API) → `data/KHL/daily/YYYYMMDD khl.json` (모스크바 날짜)
- 독일 DEL·체코 엑스트라리가: `collectors/flashscore_hockey_collector.py` (Flashscore 피드, 공식 hokej.cz는 Actions IP 차단) → `data/DEL/daily/YYYYMMDD del.json`, `data/CZE/daily/YYYYMMDD cze.json` (중부유럽 날짜). 시즌 결과 목록 기반이라 날짜 제한 없이 재수집·백필 가능
- 유럽 하키 집계: `analytics/build_hockey_stats.py KHL DEL CZE` → `analytics/{KHL,DEL,CZE}_stats.json` (승점순위·홈/원정·최근10·정규시간 3-way/언오버·슈팅점유율·SV%/PDO·PP/PK·휴식일/백투백·선발골리·리더·지난시즌·H2H). 승점 규칙: KHL 2-2-1, DEL/체코 3-2-1
- 누락 재수집: 자동 실행 때 최근 7일 중 파일 없는 날짜를 다시 수집 (NHL·NBA·KHL·DEL·CZE·KBL·KOVO·WKOVO)
- 지난 시즌 백필: Historical Data Load 워크플로우에서 league=KHL / DEL / CZE
