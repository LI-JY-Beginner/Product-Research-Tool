# -*- coding: utf-8 -*-
"""
c23_feigua_profile.py — 洁面/洗面奶：飞瓜「受众画像 + 商品评价」补采

★ 完全照搬产品调研模块 12c 的已验证路线（那里跑通过几百个 gid）：
  1) 一商品一独立标签页（navigate newTab → 取完 close_tab）
     —— 同标签页连刷会「前 5-9 个正常、之后全部返 null（HTTP 200）」，必踩
  2) 不点 tab 硬解 DOM，而是**在页面内直接 fetch 重放接口**（同源带 cookie）：
       /api/v3/goods/portrait/goodsTransactPortray   → 性别/年龄/地域/兴趣/消费层级
       /api/v3/goods/GetGoodsCommentPolarityStat     → 好评/中评/差评计数 → 差评率
       /api/v3/goods/GetGoodsCommentWord             → 评价词云
     这几个接口**明文返回、不需 ts/sign，只认 gid**
  3) fallback：若评价接口返空，先点开「商品评价」tab 再重放（12d 的经验）

用法:
  python c23_feigua_profile.py            # 采 TOPN（默认 12）个
  python c23_feigua_profile.py 20         # 采前 20 个
  python c23_feigua_profile.py --retry    # 只补上次返空的
"""
import json, os, re, subprocess, sys, time
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.dirname(os.path.dirname(BASE))
TMP = os.path.join(WORKSPACE, "tmp")
os.makedirs(TMP, exist_ok=True)
RAW = os.path.join(BASE, "raw")
os.makedirs(RAW, exist_ok=True)
WB = "http://127.0.0.1:10086/command"
SESSION = "fg-cleanser-profile"
REQ = os.path.join(TMP, "req_c23.json")
HELPER = os.path.join(BASE, "tmp", "_helper.js")
TODAY = datetime.now().strftime("%Y-%m-%d")
TOPN = 12

# 评价分类（与商品评价页的 15 个词云分类一致）
CATS = ["功效", "成分", "气味", "质地", "肤质", "包装", "规格", "目标受众", "痛点问题",
        "使用场景", "外观", "技术工艺", "美妆概念", "产品需求", "感受体验", "宣传价格"]


def _dcode(offset_days):
    return (datetime.now() - timedelta(days=offset_days)).strftime("%Y%m%d")


def wb(action, args=None, wait=0, timeout=180):
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


def ev_json(code, wait=0, tries=2):
    for _ in range(tries):
        r = ev(code, wait=wait)
        if isinstance(r, dict):
            return r
        if isinstance(r, str):
            try:
                return json.loads(r)
            except Exception:
                pass
        time.sleep(1.2)
    return None


def body_text():
    t = ev("document.body.innerText")
    return t if isinstance(t, str) else ""


def helper_js():
    with open(HELPER, encoding="utf-8") as f:
        return f.read()


# ---------- 详情页「概览」解析（来源更可靠：品牌/销售额/销量/带货视频/直播/达人 都在这里）----------
# 商品榜列表是懒渲染 + 有遮罩，innerText 行解析经常错位；详情页概览是稳定渲染的，
# 所以 TOP10 的指标改用详情页概览，商品榜只用来出「商品池」。
OV_LABELS = ["销售额", "销量", "订单量", "浏览量", "转化率", "带货视频", "带货直播", "带货达人"]


def _seg(txt, a, b):
    i, j = txt.find(a), txt.find(b)
    if i < 0:
        return ""
    return txt[i:j] if j > i else txt[i:]


