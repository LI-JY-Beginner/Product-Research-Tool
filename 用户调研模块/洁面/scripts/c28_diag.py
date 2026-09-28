# -*- coding: utf-8 -*-
"""c28_diag.py — 单条诊断：为什么 c27 重放 portrait 接口拿不到数据"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import c23_feigua_profile as P

RAW = P.RAW
gd = json.load(open(os.path.join(RAW, "feigua_gid_洁面_%s.json" % P.TODAY.replace("-", "")), encoding="utf-8"))
gid_wanted = sys.argv[1] if len(sys.argv) > 1 else None
it = next((x for x in gd["goods"] if x["gid"] == gid_wanted), gd["goods"][0])
gid, ts, sg = it["gid"], it.get("ts", ""), it.get("sign", "")
print("gid:", gid, "ts:", ts, "sign:", (sg or "")[:12], flush=True)

url = "https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=%s&tab=overview" % gid
if ts and sg:
    url += "&ts=%s&sign=%s" % (ts, sg)
r = P.wb("navigate", {"url": url, "newTab": True}, wait=9)
print("navigate:", json.dumps(r)[:300], flush=True)
time.sleep(9)
print("href:", P.ev("location.href"), flush=True)
P.ev(P.helper_js())
print("killMask:", P.ev("window.__killMask()"), flush=True)
bt = P.body_text()
print("body len:", len(bt or ""), flush=True)
print("body head:", (bt or "")[:200].replace("\n", " | "), flush=True)

# 1) 直接同步 fetch 看 Code/DataType
JS1 = """
(async function(){
  try{
    var r = await fetch('/api/v3/goods/portrait/goodsTransactPortray?gid=' + __G__, {method:'GET'});
    var j = await r.json();
    var D = j.Data;
    return JSON.stringify({status:r.status, Code:j.Code, Msg:(j.Msg||'').slice(0,80),
      DataType:Object.prototype.toString.call(D), len:(typeof D==='string'?D.length:(D?Object.keys(D).length:0)),
      keys:(D&&typeof D==='object')?Object.keys(D).slice(0,10):null});
  }catch(e){ return JSON.stringify({err:String(e)}); }
})()""".replace("__G__", json.dumps(gid))
print("\n--- 直连 portrait ---", flush=True)
print("raw:", P.ev(JS1), flush=True)

# 2) 用 c27 一模一样的写法
KEEP = ["Gender", "Age", "Province", "City", "Hobbys", "Consumer"]
JS2 = """
(async function(){
  var gid = __G__;
  async function G(u){ try{ var r = await fetch(u, {method:'GET'}); return await r.json(); }catch(e){ return null; } }
  var pt = await G('/api/v3/goods/portrait/goodsTransactPortray?gid=' + gid);
  if (!pt || !pt.Data) return JSON.stringify({gid: gid, audience: null, why:(pt?('Code='+pt.Code+' Data='+String(pt.Data).slice(0,40)):'pt=null')});
  var D = pt.Data, keep = {};
  __K__.forEach(function(k){ if (D[k]) keep[k] = (D[k]||[]).slice(0,12).map(function(x){return {n:x.Name, r:x.RatioStr};}); });
  return JSON.stringify({gid: gid, audience: keep});
})()""".replace("__G__", json.dumps(gid)).replace("__K__", json.dumps(KEEP))
print("\n--- c27 同款写法 ---", flush=True)
v = P.ev(JS2)
print("raw type:", type(v).__name__, "value:", str(v)[:400], flush=True)
