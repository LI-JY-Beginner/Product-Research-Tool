# -*- coding: utf-8 -*-
"""c13_feigua_nav.py — 点顶部导航「商品/SPU」进入商品库，dump 真实路由 + 控件 + 商品行"""
import json, os, subprocess, time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.dirname(os.path.dirname(BASE))
TMP = os.path.join(WORKSPACE, "tmp")
os.makedirs(TMP, exist_ok=True)
WB = "http://127.0.0.1:10086/command"
SESSION = "fg-cleanser-nav"
REQ = os.path.join(TMP, "req_c13.json")
DUMP = os.path.join(TMP, "fg_nav_dump.txt")


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


# 点击文本完全等于 / 包含目标文案的可点元素（带完整指针事件序列）
JS_CLICK = """(() => {
  const want = %s;
  const all = [...document.querySelectorAll('a,li,span,div,button')];
  const cands = all.filter(e => {
    const t = (e.innerText||'').trim();
    return t === want && e.children.length <= 1;
  });
  if (!cands.length) return 'NOTFOUND';
  const el = cands[cands.length-1];
  const r = el.getBoundingClientRect();
  const opts = {bubbles:true, cancelable:true, view:window,
                clientX:r.left+r.width/2, clientY:r.top+r.height/2};
  ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(t => {
    const E = t.startsWith('pointer') ? PointerEvent : MouseEvent;
    el.dispatchEvent(new E(t, opts));
  });
  return 'CLICKED:' + el.tagName + ':' + el.innerText.trim().slice(0,20);
})()"""

JS_UI = """(() => {
  const ins=[...document.querySelectorAll('input')].map(i=>({
    ph:i.placeholder||'', val:i.value||'', cls:(i.className||'').slice(0,60)}));
  const tabs=[...document.querySelectorAll('.el-tabs__item,.el-select,.el-radio-button,button')]
    .map(b=>(b.innerText||'').trim()).filter(t=>t&&t.length<26).slice(0,60);
  const hrefs=[...document.querySelectorAll('a[href]')].map(a=>a.getAttribute('href'))
    .filter(h=>h&&h.indexOf('gid=')>=0).slice(0,6);
  const body=document.body.innerText||'';
  return JSON.stringify({url:location.href, hash:location.hash, len:body.length,
    ins, tabs, hrefs, head:body.slice(0,900)});
})()"""

JS_ROWS = """(() => {
  const rows=[...document.querySelectorAll('tr,.el-table__row')].map(tr=>{
    const a=tr.querySelector('a[href]');
    const gid=a?(a.getAttribute('href').match(/gid=([A-Za-z0-9]+)/)||[])[1]||'':'';
    return {txt:(tr.innerText||'').replace(/\\n/g,'|'), gid};
  }).filter(r=>r.txt.length>20);
  return JSON.stringify({n:rows.length, rows:rows.slice(0,25)});
})()"""


def show(tag, js, wait=0):
    v = ev(js, wait=wait)
    print(f"\n---- {tag} ----", flush=True)
    try:
        d = json.loads(v)
        for k in ("url", "hash", "len", "n"):
            if k in d:
                print(f"  {k}: {d[k]}", flush=True)
        if "ins" in d:
            print("  inputs:", json.dumps(d["ins"][:10], ensure_ascii=False), flush=True)
        if "tabs" in d:
            print("  tabs:", json.dumps(d["tabs"][:40], ensure_ascii=False), flush=True)
        if "hrefs" in d:
            print("  hrefs:", json.dumps(d["hrefs"], ensure_ascii=False), flush=True)
        if "head" in d:
            print("  head:", (d["head"] or "")[:500].replace("\n", " / "), flush=True)
        if "rows" in d:
            for i, r in enumerate(d["rows"][:8], 1):
                print(f"  {i}. gid={r['gid'][:16]} {r['txt'][:140]}", flush=True)
    except Exception as e:
        print("  (raw)", v[:600], flush=True)
    open(DUMP, "a", encoding="utf-8").write(f"\n==== {tag} ====\n{v}\n")


def main():
    open(DUMP, "w", encoding="utf-8").write("fg nav probe\n")

    wb("navigate", {"url": "https://dy.feigua.cn/app/"}, wait=10)
    show("首页", JS_UI)

    print("\n>>> 点击「商品/SPU」", flush=True)
    print("   ", ev(JS_CLICK % json.dumps("商品/SPU", ensure_ascii=False)), flush=True)
    time.sleep(6)
    show("点完后", JS_UI, wait=1)
    show("商品行", JS_ROWS, wait=1)

    # 落一个可以继续操作的好页面
    print("\n最终 URL:", ev("location.href"), flush=True)


if __name__ == "__main__":
    main()
