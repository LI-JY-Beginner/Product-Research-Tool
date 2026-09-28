# -*- coding: utf-8 -*-
"""c15_feigua_open_lib.py — 通过悬浮菜单点进「SPU库」，dump 真实路由与筛选控件"""
import json, os, subprocess, time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.dirname(os.path.dirname(BASE))
TMP = os.path.join(WORKSPACE, "tmp")
os.makedirs(TMP, exist_ok=True)
WB = "http://127.0.0.1:10086/command"
SESSION = "fg-cleanser-lib"
REQ = os.path.join(TMP, "req_c15.json")


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


JS_HOVER_TOP = """(() => {
  const el=[...document.querySelectorAll('.top-item')].find(e=>/商品\\/SPU/.test(e.innerText||''));
  if(!el) return 'NF';
  const r=el.getBoundingClientRect();
  const o={bubbles:true,cancelable:true,view:window,clientX:r.left+r.width/2,clientY:r.top+r.height/2};
  ['pointerover','pointerenter','mouseover','mouseenter','mousemove'].forEach(t=>{
    el.dispatchEvent(new MouseEvent(t,o));});
  return 'HOVER:'+r.left.toFixed(0)+','+r.top.toFixed(0);
})()"""

JS_CLICK_CHILD = """(() => {
  const want=%s;
  const el=[...document.querySelectorAll('.child-wrapper,.child-label')]
    .filter(e=>(e.innerText||'').trim().indexOf(want)===0)[0];
  if(!el) return 'NF';
  const t=el.classList.contains('child-wrapper')?el:(el.closest('.child-wrapper')||el);
  const r=t.getBoundingClientRect();
  const o={bubbles:true,cancelable:true,view:window,clientX:r.left+r.width/2,clientY:r.top+r.height/2};
  ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(k=>
    t.dispatchEvent(new MouseEvent(k,o)));
  return 'CLICK:'+(t.innerText||'').trim().slice(0,20);
})()"""

JS_STATE = """(() => {
  const body=document.body.innerText||'';
  const ins=[...document.querySelectorAll('input')].map(i=>({ph:i.placeholder||'',val:i.value||''}));
  const sel=[...document.querySelectorAll('.el-select,.el-dropdown')].map(e=>(e.innerText||'').trim().slice(0,30));
  const tabs=[...document.querySelectorAll('.el-tabs__item,.el-radio-button__inner')]
    .map(e=>(e.innerText||'').trim()).filter(t=>t&&t.length<24).slice(0,40);
  const btns=[...document.querySelectorAll('button,.el-button')]
    .map(e=>(e.innerText||'').trim()).filter(t=>t&&t.length<16).slice(0,30);
  const gids=[...document.querySelectorAll('a[href]')].map(a=>a.getAttribute('href'))
    .filter(h=>h&&h.indexOf('gid=')>=0).slice(0,4);
  return JSON.stringify({url:location.href, len:body.length, ins, sel, tabs, btns, gids,
    head:body.slice(0,1200)});
})()"""


def main():
    wb("navigate", {"url": "https://dy.feigua.cn/app/#/workbench/index"}, wait=9)
    print("hover:", ev(JS_HOVER_TOP), flush=True)
    time.sleep(2)
    print("click 实时爆款商品:", ev(JS_CLICK_CHILD % json.dumps("实时爆款商品", ensure_ascii=False)), flush=True)
    time.sleep(7)
    v = ev(JS_STATE, wait=1)
    try:
        d = json.loads(v)
        print("\nURL:", d["url"], flush=True)
        print("len:", d["len"], flush=True)
        print("inputs:", json.dumps(d["ins"][:10], ensure_ascii=False), flush=True)
        print("selects:", json.dumps(d["sel"][:20], ensure_ascii=False), flush=True)
        print("tabs:", json.dumps(d["tabs"][:40], ensure_ascii=False), flush=True)
        print("btns:", json.dumps(d["btns"][:30], ensure_ascii=False), flush=True)
        print("gids:", json.dumps(d["gids"], ensure_ascii=False), flush=True)
        print("head:", d["head"][:700].replace("\n", " / "), flush=True)
    except Exception:
        print("raw:", v[:1200], flush=True)


if __name__ == "__main__":
    main()
