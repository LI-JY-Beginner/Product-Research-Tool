# -*- coding: utf-8 -*-
"""
c30_repatch2.py — 补「内容偏好 Hobbys / 消费层级 Consumer」等画像维度（第二批）

★ 为什么另起一个脚本：c27 无论怎么改都全批失败，而 c28（诊断脚本）用同样接口 100% 成功。
  差异只在**调用序列**，所以这里逐字照搬 c28 的序列：
    navigate(newTab,wait=9) → sleep 8 → ev(location.href) → ev(helper) → ev(killMask)
    → body_text() → ev(JS)
  另外 JS 里对非数组维度加 Array.isArray 守卫，避免 .slice 抛异常。

用法: python c30_repatch2.py [前N个]
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import c23_feigua_profile as P

RAW = P.RAW
KEEP = ["Gender", "Age", "GenderAge", "Province", "City", "CityLevel",
        "Hobbys", "AwemeHobbys", "Consumer", "ActHours", "CategoryPreference"]

JS = """
(async function(){
  var gid = __G__;
  try{
    var r = await fetch('/api/v3/goods/portrait/goodsTransactPortray?gid=' + gid, {method:'GET'});
    var pt = await r.json();
    if(!pt || !pt.Data) return JSON.stringify({gid: gid, audience: null, why: pt? ('Code='+String(pt.Code)+' Data='+String(pt.Data).slice(0,60)) : 'pt=null'});
    var D = pt.Data, keep = {};
    __K__.forEach(function(k){
      if(Array.isArray(D[k]) && D[k].length) keep[k] = D[k].slice(0,12).map(function(x){
        return {n:x.Name, r:x.RatioStr, tgi:x.TGI, s:x.Samples};
      });
    });
    return JSON.stringify({gid: gid, audience: keep, audience_keys: Object.keys(D)});
  }catch(e){ return JSON.stringify({gid: gid, audience: null, why: 'throw:'+String(e).slice(0,120)}); }
})()"""


def main():
    lim = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 0
    OUTP = os.path.join(RAW, "feigua_profile_洁面_%s.json" % P.TODAY.replace("-", ""))
    prof = json.load(open(OUTP, encoding="utf-8"))
    gfp = os.path.join(RAW, "feigua_gid_洁面_%s.json" % P.TODAY.replace("-", ""))
    ts_map, sg_map = {}, {}
    if os.path.exists(gfp):
        for g in json.load(open(gfp, encoding="utf-8"))["goods"]:
            ts_map[g["gid"]] = g.get("ts") or ""
            sg_map[g["gid"]] = g.get("sign") or ""

    todo = [g for g, d in prof.items() if not d.get("noData")]
    if lim:
        todo = todo[:lim]
    print(f"待补 {len(todo)} 个", flush=True)
    ok = 0
    for i, gid in enumerate(todo, 1):
        d = prof[gid]
        url = "https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=%s&tab=overview" % gid
        if ts_map.get(gid) and sg_map.get(gid):
            url += "&ts=%s&sign=%s" % (ts_map[gid], sg_map[gid])
        P.wb("navigate", {"url": url, "newTab": True}, wait=9)
        time.sleep(8)
        P.ev("location.href")
        P.ev(P.helper_js())
        P.ev("window.__killMask()")
        P.body_text()
        v = P.ev(JS.replace("__G__", json.dumps(gid)).replace("__K__", json.dumps(KEEP)))
        j = {}
        if isinstance(v, dict):
            j = v
        elif isinstance(v, str):
            try:
                j = json.loads(v)
            except Exception:
                j = {}
        P.wb("close_tab", {}, timeout=25)
        au = j.get("audience")
        if not au:
            print(f"[{i}/{len(todo)}] ✗ {(d.get('brand') or '')[:8]} {str(j.get('why'))[:70]}", flush=True)
            continue
        old = dict(d.get("audience") or {})
        old.update(au)
        d["audience"] = old
        d["audience_keys"] = j.get("audience_keys") or d.get("audience_keys")
        print(f"[{i}/{len(todo)}] ✓ {(d.get('brand') or '')[:10]:<10} 维度{len(au)} "
              f"Hobbys{len(au.get('Hobbys') or [])} Consumer{len(au.get('Consumer') or [])} "
              f"Province{len(au.get('Province') or [])}", flush=True)
        ok += 1
        prof[gid] = d
        json.dump(prof, open(OUTP, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(prof, open(OUTP, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nDONE 补画像 {ok}/{len(todo)}", flush=True)


if __name__ == "__main__":
    main()
