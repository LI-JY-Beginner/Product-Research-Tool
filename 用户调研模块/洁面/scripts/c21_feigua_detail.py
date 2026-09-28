# -*- coding: utf-8 -*-
"""
c21_feigua_detail.py — 飞瓜商品详情页采集：受众画像 + 商品评价

★ 关键思路（复用产品调研模块 g35 的成功做法）：
  飞瓜 v3 接口的 Data 大量是加密串，但**页面自己会解密并渲染**。
  所以不硬解接口，而是：
    1) 挂 fetch/XHR 钩子 → 2) navigate 到详情页 → 3) 点各 tab 触发页面自己发请求
    4) 从钩子里读**请求体**（明文参数），或直接读**渲染后的 innerText** 解析
  两条腿走路，哪条通就用哪条。

用法:
  python c21_feigua_detail.py <gid> <sign>          # 采一个商品（打印探测结果）
  python c21_feigua_detail.py --batch <json文件>     # 批量（文件为 [{gid,sign},...]）
"""
import json, os, re, subprocess, sys, time
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.dirname(os.path.dirname(BASE))
TMP = os.path.join(WORKSPACE, "tmp")
os.makedirs(TMP, exist_ok=True)
RAW = os.path.join(BASE, "raw")
os.makedirs(RAW, exist_ok=True)
WB = "http://127.0.0.1:10086/command"
SESSION = "fg-cleanser-detail"
REQ = os.path.join(TMP, "req_c21.json")
HELPER = os.path.join(BASE, "tmp", "_helper.js")
TODAY = datetime.now().strftime("%Y-%m-%d")


def wb(action, args=None, wait=0, timeout=150):
    with open(REQ, "w", encoding="utf-8") as f:
        json.dump({"action": action, "args": args or {}, "session": SESSION}, f, ensure_ascii=False)
    try:
        r = subprocess.run(["curl.exe", "-s", "--noproxy", "*", "-X", "POST", WB,
                            "-H", "Content-Type: application/json", "--data-binary", "@" + REQ],
                           capture_output=True, text=True, encoding="utf-8", timeout=timeout)
        return json.loads(r.stdout)
    except Exception as e:
        return {"ok": False, "err": str(e)}
    finally:
        if wait:
            time.sleep(wait)


def ev(code, wait=0):
    r = wb("evaluate", {"code": code}, wait=wait)
    if not r.get("ok"):
        return None
    try:
        return json.loads(r["data"]["value"])
    except Exception:
        return r["data"].get("value")


def body_text():
    t = ev("document.body.innerText")
    return t if isinstance(t, str) else ""


HOOK = r"""
(function(){
  if(window.__hooked) return 'already';
  window.__hooked = true;
  window.__cap = [];
  function rec(o){ try{ window.__cap.push(o); if(window.__cap.length>400) window.__cap.shift(); }catch(e){} }
  var _f = window.fetch;
  window.fetch = function(){
    var a=arguments, u=(typeof a[0]==='string')?a[0]:((a[0]&&a[0].url)||'');
    var opt=a[1]||{}, rb=opt.body?String(opt.body).slice(0,4000):'';
    return _f.apply(this,a).then(function(r){
      try{ r.clone().text().then(function(tx){ rec({t:'fetch',url:u,method:opt.method||'GET',
        reqBody:rb,status:r.status,len:(tx||'').length,body:(tx||'').slice(0,80000)}); })['catch'](function(){}); }catch(e){}
      return r;
    });
  };
  var _o=XMLHttpRequest.prototype.open, _s=XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open=function(m,u){ this.__u=u; this.__m=m; return _o.apply(this,arguments); };
  XMLHttpRequest.prototype.send=function(d){
    var self=this, rb=d?String(d).slice(0,4000):'';
    this.addEventListener('load', function(){
      var tx=''; try{ tx=(typeof self.responseText==='string')?self.responseText:''; }catch(e){}
      rec({t:'xhr',url:self.__u,method:self.__m,reqBody:rb,status:self.status,
           len:tx.length,body:tx.slice(0,80000)});
    });
    return _s.apply(this,arguments);
  };
  return 'hooked';
})()
"""


def install_hook():
    return ev(HOOK)


