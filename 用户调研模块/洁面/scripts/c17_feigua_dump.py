# -*- coding: utf-8 -*-
"""c17_feigua_dump.py — dump 实时爆款商品页的真实 DOM 结构（表格/行/链接/类名）"""
import json, os, subprocess, time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.dirname(os.path.dirname(BASE))
TMP = os.path.join(WORKSPACE, "tmp")
os.makedirs(TMP, exist_ok=True)
WB = "http://127.0.0.1:10086/command"
SESSION = "fg-cleanser-dump"
REQ = os.path.join(TMP, "req_c17.json")


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


JS = """(() => {
  const info = {};
  info.url = location.href;
  info.bodyLen = (document.body.innerText||'').length;
  // 所有含 gid 的链接
  const as=[...document.querySelectorAll('a[href]')].map(a=>a.getAttribute('href')).filter(h=>h&&h.indexOf('gid=')>=0);
  info.nGidLinks = as.length; info.gidSample = as.slice(0,3);
  // 任何元素的 data-* 里含 gid
  const ds=[...document.querySelectorAll('*')].map(e=>e.getAttribute&&e.getAttribute('data-gid')).filter(Boolean);
  info.dataGid = ds.slice(0,5);
  // 表格结构
  info.tables = [...document.querySelectorAll('table')].length;
  info.trs = [...document.querySelectorAll('tr')].length;
  // 找最像"行容器"的类名（重复出现 >=5 次、且 innerText 长度 > 40）
  const cnt={};
  [...document.querySelectorAll('div,li,section')].forEach(e=>{
    const t=(e.innerText||'').trim(); if(t.length<40||t.length>900) return;
    const c=(e.className||'').toString().split(' ')[0]; if(!c) return;
    cnt[c]=(cnt[c]||0)+1;
  });
  info.repeatCls = Object.entries(cnt).filter(([k,v])=>v>=5).sort((a,b)=>b[1]-a[1]).slice(0,15);
  // 候选行：className 首词重复 >=5
  const picked=[];
  const names = info.repeatCls.map(x=>x[0]);
  for (const n of names.slice(0,6)) {
    const els=[...document.querySelectorAll('.'+n)].slice(0,2);
    els.forEach(e=>picked.push({cls:n, len:(e.innerText||'').length,
      txt:(e.innerText||'').replace(/\\n/g,'|').slice(0,300),
      htmlHead:(e.innerHTML||'').slice(0,600)}));
  }
  info.picked = picked;
  return JSON.stringify(info);
})()"""


def main():
    wb("navigate", {"url": "https://dy.feigua.cn/app/#/real-time-goods-rank/index"}, wait=11)
    print("URL:", ev("location.href"), flush=True)
    v = ev(JS, wait=2)
    try:
        d = json.loads(v)
        print("bodyLen:", d["bodyLen"], "| tables:", d["tables"], "| trs:", d["trs"], flush=True)
        print("nGidLinks:", d["nGidLinks"], flush=True)
        print("gidSample:", json.dumps(d["gidSample"], ensure_ascii=False), flush=True)
        print("dataGid:", json.dumps(d["dataGid"], ensure_ascii=False), flush=True)
        print("\n重复类名(候选行容器):", json.dumps(d["repeatCls"], ensure_ascii=False), flush=True)
        print("\n--- 候选行样本 ---", flush=True)
        for p in d.get("picked", [])[:6]:
            print(f"\n[cls={p['cls']}] len={p['len']}", flush=True)
            print("  txt:", p["txt"][:260], flush=True)
            print("  html:", p["htmlHead"][:400], flush=True)
    except Exception as e:
        print("parse fail:", e, v[:800], flush=True)
    open(os.path.join(TMP, "fg_rank_dump.txt"), "w", encoding="utf-8").write(v)


if __name__ == "__main__":
    main()