def parse_overview(txt):
    d = {}
    m = re.search(r"飞瓜抖音\n([^\n]+)\n复制标题", txt)
    if m:
        d["title"] = m.group(1).strip()
    s = _seg(txt, "更新时间", "分析同类商品热度")
    for key, pat in (("brand", r"\n品牌\n([^\n]+)"),
                     ("shop", r"\n小店\n([^\n]+)"),
                     ("cate", r"\n分类\n([^\n]+)")):
        m = re.search(pat, s)
        if m:
            d[key] = m.group(1).strip()
    m = re.search(r"近30天销量：([^\n]+)", s)
    if m:
        d["volume30d"] = m.group(1).strip()
    m = re.search(r"佣金率：([\d.]+)%[（(]\s*￥([\d.]+)\s*[）)]", s)
    if m:
        d["commission"] = m.group(1) + "%"
    m = re.search(r"上架时间：([\d/]+)", s)
    if m:
        d["onsaleDate"] = m.group(1).strip()
    m = re.search(r"共([\d.]+[w万]?)条评价好评([\d.]+)%", s)
    if m:
        d["reviewCount"], d["praiseRate"] = m.group(1), m.group(2) + "%"
    s2 = _seg(txt, "商品数据", "销售渠道")
    lines = [x.strip() for x in s2.split("\n") if x.strip()]
    for i, l in enumerate(lines):
        if l in OV_LABELS and i + 1 < len(lines) and lines[i + 1] not in OV_LABELS:
            d.setdefault(l, lines[i + 1])
    return d


# ---------- 页面内重放接口 ----------
JS_MAIN = r"""
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
  return 'ok';
})()"""


def load_gids():
    """读 c22 产出的 gid 清单；按「主关键词优先 + 原榜单顺序」排序"""
    fp = os.path.join(RAW, "feigua_gid_洁面_%s.json" % TODAY.replace("-", ""))
    if not os.path.exists(fp):
        print("找不到", fp, "→ 先跑 c22_feigua_gid.py collect")
        sys.exit(1)
    d = json.load(open(fp, encoding="utf-8"))
    gs = [g for g in d["goods"] if not g.get("isNoise")]
    # 榜单顺序：先按 keyword 在 KEYWORDS 里的次序，再按原顺序
    order = {"洗面奶": 0, "洁面": 1, "氨基酸洗面奶": 2}
    gs.sort(key=lambda g: (order.get(g.get("keyword"), 9), g.get("keyword", "")))
    return gs


