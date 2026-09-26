# -*- coding: utf-8 -*-
"""09_probe_video.py — 探查飞瓜商品详情「带货视频」tab 的真实 DOM / 文本结构"""
import json, os, subprocess, sys, time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 自动定位：.../用户调研模块
WORKSPACE = os.path.dirname(BASE)
TMP = os.path.join(WORKSPACE, "tmp")
os.makedirs(TMP, exist_ok=True)
WB = "http://127.0.0.1:10086/command"
SESSION = "xhs-user-research"
REQ = os.path.join(TMP, "req_social.json")

GID, SIGN, TS = "3Z649OBD1oFEBM7YnOjwcJ410p8vmBFjA", "10d4613389633a583b0a8f82309b91fd", "1790244793"


def wb(action, args=None):
    with open(REQ, "w", encoding="utf-8") as f:
        json.dump({"action": action, "args": args or {}, "session": SESSION}, f, ensure_ascii=False)
    try:
        r = subprocess.run(["curl.exe", "-s", "-X", "POST", WB, "-H", "Content-Type: application/json",
                            "--data-binary", "@" + REQ], capture_output=True, text=True,
                           encoding="utf-8", timeout=60)
        return json.loads(r.stdout)
    except Exception as e:
        return {"ok": False, "err": str(e)}


def ev(code):
    r = wb("evaluate", {"code": code})
    if not r.get("ok"):
        return "ERR:" + str(r)[:200]
    try:
        return json.loads(r["data"]["value"])
    except Exception:
        return r["data"].get("value", "")


url = f"https://dy.feigua.cn/app/#/goods-detail/index?id=&gid={GID}&tab=video&ts={TS}&sign={SIGN}"
print("navigate:", wb("navigate", {"url": url}).get("ok"))
time.sleep(9)
print("url now:", ev("location.href"))
CLICK = ("(() => { var els=[...document.querySelectorAll('div,span,a,li,button')]"
         ".filter(function(e){ var t=(e.innerText||'').trim(); return t.indexOf('带货视频')===0 && t.length<12 && e.children.length<=2; });"
         "if(els.length){ els[els.length-1].click(); return 'ok:'+els[els.length-1].innerText.trim(); } return 'nf'; })()")
print("click tab:", ev(CLICK))
time.sleep(10)
txt = ev("document.body.innerText")
print("=== TEXT (3000-9000 字) ===")
print((txt or "")[3000:9000])
print("\n=== 候选行容器 class ===")
print(ev("Array.from(document.querySelectorAll('[class*=row],[class*=item],[class*=list]')).slice(0,40).map(e=>e.className).join(' | ')"))
