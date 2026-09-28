# -*- coding: utf-8 -*-
"""c10_feigua_probe.py — 探测飞瓜商品库页面控件（一级类目筛选 + 关键词搜索框），并尝试取商品行"""
import json, os, subprocess, time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.dirname(os.path.dirname(BASE))
TMP = os.path.join(WORKSPACE, "tmp")
os.makedirs(TMP, exist_ok=True)
WB = "http://127.0.0.1:10086/command"
SESSION = "fg-cleanser"
REQ = os.path.join(TMP, "req_c10.json")
DUMP = os.path.join(TMP, "fg_probe_dump.txt")


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


JS_UI = """(() => {
  const ins=[...document.querySelectorAll('input')].map(i=>({
    ph:i.placeholder||'', val:i.value||'', cls:(i.className||'').slice(0,60)}));
  const btns=[...document.querySelectorAll('button,.el-button,.el-tabs__item,li')]
    .map(b=>(b.innerText||'').trim()).filter(t=>t&&t.length<20).slice(0,60);
  const href=[...document.querySelectorAll('a[href]')].map(a=>a.getAttribute('href'))
    .filter(h=>h&&h.indexOf('gid=')>=0).slice(0,5);
  return JSON.stringify({ins, btns, hrefSample:href, len:(document.body.innerText||'').length,
    head:(document.body.innerText||'').slice(0,600)});
})()"""

JS_ROWS = """(() => {
  const rows=[...document.querySelectorAll('tr')].map(tr=>{
    const a=tr.querySelector('a[href]');
    const gid=a?(a.getAttribute('href').match(/gid=([A-Za-z0-9]+)/)||[])[1]||'':'';
    return {txt:(tr.innerText||'').replace(/\\n/g,'|'), gid};
  }).filter(r=>r.txt.length>20);
  return JSON.stringify({n:rows.length, rows:rows.slice(0,25)});
})()"""


def main():
    wb("navigate", {"url": "https://dy.feigua.cn/app/#/goods-library/index"}, wait=9)
    print("URL:", ev("location.href"), flush=True)
    ui = ev(JS_UI, wait=2)
    open(DUMP, "w", encoding="utf-8").write(ui)
    try:
        d = json.loads(ui)
        print("page len:", d.get("len"), flush=True)
        print("inputs:", json.dumps(d.get("ins", [])[:12], ensure_ascii=False), flush=True)
        print("btns:", json.dumps(d.get("btns", [])[:40], ensure_ascii=False), flush=True)
        print("hrefSample:", json.dumps(d.get("hrefSample", []), ensure_ascii=False), flush=True)
        print("head:", (d.get("head") or "")[:400].replace("\n", " / "), flush=True)
    except Exception as e:
        print("parse fail", e, ui[:500], flush=True)
    rows = ev(JS_ROWS, wait=1)
    try:
        d = json.loads(rows)
        print("\n行数:", d.get("n"), flush=True)
        for i, r in enumerate(d.get("rows", [])[:8], 1):
            print(f"  {i}. gid={r['gid'][:14]} {r['txt'][:150]}", flush=True)
    except Exception as e:
        print("rows parse fail", e, rows[:300], flush=True)


if __name__ == "__main__":
    main()
