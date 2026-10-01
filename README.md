# sports-pipeline
KBO/NPB/MLB/NHL 등 자동 수집

- NHL: `collectors/nhl_collector.py` (api-web.nhle.com) → `data/NHL/daily/YYYYMMDD.json`
- NHL 집계: `analytics/build_nhl_stats.py` → `analytics/NHL_stats.json` (팀·골리·H2H·리더, 매 실행 재계산)
- 지난 시즌 백필: Historical Data Load 워크플로우에서 league=NHL