def main():
    args = sys.argv[1:]
    retry_only = "--retry" in args
    n = TOPN
    for a in args:
        if a.isdigit():
            n = int(a)

    gs = load_gids()[:n]
    D1, D2 = _dcode(29), _dcode(0)
    OUTP = os.path.join(RAW, "feigua_profile_洁面_%s.json" % TODAY.replace("-", ""))
    prof = json.load(open(OUTP, encoding="utf-8")) if os.path.exists(OUTP) else {}
    if retry_only:
        gs = [g for g in gs if not (prof.get(g["gid"]) or {}).get("polarity")]
    print(f"待采 {len(gs)} 个（周期 {D1}~{D2}）", flush=True)

    for i, it in enumerate(gs, 1):
        gid = it["gid"]
        title = (it.get("title") or "")[:34]
        url = ("https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=%s&tab=overview" % gid)
        if it.get("ts") and it.get("sign"):
            url += "&ts=%s&sign=%s" % (it["ts"], it["sign"])
        wb("navigate", {"url": url, "newTab": True}, wait=9)
        time.sleep(9)
        ev(helper_js())
        ev("window.__killMask()")

        # —— 概览：等渲染（品牌 / 销售额 / 销量 / 带货视频 / 直播 / 达人）——
        ov_ok = False
        for _ in range(10):
            t = body_text()
            if "上架时间" in t or "近30天销量" in t:
                ov_ok = True
                break
            time.sleep(2.5)
            ev("window.__killMask()")
        ov = parse_overview(body_text()) if ov_ok else {}

        code = (JS_MAIN.replace("__GID__", json.dumps(gid))
                       .replace("__D1__", json.dumps(D1)).replace("__D2__", json.dumps(D2)))
        j = ev_json(code, wait=4, tries=2) or {}

        # fallback：评价为空 → 先点开「商品评价」tab 再重放
        if not j.get("polarity"):
            ev("window.__killMask()")
            ev(CLICK_TAB % json.dumps("商品评价", ensure_ascii=False))
            time.sleep(7)
            ev("window.__killMask()")
            j2 = ev_json(code, wait=4, tries=2) or {}
            if j2.get("polarity"):
                j = j2
                print("   （点开「商品评价」tab 后拿到）", flush=True)

        if not j.get("polarity") and not j.get("audience") and not ov:
            print(f"[{i}/{len(gs)}] ✗ 无数据 {title}", flush=True)
            wb("close_tab", {}, timeout=25)
            d = dict(prof.get(gid) or {})
            d.update({"gid": gid, "title": it.get("title"), "brand": it.get("brand"),
                      "keyword": it.get("keyword"), "noData": True, "fetchDate": TODAY})
            prof[gid] = d
            json.dump(prof, open(OUTP, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            continue

        d = dict(prof.get(gid) or {})
        br = ov.get("brand") or it.get("brand") or "—"
        d.update({
            "gid": gid, "title": ov.get("title") or it.get("title"), "brand": br,
            "keyword": it.get("keyword"), "fetchDate": TODAY, "noData": False,
            "ov": {"销售额": ov.get("销售额", ""), "销量": ov.get("销量", ""),
                   "带货视频": ov.get("带货视频", ""), "带货直播": ov.get("带货直播", ""),
                   "带货达人": ov.get("带货达人", ""), "volume30d": ov.get("volume30d", ""),
                   "praiseRate": ov.get("praiseRate", ""), "reviewCount": ov.get("reviewCount", ""),
                   "onsaleDate": ov.get("onsaleDate", ""), "shop": ov.get("shop", ""),
                   "cate": ov.get("cate", ""), "commission": ov.get("commission", "")},
            "audience": j.get("audience"), "audience_keys": j.get("audience_keys"),
            "polarity": j.get("polarity"), "words": j.get("words"),
        })
        pol = d.get("polarity") or []
        tot = next((x["c"] for x in pol if x.get("p") == "全部"), 0) or sum(x.get("c", 0) for x in pol)
        bad = next((x["c"] for x in pol if x.get("p") == "差"), 0)
        mid = next((x["c"] for x in pol if x.get("p") == "中"), 0)
        d["n_reviews"] = tot
        d["rate_bad"] = round(bad / tot * 100, 2) if tot else None
        d["rate_mid"] = round(mid / tot * 100, 2) if tot else None
        d["rate_good"] = round(100 - (d["rate_bad"] or 0) - (d["rate_mid"] or 0), 2) if tot else None

        cc = (JS_CATS.replace("__GID__", json.dumps(gid))
                     .replace("__D1__", json.dumps(D1)).replace("__D2__", json.dumps(D2))
                     .replace("__CATS__", json.dumps(CATS, ensure_ascii=False)))
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

        wb("close_tab", {}, timeout=25)
        print(f"[{i}/{len(gs)}] ✓ {d['brand']:<8} {(d['title'] or '')[:22]:<22} "
              f"额{d['ov']['销售额'] or '-':<9} 销{d['ov']['销量'] or '-':<8} "
              f"视{d['ov']['带货视频'] or '-':<7} 播{d['ov']['带货直播'] or '-':<5} 达{d['ov']['带货达人'] or '-':<5} "
              f"| 评{tot} 差{d.get('rate_bad')}% 画像{len(d.get('audience') or {})} "
              f"词云{len(d.get('words') or [])} 分类{len(d['cats'])}", flush=True)
        prof[gid] = d
        json.dump(prof, open(OUTP, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    json.dump(prof, open(OUTP, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ok = sum(1 for v in prof.values() if v.get("rate_bad") is not None)
    print(f"\nDONE {OUTP} = {len(prof)} 个，其中差评率 {ok} 个", flush=True)


if __name__ == "__main__":
    main()
