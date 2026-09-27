# -*- coding: utf-8 -*-
"""12d · 补采「16 类分类词云」+ 评价原文
★ 关键：必须先点开该链接的「商品评价」tab，再调 GetGoodsCommentWord（否则接口返 Code500「接口不存在或不被支持」）
★ 同样一商品一独立标签页
增量合并进 data/profile.json
"""
import os, sys, json, time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
import pcommon as P

DATA = os.path.join(BASE, "data")
HELPER = open(os.path.join(BASE, "tmp", "_helper.js"), encoding="utf-8").read()
OUT = P.dpath("profile.json")
LOG = open(os.path.join(BASE, "tmp", "12d_cats_%s.log" % (P.CATE_NS or "eye")), "w", encoding="utf-8")


def out(*a):
    s = " ".join(str(x) for x in a)
    LOG.write(s + "\n"); LOG.flush(); print(s, flush=True)


CATS = ["功效", "成分", "气味", "质地", "肤质", "包装", "规格", "目标受众", "痛点问题",
        "使用场景", "外观", "技术工艺", "美妆概念", "产品需求", "感受体验", "宣传价格"]

JS_CATS = r"""
(async function(){
  var gid = __GID__, d1 = __D1__, d2 = __D2__;
  var B = '/api/v3/goods/';
  var q = '&fromDateCode=' + d1 + '&toDateCode=' + d2 + '&PeriodType=10000';
  var cats = __CATS__;
  async function G(u){
    for (var t = 0; t < 3; t++){
      try{
        var r = await fetch(u, {method:'GET'}); var j = await r.json();
        if (j && j.Data) return j;
      }catch(e){}
      await new Promise(function(s){setTimeout(s, 700)});
    }
    return null;
  }
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
    for (var t = 0; t < 2; t++){
      try{
        var r = await fetch('/api/v1/goods/getSegmentCommentsV2?gid=' + gid + '&keyword=' + encodeURIComponent(kws[i]), {method:'GET'});
        var j = await r.json();
        if (j && j.Data && j.Data.length){ o[kws[i]] = j.Data.slice(0, 8).map(function(x){return {t:(x.Content||'').slice(0,140), d:x.CommentTime};}); break; }
        o[kws[i]] = [];
      }catch(e){ o[kws[i]] = []; }
      await new Promise(function(s){setTimeout(s, 500)});
    }
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
    D1, D2 = P._dcode(29), P._dcode(0)
    prof = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    need = [i for i in items
            if not any((prof.get(i["gid"]) or {}).get("cats", {}).get(k) for k in CATS)]
    # 可选：只补某些 gid
    ONLY = [x for x in os.environ.get("PROFILE_ONLY_GIDS", "").split(",") if x.strip()]
    if ONLY:
        need = [i for i in need if i["gid"] in ONLY]
    out("login:", P.check_login(), " 需补分类词云 =", len(need), "/", len(items))

    for i, it in enumerate(need):
        gid = it["gid"]
        url = ("https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=%s&tab=overview&ts=%s&sign=%s"
               % (gid, it.get("ts"), it.get("sign")))
        P.wb("navigate", {"url": url, "newTab": True}, wait=9)
        time.sleep(9)
        P.ev(HELPER)
        P.click_tab_full("商品评价")
        time.sleep(7)
        P.ev("window.__killMask && window.__killMask()")
        cc = JS_CATS.replace("__GID__", json.dumps(gid)).replace("__D1__", json.dumps(D1)) \
            .replace("__D2__", json.dumps(D2)).replace("__CATS__", json.dumps(CATS, ensure_ascii=False))
        cj = ev_json(cc, wait=14, tries=2) or {}
        cats = {k: v for k, v in cj.items() if isinstance(v, list)}
        # 评价原文
        d0 = prof.get(gid) or {}
        kws = []
        for x in (d0.get("words") or [])[:3]:
            if x.get("k"):
                kws.append(x["k"])
        for k in ("痛点问题", "感受体验", "质地", "气味"):
            for x in (cats.get(k) or [])[:2]:
                if x.get("k") and x["k"] not in kws:
                    kws.append(x["k"])
        kws = kws[:8]
        cm = ev_json(JS_CMT.replace("__GID__", json.dumps(gid)).replace("__KWS__", json.dumps(kws, ensure_ascii=False)), wait=10, tries=1) or {}
        P.wb("close_tab", {}, timeout=20)

        d = dict(d0); d["gid"] = gid; d["title"] = it.get("title")
        d["cats"] = cats
        if cm:
            d["comments"] = cm
        nz = sum(1 for v in cats.values() if v)
        out("[%d/%d] %s | 分类 %d/16 类有内容 %s | 原文 %d 组"
            % (i + 1, len(need), (it.get("title") or "")[:22], nz,
               "/".join("%s:%d" % (k, len(v)) for k, v in list(cats.items())[:6]),
               len([k for k, v in cm.items() if v])))
        prof[gid] = d
        json.dump(prof, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    json.dump(prof, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ok = sum(1 for v in prof.values() if any((v.get("cats") or {}).get(k) for k in CATS))
    out("\nDONE 有分类词云的 = %d / %d" % (ok, len(prof)))


if __name__ == "__main__":
    main()
