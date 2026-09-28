# -*- coding: utf-8 -*-
"""c11_feigua_route.py — 探测飞瓜「商品库」正确路由"""
import json, os, subprocess, time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.dirname(os.path.dirname(BASE))
TMP = os.path.join(WORKSPACE, "tmp")
os.makedirs(TMP, exist_ok=True)
WB = "http://127.0.0.1:10086/command"
SESSION = "fg-cleanser"
REQ = os.path.join(TMP, "req_c11.json")

ROOT = "https://dy.feigua.cn/app/"
CANDS = ["#/goods/index", "#/goods/list", "#/goods-lib/index", "#/goods/search",
         "#/goods-rank/index", "#/spu/index", "#/product/index", "#/goods/all",
         "#/goods-library/goods", "#/goodsLibrary/index", "#/goods-spu/index",
         "#/goods-center/index", "#/goodsdb/index"]


def wb(action, args=None, wait=0):
    with open(REQ, "w", encoding="utf-8") as f:
        json.dump({"action": action, "args": args or {}, "session": SESSION}, f, ensure_ascii=False)
    try:
        r = subprocess.run(["curl.exe", "-s", "-X", "POST", WB, "-H", "Content-Type: application/json",
                            "--data-binary", "@" + REQ], capture_output=True, text=True,
                           encoding="utf-8", timeout=120)
        return json.loads(r.stdout)
    except Exception as e:
        return {"ok": False, "err": str(e)}
    finally:
        if wait:
            time.sleep(wait)


def ev(code, wait=0):
    r = wb("evaluate", {"code": code}, wait=wait)
    if not r.get("ok"):
        return ""
    return r.get("data", {}).get("value", "")


def main():
    for c in CANDS:
        try:
            wb("close_tab", {}, wait=0)
        except Exception:
            pass
        wb("navigate", {"url": ROOT + c, "newTab": True}, wait=7)
        href = ev("location.href") or ""
        t = ev("(()=>{var x=document.body.innerText||'';return JSON.stringify({len:x.length,head:x.slice(0,300)})})()") or ""
        try:
            d = json.loads(t)
            ln, head = d.get("len", 0), (d.get("head") or "").replace("\n", " / ")
        except Exception:
            ln, head = len(t), t[:200]
        hit = ("找不到" not in head) and ln > 1500 and ("销量" in head or "销售额" in head or "商品" in head)
        print(f"{c:26s} len={ln:6d} href_ok={c[1:] in href} 命中={hit}", flush=True)
        if hit:
            print("   head:", head[:260], flush=True)
            rows = ev("""(()=>{const rs=[...document.querySelectorAll('tr')].map(tr=>{
              const a=tr.querySelector('a[href]');
              const gid=a?(a.getAttribute('href').match(/gid=([A-Za-z0-9]+)/)||[])[1]||'':'';
              return {txt:(tr.innerText||'').replace(/\\n/g,'|').slice(0,160), gid};})
              .filter(r=>r.txt.length>20);
              return JSON.stringify({n:rs.length, rows:rs.slice(0,6)});})()""")
            print("   rows:", rows[:900], flush=True)


if __name__ == "__main__":
    main()
