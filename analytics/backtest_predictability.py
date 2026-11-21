"""리그별 '예측 가능성' 백테스트 (배당 없음 → 단순 모델 적중률로 비교)

모델(모든 리그 동일):
  - 승패: 시즌 누적 경기당 득실차가 큰 팀 승리 예측 (양 팀 모두 MIN_GP경기 이상 소화 후)
          → 전체 적중률 + 득실차 격차 상위 1/3(확신 구간) 적중률
          축구는 무승부 = 실패(1X2 승리 기준), 하키는 정규시간 승리 기준도 따로 표시
  - 토탈: 예측 토탈 = (홈 득점+원정 실점+원정 득점+홈 실점)/2 (시즌 누적)
          기준선 = 리그 시즌 누적 평균. |예측-기준| 상위 1/3 경기에서 방향(오버/언더) 적중률
          + 예측 vs 실제 상관계수 r
  - 홈 승률(기준값)
사용: python analytics/backtest_predictability.py  → analytics/predictability_backtest.json
"""
import glob
import json
import os
import statistics as st
from collections import defaultdict
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN_GP = 8
LEAGUES = {  # 리그: (종목, 하키 정규시간 키 사용 여부)
    "ABL": "baseball", "LMP": "baseball", "MLB": "baseball",
    "NHL": "hockey", "KHL": "hockey", "LIIGA": "hockey", "SHL": "hockey", "DEL": "hockey", "CZE": "hockey", "AHL": "hockey", "OHL": "hockey",
    "NBA": "basketball", "NBL": "basketball", "KBL": "basketball", "WKBL": "basketball", "BLEAGUE": "basketball",
    "J1": "soccer", "K1": "soccer", "J2": "soccer",
}


def load(league):
    seen = {}
    for sub in ("historical", "daily"):
        for f in sorted(glob.glob(os.path.join(ROOT, "data", league, sub, "*.json"))):
            try:
                d = json.load(open(f, encoding="utf-8"))
            except Exception:
                continue
            fdate = os.path.basename(f)[:8]
            for g in d.get("games", []):
                if g.get("home_score") is None or g.get("away_score") is None:
                    continue
                gt = g.get("game_type")
                if gt and gt not in ("REG", "R", "FINAL_A", "FINAL_B"):
                    continue
                g = dict(g)
                g["_date"] = (g.get("date_kst") or fdate)
                seen[str(g.get("game_id")) + g["home_team"]] = g
    gs = sorted(seen.values(), key=lambda g: (g["_date"], g.get("start_utc") or ""))
    # 시즌 구분: 60일 이상 공백이면 새 시즌
    season, prev = 0, None
    for g in gs:
        d = datetime.strptime(g["_date"], "%Y%m%d")
        if prev and (d - prev).days > 60:
            season += 1
        g["_season"], prev = season, d
    return gs


def run(league, sport):
    gs = load(league)
    if len(gs) < 60:
        return None
    ml_all, ml_conf, ml_reg_conf, tot_dir, pred_act, home_w, draws = [], [], [], [], [], [], 0
    cand = []
    cur, tm, lg = None, None, None
    for g in gs:
        if g["_season"] != cur:
            cur, tm, lg = g["_season"], defaultdict(lambda: [0, 0, 0]), [0, 0]
        h, a = g["home_team"], g["away_team"]
        hs, as_ = g["home_score"], g["away_score"]
        th, ta = tm[h], tm[a]
        if th[0] >= MIN_GP and ta[0] >= MIN_GP:
            dh, da = (th[1] - th[2]) / th[0], (ta[1] - ta[2]) / ta[0]
            gap = abs(dh - da)
            pick_home = dh > da
            won = (hs > as_) if pick_home else (as_ > hs)
            reg_won = None
            if sport == "hockey" and g.get("reg_home_score") is not None:
                rh, ra = g["reg_home_score"], g["reg_away_score"]
                reg_won = (rh > ra) if pick_home else (ra > rh)
            pred = (th[1] / th[0] + ta[2] / ta[0] + ta[1] / ta[0] + th[2] / th[0]) / 2
            base = lg[0] / lg[1]
            cand.append((gap, won, reg_won, pred - base, hs + as_ - base, pred, hs + as_))
        home_w.append(hs > as_)
        draws += hs == as_
        for t, f_, a_ in ((h, hs, as_), (a, as_, hs)):
            tm[t][0] += 1; tm[t][1] += f_; tm[t][2] += a_
        lg[0] += hs + as_; lg[1] += 1
    if len(cand) < 30:
        return None
    n = len(cand)
    by_gap = sorted(cand, key=lambda c: -c[0])[: n // 3]
    by_dev = sorted(cand, key=lambda c: -abs(c[3]))[: n // 3]
    dir_hits = [(c[3] > 0) == (c[4] > 0) for c in by_dev if c[4] != 0]
    r = st.correlation([c[5] for c in cand], [c[6] for c in cand]) if n > 2 else None
    out = {
        "sport": sport, "games_total": len(gs), "games_tested": n,
        "home_win_pct": round(sum(home_w) / len(home_w), 3),
        "draw_pct": round(draws / len(gs), 3),
        "ml_hit_all": round(sum(c[1] for c in cand) / n, 3),
        "ml_hit_top_third": round(sum(c[1] for c in by_gap) / len(by_gap), 3),
        "total_dir_hit_top_third": round(sum(dir_hits) / len(dir_hits), 3) if dir_hits else None,
        "total_pred_r": round(r, 3) if r is not None else None,
    }
    if sport == "hockey":
        reg = [c[2] for c in by_gap if c[2] is not None]
        out["reg_win_hit_top_third"] = round(sum(reg) / len(reg), 3) if reg else None
    return out


if __name__ == "__main__":
    res = {}
    for lg, sp in LEAGUES.items():
        r = run(lg, sp)
        if r:
            res[lg] = r
    with open(os.path.join(ROOT, "analytics/predictability_backtest.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    hdr = f'{"리그":8}{"검증":>6}{"홈승":>7}{"ML전체":>8}{"ML상위⅓":>9}{"정규승⅓":>9}{"토탈방향⅓":>10}{"r":>7}'
    print(hdr)
    for lg, r in res.items():
        print(f'{lg:8}{r["games_tested"]:>6}{r["home_win_pct"]:>7}{r["ml_hit_all"]:>8}{r["ml_hit_top_third"]:>9}'
              f'{str(r.get("reg_win_hit_top_third") or "-"):>9}{str(r["total_dir_hit_top_third"]):>10}{str(r["total_pred_r"]):>7}')
