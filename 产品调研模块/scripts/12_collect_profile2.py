# -*- coding: utf-8 -*-
"""12 · 接口层批量补采（画像 / 评价 / 词云分类 / 评价原文）
★ 关键：这些接口都只认 gid 参数、不需要 ts/sign，所以只开 1 个页面就能刷完 30 个商品。

采集内容：
  - 受众画像 goodsTransactPortray      → 性别/年龄/地域/兴趣/消费层级（主要消费人群）
  - 评价极性 GetGoodsCommentPolarityStat → 好评/中评/差评计数 → 差评率
  - 评价词云 GetGoodsCommentWord       → 全部词 + 15 个分类（功效/成分/气味/包装/规格/目标受众/痛点问题…）
  - 评价原文 getSegmentCommentsV2      → 好评原文 / 差评原文
产出 data/profile.json
"""
import os, sys, json, time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
import pcommon as P

DATA = os.path.join(BASE, "data")
HELPER = open(os.path.join(BASE, "tmp", "_helper.js"), encoding="utf-8").read()
OUT = os.path.join(DATA, "profile.json")
LOG = open(os.path.join(BASE, "tmp", "12_profile.log"), "w", encoding="utf-8")


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
    o.audience = keep;
    o.audience_keys = Object.keys(D);
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

HEAD = r"""
(function(){
  function mk(u, ts){
    var out = 'https://p5-sign.douyinpic.com/' + u.slice(0, 12);
    return u;
  }
  var el = document.querySelector('.xImg.img-product');
  return el ? (el.getAttribute('src')||'').slice(0,40) : 'none';
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
                if len(r) > 50:
                    return {"_raw": r[:3000]}
        time.sleep(1)
    return None


cards = json.load(open(os.path.join(DATA, "cards.json"), encoding="utf-8"))
items = []
for gid, c in cards.items():
    c = dict(c); c["gid"] = gid
    items.append(c)
items.sort(key=lambda x: (x.get("榜_rank") or 999))
ONLY = [x for x in os.environ.get("PROFILE_ONLY_GIDS", "").split(",") if x.strip()]
if ONLY:
    items = [i for i in items if i["gid"] in ONLY]
TOPN = int(os.environ.get("PROFILE_TOPN", "0"))
if TOPN:
    items = items[:TOPN]

D1, D2 = P._dcode(29), P._dcode(0)


def main():
    prof = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    out("login:", P.check_login(), " 商品数 =", len(items), " 周期", D1, "~", D2)
    # 只开一次页面
    P.wb("navigate", {"url": "https://dy.feigua.cn/app/#/product-rank/index?tab=product", "newTab": True}, wait=8)
    time.sleep(7)
    P.ev(HELPER); P.install_hook()
    g0 = items[0]["gid"]
    P.ev("location.hash='#/goods-detail/index?id=&gid=%s&tab=overview&ts=%s&sign=%s'"
         % (g0, items[0].get("ts", ""), items[0].get("sign", "")))
    time.sleep(13); P.ev("window.__killMask()")

    for i, it in enumerate(items):
        gid = it["gid"]
        old = prof.get(gid) or {}
        if old.get("polarity") and old.get("words") and old.get("audience"):
            out("[%d/%d] skip 已有 %s" % (i + 1, len(items), (it.get("title") or "")[:22]))
            continue
        out("\n[%d/%d] %s" % (i + 1, len(items), (it.get("title") or "")[:36]))
        d = dict(old); d["gid"] = gid; d["title"] = it.get("title")
        # 1) 画像 + 极性 + 全部词云
        code = JS.replace("__GID__", json.dumps(gid)).replace("__D1__", json.dumps(D1)).replace("__D2__", json.dumps(D2))
        j = ev_json(code, wait=3, tries=2) or {}
        d["audience"] = j.get("audience") or d.get("audience")
        d["audience_keys"] = j.get("audience_keys")
        d["polarity"] = j.get("polarity") or d.get("polarity")
        d["words"] = j.get("words") or d.get("words")
        # 差评率
        pol = d.get("polarity") or []
        tot = next((x["c"] for x in pol if x.get("p") == "全部"), 0) or sum(x.get("c", 0) for x in pol)
        bad = next((x["c"] for x in pol if x.get("p") == "差"), 0)
        mid = next((x["c"] for x in pol if x.get("p") == "中"), 0)
        d["n_reviews"] = tot
        d["rate_bad"] = round(bad / tot * 100, 2) if tot else None
        d["rate_mid"] = round(mid / tot * 100, 2) if tot else None
        d["rate_good"] = round(100 - (d["rate_bad"] or 0) - (d["rate_mid"] or 0), 2) if tot else None
        out("   画像 %s 组 / 评价 %s 条 / 差评率 %s%% / 词云 %s 词"
            % (len(d.get("audience") or {}), tot, d.get("rate_bad"), len(d.get("words") or [])))
        # 2) 分类词云
        cc = JS_CATS.replace("__GID__", json.dumps(gid)).replace("__D1__", json.dumps(D1)) \
            .replace("__D2__", json.dumps(D2)).replace("__CATS__", json.dumps(CATS, ensure_ascii=False))
        cj = ev_json(cc, wait=6, tries=1) or {}
        d["cats"] = {k: v for k, v in cj.items() if isinstance(v, list)}
        out("   分类词云 %s 类（%s）" % (len(d["cats"]),
                                    "/".join("%s:%d" % (k, len(v)) for k, v in list(d["cats"].items())[:6])))
        # 3) 评价原文：取 TOP 词 + 差评分类词
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
        mj = ev_json(cj2, wait=5, tries=1) or {}
        d["comments"] = mj
        out("   评价原文 %s 组关键字" % len([k for k, v in mj.items() if v]))

        prof[gid] = d
        json.dump(prof, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    P.wb("close_tab", {}, timeout=20)
    out("\n已写 data/profile.json（%d 个）" % len(prof))
    for g, d in prof.items():
        out("  %s 差评率%s%% 画像%s 词云%s 分类%s" % (g[:12], d.get("rate_bad"),
                                                len(d.get("audience") or {}), len(d.get("words") or []),
                                                len(d.get("cats") or {})))


if __name__ == "__main__":
    main()
