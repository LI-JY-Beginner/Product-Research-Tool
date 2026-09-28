# -*- coding: utf-8 -*-
"""c12_feigua_menu.py — 从飞瓜顶部导航「商品/SPU」进入，拿到真实路由 + 商品行"""
import json, os, subprocess, time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.dirname(os.path.dirname(BASE))
TMP = os.path.join(WORKSPACE, "tmp")
os.makedirs(TMP, exist_ok=True)
WB = "http://127.0.0.1:10086/command"
SESSION = "fg-cleanser"
REQ = os.path.join(TMP, "req_c12.json")


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


JS_CLICK = """(() => {
  const all=[...document.querySelectorAll('a,li,span,div')];
  const t=all.filter(e=>(e.innerText||'').trim()==='商品/SPU' || (e.innerText||'').trim().indexOf('商品/SPU')===0);
  if(!t.length) return 'NOT_FOUND';
  const e=t[0];
  try{ e.dispatchEvent(new MouseEvent('mouseover',{bubbles:true})); }catch(err){}
  try{ e.click(); }catch(err){}
  return 'CLICKED:'+(e.tagName||'');
})()"""

JS_ALL_HREF = """(() => {
  const hs=[...document.querySelectorAll('a[href]')].map(a=>a.getAttribute('href'))
    .filter(h=>h&&(h.indexOf('goods')>=0||h.indexOf('spu')>=0||h.indexOf('product')>=0));
  return JSON.stringify([...new Set(hs)].slice(0,20));
})()"""


def main():
    wb("navigate", {"url": "https://dy.feigua.cn/app/#/home/index", "newTab": True}, wait=8)
    print("start href:", ev("location.href"), flush=True)
    print("nav hrefs:", ev(JS_ALL_HREF, wait=1), flush=True)
    print("click:", ev(JS_CLICK, wait=4), flush=True)
    time.sleep(3)
    print("after href:", ev("location.href"), flush=True)
    # 再找一遍
    print("nav hrefs2:", ev(JS_ALL_HREF, wait=1), flush=True)
    t = ev("(()=>{var x=document.body.innerText||'';return JSON.stringify({len:x.length,head:x.slice(0,400)})})()") or ""
    print("page:", t[:600], flush=True)


if __name__ == "__main__":
    main()
