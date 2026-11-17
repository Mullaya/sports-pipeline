import requests, re
S = requests.Session(); S.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124.0"})
r = S.post("https://www.wkbl.or.kr/game/ajax/ajax_game_result_2.asp",
           data={"season_gu": "047", "game_type": "01", "game_no": "14", "ym": "", "h_player": "", "a_player": ""},
           headers={"Referer": "https://www.wkbl.or.kr/game/result.asp"}, timeout=30)
r.encoding = "utf-8"; t = r.text
i = t.find("2PM-A"); print("RAW1", t[i-1500:i+2500])
j = t.find("2PM-A", i + 10); print("\nRAW2", t[j-900:j+300])
k = t.rfind("</table>"); print("\nTAIL", re.sub(r"\s+", " ", t[k-2500:k+50]))
