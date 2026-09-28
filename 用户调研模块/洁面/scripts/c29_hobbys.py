# -*- coding: utf-8 -*-
"""c29_hobbys.py — 抽样看 3 个商品的 portrait 各维度「是不是数组 + 有没有内容」
用来确认：① c27 是不是被非数组维度搞崩的；② Hobbys（内容偏好）到底有没有数据"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import c23_feigua_profile as P

RAW = P.RAW
gd = json.load(open(os.path.join(RAW, "feigua_gid_洁面_%s.json" % P.TODAY.replace("-", "")), encoding="utf-8"))

JS = """
(async function(){
  var gid = __G__;
  var r = await fetch('/api/v3/goods/portrait/goodsTransactPortray?gid=' + gid, {method:'GET'});
  var j = await r.json(); var D = j.Data || {};
  var out = {};
  Object.keys(D).forEach(function(k){
    var v = D[k];
    out[k] = Array.isArray(v) ? ('array:' + v.length) : (typeof v);
  });
  var hb = Array.isArray(D.Hobbys) ? D.Hobbys.slice(0,6).map(function(x){return x.Name + ' ' + x.RatioStr;}) : null;
  return JSON.stringify({types: out, hobbys: hb});
})()"""

for it in gd["goods"][:3]:
    gid, ts, sg = it["gid"], it.get("ts", ""), it.get("sign", "")
    url = "https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=%s&tab=overview" % gid
    if ts and sg:
        url += "&ts=%s&sign=%s" % (ts, sg)
    P.wb("navigate", {"url": url, "newTab": True}, wait=9)
    time.sleep(8)
    P.ev(P.helper_js()); P.ev("window.__killMask()")
    v = P.ev(JS.replace("__G__", json.dumps(gid)))
    try:
        v = json.loads(v) if isinstance(v, str) else v
    except Exception:
        pass
    print("\n===== %s | %s" % ((it.get('brand') or '')[:12], (it.get('title') or '')[:30]), flush=True)
    if isinstance(v, dict):
        t = v.get("types") or {}
        bad = {k: x for k, x in t.items() if x != "object" and not str(x).startswith("array")}
        zero = [k for k, x in t.items() if str(x) == "array:0"]
        print("  非数组维度:", bad, flush=True)
        print("  空数组维度:", zero, flush=True)
        print("  Hobbys:", v.get("hobbys"), flush=True)
    else:
        print("  raw:", str(v)[:200], flush=True)
    P.wb("close_tab", {}, timeout=25)
