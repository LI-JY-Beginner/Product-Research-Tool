# -*- coding: utf-8 -*-
"""12c · 画像/评价/词云 补采（★ 一商品一独立标签页，规避同页批量跑后接口返空）
产出于 data/profile.json（与 12 同格式，增量合并）
"""
import os, sys, json, time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
import pcommon as P

DATA = os.path.join(BASE, "data")
HELPER = open(os.path.join(BASE, "tmp", "_helper.js"), encoding="utf-8").read()
OUT = P.dpath("profile.json")
LOG = open(os.path.join(BASE, "tmp", "12c_profile_%s.log" % (P.CATE_NS or "eye")), "w", encoding="utf-8")


def out(*a):
    s = " ".join(str(x) for x in a)
    LOG.write(s + "\n"); LOG.flush(); print(s, flush=True)


CATS = ["功效", "成分", "气味", "质地", "肤质", "包装", "规格", "目标受众", "痛点问题",
        "使用场景", "外观", "技术工艺", "美妆概念", "产品需求", "感受体验", "宣传价格"]

JS = r"""
(async function(){
  var gid = __GID__, d1 = __D1__, d2 = __D2__;
  var B = '/api/v3/goods/';
  var q = '&fromDateCode=' + d1 + '&toDateCode=' + d2 + '&PeriodType=10000';
  async function G(u){ try{ var r = await fetch(u, {method:'GET'}); return await r.json(); }catch(e){ return null; } }
  var o = {gid: gid};
  var pt = await G(B + 'portrait/goodsTransactPortray?gid=' + gid);
  if (pt && pt.Data){
    var D = pt.Data, keep = {};
    ['Gender','Age','Region','Province','City','Interest','ConsumeLevel','PriceLevel','FansLevel','Device']
      .forEach(function(k){
        if (D[k]) keep[k] = (D[k]||[]).slice(0,12).map(function(x){
          return {n:x.Name, r:x.RatioStr, tgi:x.TGI, s:x.Samples};
        });
      });
    o.audience = keep; o.audience_keys = Object.keys(D);
  } else { o.audience = null; }
  var pol = await G(B + 'GetGoodsCommentPolarityStat?gid=' + gid + q + '&wordType=&wordLevel=2&wordHitMode=1');
  o.polarity = (pol && pol.Data) ? pol.Data.map(function(x){return {p:x.Polarity, v:x.Value, c:x.Count, cs:x.CountStr};}) : null;
  var w = await G(B + 'GetGoodsCommentWord?gid=' + gid + q + '&wordType=&WordLevel=2&WordHitMode=1');
  o.words = (w && w.Data) ? w.Data.slice(0, 60).map(function(x){return {k:x.Keyword, c:x.CommentCount, r:x.RatioStr};}) : null;
  return JSON.stringify(o);
})()
"""

JS_CATS = r"""
(async function(){
  var gid = __GID__, d1 = __D1__, d2 = __D2__;
  var B = '/api/v3/goods/';
  var q = '&fromDateCode=' + d1 + '&toDateCode=' + d2 + '&PeriodType=10000';
  var cats = __CATS__;
  async function G(u){ try{ var r = await fetch(u, {method:'GET'}); return await r.json(); }catch(e){ return null; } }
  var o = {};
  for (var i = 0; i < cats.length; i++){
    var w = await G(B + 'GetGoodsCommentWord?gid=' + gid + q + '&wordType=' + encodeURIComponent(cats[i]) + '&WordLevel=2&WordHitMode=1');
    o[cats[i]] = (w && w.Data) ? w.Data.slice(0, 20).map(function(x){return {k:x.Keyword, c:x.CommentCount, r:x.RatioStr};}) : [];
  }
  return JSON.stringify(o);
})()
"""

JS_CMT = r"""
(async function(){
  var gid = __GID__, kws = __KWS__;
  var o = {};
  for (var i = 0; i < kws.length; i++){
    try{
      var r = await fetch('/api/v1/goods/getSegmentCommentsV2?gid=' + gid + '&keyword=' + encodeURIComponent(kws[i]), {method:'GET'});
      var j = await r.json();
      o[kws[i]] = (j && j.Data) ? j.Data.slice(0, 8).map(function(x){return {t:(x.Content||'').slice(0,140), d:x.CommentTime};}) : [];
    }catch(e){ o[kws[i]] = []; }
  }
  return JSON.stringify(o);
})()
"""


def ev_json(code, wait=0, tries=2):
    for _ in range(tries):
        r = P.ev(code, wait=wait)
        if isinstance(r, dict):
            return r
        if isinstance(r, str):
            try:
                return json.loads(r)
            except Exception:
                pass
        time.sleep(1)
    return None


