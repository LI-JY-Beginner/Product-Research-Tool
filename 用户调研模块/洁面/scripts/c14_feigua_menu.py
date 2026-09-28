# -*- coding: utf-8 -*-
"""c14_feigua_menu.py — 读出顶部导航「商品/SPU」的真实 href / 菜单项，并逐个尝试直达"""
import json, os, subprocess, time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.dirname(os.path.dirname(BASE))
TMP = os.path.join(WORKSPACE, "tmp")
os.makedirs(TMP, exist_ok=True)
WB = "http://127.0.0.1:10086/command"
SESSION = "fg-cleanser-menu"
REQ = os.path.join(TMP, "req_c14.json")


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


# 找到所有含「商品」的导航元素，输出其 href / 标签 / 父级结构
JS_NAVITEMS = """(() => {
  const out=[];
  document.querySelectorAll('a,li,span,div').forEach(e=>{
    const t=(e.innerText||'').trim();
    if(!t || t.length>14) return;
    if(!/商品|SPU/.test(t)) return;
    out.push({tag:e.tagName, text:t, href:e.getAttribute('href')||'',
      cls:(e.className||'').toString().slice(0,50),
      parent:(e.parentElement? (e.parentElement.className||'').toString().slice(0,40):'')});
  });
  return JSON.stringify(out.slice(0,40), null, 0);
})()"""


def main():
    wb("navigate", {"url": "https://dy.feigua.cn/app/#/workbench/index"}, wait=9)
    print("== 含「商品」的导航元素 ==", flush=True)
    v = ev(JS_NAVITEMS, wait=1)
    try:
        for x in json.loads(v):
            print(f"  {x['tag']:6} | {x['text']:10} | href={x['href'][:70]:70} | cls={x['cls'][:34]}", flush=True)
    except Exception:
        print("  raw:", v[:800], flush=True)

    # 逐个候选路由尝试
    cands = [
        "https://dy.feigua.cn/app/#/goods/index",
        "https://dy.feigua.cn/app/#/goods-list/index",
        "https://dy.feigua.cn/app/#/goods/library",
        "https://dy.feigua.cn/app/#/goods-library/index",
        "https://dy.feigua.cn/app/#/product/index",
        "https://dy.feigua.cn/app/#/spu/index",
    ]
    print("\n== 候选路由探测 ==", flush=True)
    for u in cands:
        wb("navigate", {"url": u}, wait=5)
        body = ev("(document.body.innerText||'').length + '|' + (document.body.innerText||'').slice(0,120).replace(/\\n/g,' / ')", wait=1)
        ok = "页面找不到" not in body
        print(f"  {'OK ' if ok else '404'} {u}  →  {body[:110]}", flush=True)


if __name__ == "__main__":
    main()
