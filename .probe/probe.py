import requests, re
S = requests.Session(); S.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124.0"})
t = S.get("https://www.wkbl.or.kr/game/result.asp?season_gu=047&gun=1&game_type=01&game_no=14&viewType=2", timeout=30); t.encoding="utf-8"; t=t.text
print("tab_part", sorted(set(re.findall(r'tab_part\s*=\s*["\']?(\w+)', t))), re.findall(r'h_player\s*=\s*[^;]{0,60}', t)[:3], re.findall(r'data-tab[^>]{0,60}', t)[:10])
i = t.find("ajax_game_result_"); print(re.sub(r"\s+", " ", t[i-1200:i+200]))
for part in ["01", "02", "1", "2", "player", "team"]:
    r = S.post(f"https://www.wkbl.or.kr/game/ajax/ajax_game_result_{part}.asp",
               data={"season_gu": "047", "game_type": "01", "game_no": "14", "ym": "202611", "h_player": "", "a_player": ""},
               headers={"Referer": "https://www.wkbl.or.kr/game/result.asp", "X-Requested-With": "XMLHttpRequest"}, timeout=30)
    r.encoding = "utf-8"
    print("\n### part", part, r.status_code, len(r.text))
    if r.status_code == 200 and len(r.text) > 200:
        print(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "|", r.text))[:1800])