def cap(kw=None):
    raw = ev("JSON.stringify(window.__cap||[])")
    try:
        items = json.loads(raw) if isinstance(raw, str) else (raw or [])
    except Exception:
        items = []
    if kw:
        items = [x for x in items if kw in (x.get("url") or "")]
    return items


def clear_cap():
    ev("window.__cap=[]")


def open_detail(gid, sign, ts=None):
    """在商品榜页（同源）内切 hash 到详情页"""
    url = ("https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=%s&tab=overview" % gid)
    if ts:
        url += "&ts=%s&sign=%s" % (ts, sign)
    elif sign:
        url += "&ts=1790582561&sign=%s" % sign
    wb("navigate", {"url": url}, wait=8)
    time.sleep(6)
    ev(HELPER)
    ev("window.__killMask()")
    return body_text()


CLICK_TAB = """(function(){
  var want=%s;
  var els=[].slice.call(document.querySelectorAll('[role=tab],[class*=tab-item],[class*=tabItem],div,span,li,a'))
    .filter(function(e){return (e.innerText||'').trim()===want && e.offsetParent!==null && e.children.length<=2;});
  if(!els.length) return 'nf';
  var e=els[0], r=e.getBoundingClientRect();
  var x=Math.round(r.left+r.width/2), y=Math.round(r.top+r.height/2);
  var o={bubbles:true,cancelable:true,view:window,clientX:x,clientY:y,screenX:x,screenY:y,
         pointerId:1,pointerType:'mouse',isPrimary:true,button:0,buttons:1};
  e.dispatchEvent(new PointerEvent('pointerdown',o));
  e.dispatchEvent(new MouseEvent('mousedown',o));
  e.dispatchEvent(new PointerEvent('pointerup',Object.assign({},o,{buttons:0})));
  e.dispatchEvent(new MouseEvent('mouseup',Object.assign({},o,{buttons:0})));
  e.dispatchEvent(new MouseEvent('click',Object.assign({},o,{buttons:0})));
  return 'ok:'+e.innerText.trim()+':'+x+','+y;
})()"""


def click_tab(label):
    r = ev(CLICK_TAB % json.dumps(label, ensure_ascii=False))
    if r and str(r).startswith("nf"):
        # 兜底：用 helper
        r = ev("window.__clickText(%s)" % json.dumps(label, ensure_ascii=False))
    return r


def probe(gid, sign, ts=None):
    open_detail(gid, sign, ts)
    print("详情页 len:", len(body_text()), flush=True)
    install_hook()
    clear_cap()

    for tab in ("商品评价", "受众画像"):
        print(f"\n>>> 点「{tab}」", flush=True)
        print("   ", click_tab(tab), flush=True)
        time.sleep(8)
        ev("window.__killMask()")
        hits = cap()
        print(f"   捕获 {len(hits)} 个请求", flush=True)
        for x in hits[-8:]:
            u = x.get("url") or ""
            print(f"     [{x['status']}] {u[:120]}", flush=True)
            if x.get("reqBody"):
                print(f"        req: {x['reqBody'][:200]}", flush=True)
            b = x.get("body") or ""
            if b:
                try:
                    j = json.loads(b)
                    D = j.get("Data")
                    dt = type(D).__name__
                    extra = ""
                    if isinstance(D, str):
                        extra = " (encrypted str len=%d)" % len(D)
                    elif isinstance(D, dict):
                        extra = " keys=" + ",".join(list(D.keys())[:12])
                    print(f"        resp: Code={j.get('Code')} DataType={dt}{extra}", flush=True)
                except Exception:
                    print(f"        respHead: {b[:120]}", flush=True)
        st = body_text()
        i = st.find(tab)
        print(f"   DOM 段: {(st[i:i+600] if i>=0 else st[:400]).replace(chr(10),' | ')}", flush=True)
        clear_cap()

    open(os.path.join(TMP, f"c21_probe_{gid[:10]}.txt"), "w", encoding="utf-8").write(body_text())


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "--batch":
        batch = json.load(open(a[1], encoding="utf-8"))
        for i, it in enumerate(batch, 1):
            print(f"\n===== [{i}/{len(batch)}] {it['gid'][:14]} =====", flush=True)
            probe(it["gid"], it.get("sign", ""), it.get("ts"))
    elif len(a) >= 2:
        probe(a[0], a[1], a[2] if len(a) > 2 else None)
    else:
        print("用法: python c21_feigua_detail.py <gid> <sign> [ts]")