def main():
    cards = json.load(open(P.dpath("cards.json"), encoding="utf-8"))
    items = []
    for gid, c in cards.items():
        c = dict(c); c["gid"] = gid; items.append(c)
    items.sort(key=lambda x: (x.get("榜_rank") or 999))
    ONLY = [x for x in os.environ.get("PROFILE_ONLY_GIDS", "").split(",") if x.strip()]
    if ONLY:
        items = [i for i in items if i["gid"] in ONLY]
    D1, D2 = P._dcode(29), P._dcode(0)

    prof = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    todo = [i for i in items if not ((prof.get(i["gid"]) or {}).get("polarity")
                                     and (prof.get(i["gid"]) or {}).get("words")
                                     and (prof.get(i["gid"]) or {}).get("audience"))]
    out("login:", P.check_login(), " 待补 =", len(todo), "/", len(items), " 周期", D1, "~", D2)
    for i, it in enumerate(todo):
        gid = it["gid"]
        title = (it.get("title") or "")[:30]
        url = ("https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=%s&tab=overview&ts=%s&sign=%s"
               % (gid, it.get("ts"), it.get("sign")))
        P.wb("navigate", {"url": url, "newTab": True}, wait=9)
        time.sleep(9)
        P.ev(HELPER)
        code = JS.replace("__GID__", json.dumps(gid)).replace("__D1__", json.dumps(D1)).replace("__D2__", json.dumps(D2))
        j = ev_json(code, wait=4, tries=2) or {}
        P.wb("close_tab", {}, timeout=20)
        if not j.get("polarity"):
            out("[%d/%d] 无数据（飞瓜未返回） %s" % (i + 1, len(todo), title))
            d = dict(prof.get(gid) or {}); d["gid"] = gid; d["title"] = it.get("title")
            d["rate_bad"] = None; d["noRev"] = True
            prof[gid] = d
            json.dump(prof, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            continue

        d = dict(prof.get(gid) or {})
        d["gid"] = gid; d["title"] = it.get("title")
        d["audience"] = j.get("audience"); d["audience_keys"] = j.get("audience_keys")
        d["polarity"] = j.get("polarity"); d["words"] = j.get("words")
        pol = d.get("polarity") or []
        tot = next((x["c"] for x in pol if x.get("p") == "全部"), 0) or sum(x.get("c", 0) for x in pol)
        bad = next((x["c"] for x in pol if x.get("p") == "差"), 0)
        mid = next((x["c"] for x in pol if x.get("p") == "中"), 0)
        d["n_reviews"] = tot
        d["rate_bad"] = round(bad / tot * 100, 2) if tot else None
        d["rate_mid"] = round(mid / tot * 100, 2) if tot else None
        d["rate_good"] = round(100 - (d["rate_bad"] or 0) - (d["rate_mid"] or 0), 2) if tot else None
        cc = JS_CATS.replace("__GID__", json.dumps(gid)).replace("__D1__", json.dumps(D1)) \
            .replace("__D2__", json.dumps(D2)).replace("__CATS__", json.dumps(CATS, ensure_ascii=False))
        cj = ev_json(cc, wait=6, tries=1) or {}
        d["cats"] = {k: v for k, v in cj.items() if isinstance(v, list)}
        kws = []
        for x in (d.get("words") or [])[:3]:
            if x.get("k"):
                kws.append(x["k"])
        for k in ("痛点问题", "感受体验", "质地", "气味"):
            for x in (d["cats"].get(k) or [])[:2]:
                if x.get("k") and x["k"] not in kws:
                    kws.append(x["k"])
        kws = kws[:8]
        cj2 = JS_CMT.replace("__GID__", json.dumps(gid)).replace("__KWS__", json.dumps(kws, ensure_ascii=False))
        d["comments"] = ev_json(cj2, wait=5, tries=1) or {}
        out("[%d/%d] %s | 评价%s 差评率%s%% 画像%s 词云%s 分类%s 原文%s"
            % (i + 1, len(todo), title, tot, d.get("rate_bad"), len(d.get("audience") or {}),
               len(d.get("words") or []), len(d["cats"]), len([k for k, v in (d.get("comments") or {}).items() if v])))
        prof[gid] = d
        json.dump(prof, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    json.dump(prof, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ok = sum(1 for v in prof.values() if v.get("rate_bad") is not None)
    out("\nDONE profile.json = %d 个，其中差评率 %d 个" % (len(prof), ok))


if __name__ == "__main__":
    main()
