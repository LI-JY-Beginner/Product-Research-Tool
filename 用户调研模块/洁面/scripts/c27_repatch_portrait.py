# -*- coding: utf-8 -*-
"""
c27_repatch_portrait.py — 只补「受众画像」里没保留的维度（Hobbys 内容偏好 / Consumer 消费层级 等）

背景：c23 的 JS 只 keep 了 Gender/Age/Region/Province/City/Interest/...，
      飞瓜实际字段名是 Hobbys（不是 Interest），导致「内容偏好」全空。
      这里只重放 portrait 接口（不跑评价/词云/原文），一份约 12s，26 份 ≈ 6 分钟。

用法: python c27_repatch_portrait.py
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import c23_feigua_profile as P

KEEP = ["Gender", "Age", "GenderAge", "Province", "City", "CityLevel",
        "Hobbys", "AwemeHobbys", "GenderHobbys", "Consumer", "ActHours",
        "CategoryPreference", "BrandPreference", "CatePrice", "Liveness"]

JS = r"""
(async function(){
  var gid = __GID__;
  async function G(u){ try{ var r = await fetch(u, {method:'GET'}); return await r.json(); }catch(e){ return null; } }
  var pt = await G('/api/v3/goods/portrait/goodsTransactPortray?gid=' + gid);
  if (!pt || !pt.Data) return JSON.stringify({gid: gid, audience: null});
  var D = pt.Data, keep = {};
  __KEEP__.forEach(function(k){
    if (D[k]) keep[k] = (D[k]||[]).slice(0,12).map(function(x){
      return {n:x.Name, r:x.RatioStr, tgi:x.TGI, s:x.Samples};
    });
  });
  return JSON.stringify({gid: gid, audience: keep, audience_keys: Object.keys(D)});
})()
"""


def main():
    lim = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 0
    OUTP = os.path.join(P.RAW, "feigua_profile_洁面_%s.json" % P.TODAY.replace("-", ""))
    prof = json.load(open(OUTP, encoding="utf-8"))
    todo = [g for g, d in prof.items() if not d.get("noData")]

    # ★ 必须带该 gid 自己的 ts/sign（c23 带 → 29/30 成功；c27 首版没带 → 28/29 失败）
    gfp = os.path.join(P.RAW, "feigua_gid_洁面_%s.json" % P.TODAY.replace("-", ""))
    ts_map, sg_map = {}, {}
    if os.path.exists(gfp):
        for g in json.load(open(gfp, encoding="utf-8"))["goods"]:
            ts_map[g["gid"]] = g.get("ts") or ""
            sg_map[g["gid"]] = g.get("sign") or ""

    if lim:
        todo = todo[:lim]
    print(f"待补画像 {len(todo)} 个（带 ts/sign 的 {sum(1 for g in todo if ts_map.get(g))} 个）", flush=True)
    ok = 0
    for i, gid in enumerate(todo, 1):
        d = prof[gid]
        url = "https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=%s&tab=overview" % gid
        if ts_map.get(gid) and sg_map.get(gid):
            url += "&ts=%s&sign=%s" % (ts_map[gid], sg_map[gid])
        P.wb("navigate", {"url": url, "newTab": True}, wait=9)
        time.sleep(9)
        P.ev(P.helper_js())
        P.ev("window.__killMask()")
        code = JS.replace("__GID__", json.dumps(gid)).replace("__KEEP__", json.dumps(KEEP))
        # ★ 用 c28 实测可用的直连写法（P.ev_json 的 wait/tries 组合在这批接口上会拿到 None）
        j = {}
        for _t in range(3):
            v = P.ev(code)
            if isinstance(v, dict):
                j = v
                break
            if isinstance(v, str):
                try:
                    j = json.loads(v)
                    break
                except Exception:
                    pass
            time.sleep(5)
            P.ev("window.__killMask()")
        P.wb("close_tab", {}, timeout=25)
        au = j.get("audience")
        if not au:
            print(f"[{i}/{len(todo)}] ✗ {gid[:12]}", flush=True)
            continue
        old = d.get("audience") or {}
        merged = dict(old)
        merged.update(au)
        d["audience"] = merged
        d["audience_keys"] = j.get("audience_keys") or d.get("audience_keys")
        hn = len(au.get("Hobbys") or [])
        print(f"[{i}/{len(todo)}] ✓ {(d.get('brand') or '')[:10]:<10} 维度{len(au)} Hobbys{hn} "
              f"Province{len(au.get('Province') or [])} Consumer{len(au.get('Consumer') or [])}", flush=True)
        ok += 1
        prof[gid] = d
        json.dump(prof, open(OUTP, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(prof, open(OUTP, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nDONE 补画像 {ok}/{len(todo)}", flush=True)


if __name__ == "__main__":
    main()
