# -*- coding: utf-8 -*-
"""c18_feigua_net.py — 挂网络钩子，点「个护家清」+搜索，抓飞瓜商品库接口的真实请求/响应"""
import json, os, subprocess, time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.dirname(os.path.dirname(BASE))
TMP = os.path.join(WORKSPACE, "tmp")
os.makedirs(TMP, exist_ok=True)
WB = "http://127.0.0.1:10086/command"
SESSION = "fg-cleanser-net"
REQ = os.path.join(TMP, "req_c18.json")


def wb(action, args=None, wait=0):
    with open(REQ, "w", encoding="utf-8") as f:
        json.dump({"action": action, "args": args or {}, "session": SESSION}, f, ensure_ascii=False)
    try:
        r = subprocess.run(["curl.exe", "-s", "-X", "POST", WB, "-H", "Content-Type: application/json",
                            "--data-binary", "@" + REQ], capture_output=True, text=True,
                           encoding="utf-8", timeout=180)
        return json.loads(r.stdout)
    except Exception as e:
        return {"ok": False, "err": str(e)}
    finally:
        if wait:
            time.sleep(wait)


def ev(code, wait=0):
    r = wb("evaluate", {"code": code}, wait=wait)
    if not r.get("ok"):
        return {"ok": False, "err": r.get("err") or r.get("error")}
    return r.get("data", {}).get("value", "")


# 钩住 fetch + XHR，把 URL/请求体/响应文本存到 window.__NET
JS_HOOK = """(() => {
  if (window.__NET_HOOKED) return 'ALREADY';
  window.__NET = [];
  const of = window.fetch;
  window.fetch = function(input, init){
    const url = (typeof input === 'string') ? input : (input && input.url) || '';
    const body = (init && init.body) || '';
    const p = of.apply(this, arguments);
    p.then(res => {
      try {
        res.clone().text().then(t => {
          if (/goods|spu|product|rank|search/i.test(url))
            window.__NET.push({kind:'fetch', url:url, body:String(body).slice(0,600),
                               status:res.status, resp:t.slice(0,4000)});
        }).catch(()=>{});
      } catch(e){}
      return res;
    }).catch(()=>{});
    return p;
  };
  const oo = XMLHttpRequest.prototype.open, os = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(m,u){ this.__u=u; this.__m=m; return oo.apply(this, arguments); };
  XMLHttpRequest.prototype.send = function(b){
    const self=this;
    this.addEventListener('load', function(){
      try{
        if (/goods|spu|product|rank|search/i.test(self.__u||''))
          window.__NET.push({kind:'xhr', url:self.__u, body:String(b||'').slice(0,600),
                             status:self.status, resp:String(self.responseText||'').slice(0,4000)});
      }catch(e){}
    });
    return os.apply(this, arguments);
  };
  window.__NET_HOOKED = 1;
  return 'HOOKED';
})()"""


def click_text(text, exact=False):
    js = """(() => {
      const want=%s, exact=%s;
      const els=[...document.querySelectorAll('button,.el-button,div,span,li,a,label')]
        .filter(e=>{const t=(e.innerText||'').trim();
          return (exact? t===want : t.indexOf(want)>=0) && t.length<%d && e.children.length<=2;});
      if(!els.length) return 'NF';
      const el=els[els.length-1];
      const r=el.getBoundingClientRect();
      if(r.width===0&&r.height===0) return 'HIDDEN';
      const o={bubbles:true,cancelable:true,view:window,clientX:r.left+r.width/2,clientY:r.top+r.height/2};
      ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(k=>
        el.dispatchEvent(new MouseEvent(k,o)));
      return 'CLICK:'+el.innerText.trim().slice(0,20);
    })()""" % (json.dumps(text, ensure_ascii=False), "true" if exact else "false", 26)
    return ev(js)


def set_input(ph, text):
    js = """(() => {
      const el=[...document.querySelectorAll('input')].find(i=>(i.placeholder||'').indexOf(%s)>=0);
      if(!el) return 'NF';
      const setter=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
      setter.call(el, %s);
      el.dispatchEvent(new Event('input',{bubbles:true}));
      el.dispatchEvent(new Event('change',{bubbles:true}));
      return 'SET:'+el.value;
    })()""" % (json.dumps(ph, ensure_ascii=False), json.dumps(text, ensure_ascii=False))
    return ev(js)


def dump_net(tag):
    v = ev("JSON.stringify(window.__NET||[])", wait=1)
    try:
        arr = json.loads(v)
    except Exception:
        print(f"  [{tag}] net dump fail: {str(v)[:200]}", flush=True)
        return []
    print(f"\n===== {tag}：捕获 {len(arr)} 个相关请求 =====", flush=True)
    for i, n in enumerate(arr[-8:], 1):
        print(f"\n  [{i}] {n['kind']} {n['status']} {n['url'][:130]}", flush=True)
        if n.get("body"):
            print(f"      body: {n['body'][:260]}", flush=True)
        print(f"      resp: {n['resp'][:400]}", flush=True)
    return arr


def main():
    wb("navigate", {"url": "https://dy.feigua.cn/app/#/real-time-goods-rank/index"}, wait=11)
    print("URL:", ev("location.href"), flush=True)
    print("hook:", ev(JS_HOOK), flush=True)

    # 触发 1：切类目
    click_text("个护家清")
    time.sleep(6)
    dump_net("切「个护家清」后")

    # 触发 2：搜索
    set_input("请输入商品关键字搜索", "洗面奶")
    time.sleep(1)
    click_text("搜索", exact=True)
    time.sleep(7)
    arr = dump_net("搜索「洗面奶」后")

    # 看看现在页面有内容了没
    print("\nbodyLen:", ev("(document.body.innerText||'').length"), flush=True)
    print("bodyHead:", ev("(document.body.innerText||'').slice(0,900).replace(/\\n/g,' / ')"), flush=True)

    open(os.path.join(TMP, "fg_net_dump.json"), "w", encoding="utf-8").write(
        json.dumps(arr, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
