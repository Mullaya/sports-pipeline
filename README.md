# sports-pipeline
KBO/NPB/MLB/NHL 등 자동 수집

- NHL: `collectors/nhl_collector.py` (api-web.nhle.com) → `data/NHL/daily/YYYYMMDD.json`
- NHL 집계: `analytics/build_nhl_stats.py` → `analytics/NHL_stats.json` (팀·골리·H2H·리더, 매 실행 재계산)
- 지난 시즌 백필: Historical Data Load 워크플로우에서 league=NHL


- V-리그: `collectors/kovo_collector.py` (네이버 스포츠 API, 남자 kovo / 여자 wkovo, 컵대회 포함) → `data/KOVO/daily/YYYYMMDD kovo.json`, `data/WKOVO/daily/YYYYMMDD wkovo.json`
- V-리그 집계: `analytics/build_kovo_stats.py` → `analytics/KOVO_stats.json`, `analytics/WKOVO_stats.json` (승점·세트/점수 득실률·세트당 공격/블로킹/서브/리시브/범실·세트 수 분포·총점·휴식일·컵대회 별도·리더·H2H)
- 지난 시즌 백필: Historical Data Load 워크플로우에서 league=KOVO / WKOVO
