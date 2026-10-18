import requests,re
H={"x-fsign":"SW9D1eZo","Referer":"https://www.flashscore.com/","Origin":"https://www.flashscore.com","User-Agent":"Mozilla/5.0"}
t=requests.get("https://global.flashscore.ninja/2/x/feed/df_st_1_OMYslka3",headers=H,timeout=20).text
sec=None
for b in t.split("~"):
    d=dict(kv.split("÷",1) for kv in b.split("¬") if "÷" in kv)
    if "SE" in d: sec=d["SE"]
    elif "SG" in d and sec=="Match": print(d["SG"],"|",d.get("SH"),"|",d.get("SI"))
t=requests.get("https://global.flashscore.ninja/2/x/feed/df_sui_1_OMYslka3",headers=H,timeout=20).text
print("penalty events home/away", t.count("IA÷1¬")-0, t.count("IA÷2¬"), "PEN", len(re.findall(r"IK÷Penalty",t)))
for b in t.split("~"):
    if "Penalty" in b: print("  ",re.search(r"IA÷(\d)",b).group(1), re.search(r"IB÷([^¬]*)",b).group(1), re.search(r"IK÷([^¬]*)",b).group(1))
