# -*- coding: utf-8 -*-
"""B6 · 深度层：TOP5 商品的 带货视频 / 词云 / 带货达人 / 达人结构 / 直播(DOM兜底) / 规格属性
产出: data/deep.json
"""
import os, sys, json, time, re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
import pcommon as P

DATA = os.path.join(BASE, "data")
HELPER = open(os.path.join(BASE, "tmp", "_helper.js"), encoding="utf-8").read()
OUT = P.dpath("deep.json")

LOG = open(os.path.join(BASE, "tmp", "04_deep_%s.log" % (P.CATE_NS or "eye")), "w", encoding="utf-8")
def out(*a):
    s = " ".join(str(x) for x in a)
    LOG.write(s + "\n"); LOG.flush(); print(s, flush=True)

TOPN = int(os.environ.get("DEEP_TOPN", "5"))
SRC = os.environ.get("DEEP_SRC", "top30")          # top30 | cards(=全部30个，按榜序)
SKIPDONE = os.environ.get("DEEP_SKIP_DONE", "1") == "1"
DOCOVER = os.environ.get("DEEP_COVER", "1") == "1"
ONLYCOVER = os.environ.get("DEEP_ONLY_COVER", "0") == "1"
COVERDIR = os.path.join(BASE, "assets", "covers")
os.makedirs(COVERDIR, exist_ok=True)

# ★ 封面图：飞瓜的图是 data:image/jpeg;base64 内联的，不是 http 链接
IMG_JS = r"""
(function(){
  window.scrollTo(0,420); window.scrollTo(0,0);
  var res=[];
  document.querySelectorAll('img').forEach(function(im){
    var s=im.getAttribute('src')||im.getAttribute('data-src')||'';
    if(s.indexOf('data:image/jpeg')!==0) return;
    var r=im.getBoundingClientRect();
    res.push({cls:im.className||'', w:im.naturalWidth||0, h:im.naturalHeight||0,
              rw:Math.round(r.width), rh:Math.round(r.height), len:s.length, src:s});
  });
  res.sort(function(a,b){return b.w*b.h-a.w*a.h;});
  return JSON.stringify({n:res.length, top:res.slice(0,8)});
})()
"""


def save_cover(gid, res):
    """挑最大的一张 jpeg 存成 assets/covers/<gid>.jpg，返回本地相对路径"""
    import base64
    if isinstance(res, str):
        try:
            res = json.loads(res)
        except Exception:
            return None
    if isinstance(res, list):           # 兼容老写法
        res = {"top": res}
    out("     [img] 命中 %s 张 jpeg" % (res or {}).get("n"))
    for i, x in enumerate((res or {}).get("top") or []):
        out("     [img#%d] %sx%s cls=%r len=%s" % (i, x.get("w"), x.get("h"),
                                                   (x.get("cls") or "")[:40], x.get("len")))
    for x in (res or {}).get("top") or []:
        try:
            if not x.get("src") or (x.get("w") or 0) < 100:
                continue
            b = base64.b64decode(x["src"].split(",", 1)[1])
            if len(b) < 3000:
                continue
            p = os.path.join(COVERDIR, gid + ".jpg")
            open(p, "wb").write(b)
            out("     [img] 已存 %s (%s B, %sx%s)" % (p, len(b), x["w"], x["h"]))
            return {"path": "assets/covers/%s.jpg" % (gid,), "w": x["w"], "h": x["h"],
                    "cls": x.get("cls", ""), "bytes": len(b)}
        except Exception as e:
            out("     [img] decode err", e)
            continue
    return None

REPLAY_GET = r"""
(async function(u){
  var r = await fetch(u + '&_=' + Date.now(), {method:'GET'});
  var j = await r.json();
  var d = j.Data;
  return JSON.stringify({status:r.status, data: d});
})(__U__)
"""


def replay(path):
    code = REPLAY_GET.replace("__U__", json.dumps(path))
    r = P.ev(code, wait=0)
    if isinstance(r, str):
        try:
            return json.loads(r)
        except Exception:
            return {"status": -1, "err": r[:200]}
    return r or {}


def blogger_items(data, n=20):
    items = (data or {}).get("Items") or []
    res = []
    for x in data_items(items):
        b = x.get("Blogger") or {}
        res.append({
            "name": b.get("BloggerName"), "displayId": b.get("DisplayId"),
            "fans": b.get("Fans"), "fansNum": b.get("FansNum"),
            "level": b.get("AuthorLevelStr"), "cert": b.get("AccoutCertText"),
            "tag": b.get("Tag") or b.get("TagName1"), "province": b.get("ProvinceName"),
            "home": b.get("DouyinBloggerUrl"),
            "gmv": x.get("SaleGmvStr"), "volume": x.get("SaleCountStr"),
            "awemeCnt": x.get("AwemeCountStr"), "liveCnt": x.get("LiveCountStr"),
            "liveGmv": x.get("LiveSaleGmvStr"), "awemeGmv": x.get("AwemeSaleGmvStr"),
        })
        if len(res) >= n:
            break
    return res


def data_items(items):
    return items if isinstance(items, list) else []


def one(it, idx):
    gid, ts, sg = it["gid"], it.get("ts", ""), it.get("sign", "")
    d = {"gid": gid, "title": it.get("title")}
    # ★ 先落在商品榜页装 hook，再 SPA 跳详情 —— 这样 hook 能活下来
    P.wb("navigate", {"url": "https://dy.feigua.cn/app/#/product-rank/index?tab=product", "newTab": True}, wait=8)
    time.sleep(7)
    P.ev(HELPER); P.install_hook()
    P.ev("window.__cap=[]")
    P.ev("location.hash='#/goods-detail/index?id=&gid=%s&tab=overview&ts=%s&sign=%s'" % (gid, ts, sg))
    time.sleep(13); P.ev("window.__killMask()")

    cv = None
    if DOCOVER:
        try:
            res = P.ev(IMG_JS, wait=0)
            cv = save_cover(gid, res)
            d["cover"] = cv
            out("   封面 %s" % (cv["path"] if cv else "无"))
        except Exception as e:
            out("   封面异常:", e)

    # ONLY_COVER：只补封面，不点后面的重 tab
    if ONLYCOVER:
        P.wb("close_tab", {}, timeout=20)
        time.sleep(1)
        return d

    # ---------- 0. 规格 / 属性 ----------
    P.ev("window.__clickText('属性')")
    time.sleep(5); P.ev("window.__killMask()")
    t = P.body_text()
    m = re.search(r"属性\n(.{0,600}?)更新时间", t, re.S)
    d["attr_text"] = (m.group(1).strip()[:500] if m else "")

    # ---------- 1. 带货视频（接口重放，取 TOP30 by GMV） ----------
    P.ev("window.__clickText('带货视频')")
    time.sleep(8); P.ev("window.__killMask()")
    v = P.aweme_list(gid, page=1, size=30, sort_field="AwemeSaleGmvStr", order=1)
    d["videos_total"] = v.get("total")
    d["videos"] = v.get("items") or []
    out("   视频 total=%s 取到=%s" % (v.get("total"), len(d["videos"])))
    # 词云：从捕获里直接取（接口明文）
    wc = P.cap_json("GetAwemeMarketingKeyWordList") or {}
    wl = wc.get("Data") if isinstance(wc.get("Data"), list) else (wc.get("Data") or {}).get("Data")
    if not wl:
        j = P.cap("GetAwemeMarketingKeyWordList")
        for c in j:
            try:
                wl = json.loads(c["body"]).get("Data"); break
            except Exception:
                pass
    d["wordcloud"] = [{"kw": x.get("WordKeyword"), "cnt": x.get("AwemeCountStr"),
                       "ratio": x.get("AwemeCountRatioStr"), "type": x.get("WordType")}
                      for x in (wl or [])[:60]]
    out("   词云 %s 条" % len(d["wordcloud"]))
    ov = P.cap_json("loadAwemeAnalysisOverview")
    d["video_overview"] = (ov or {}).get("Data")

    # ---------- 2. 带货达人（接口重放） ----------
    P.ev("window.__cap=[]")
    P.ev("window.__clickText('带货达人')")
    time.sleep(9); P.ev("window.__killMask()")
    base = "/api/v3/goods/blogger/list?gid=%s&fromDateCode=%s&toDateCode=%s&PeriodType=10000&sort=6&order=1&page=1&pageSize=20" % (
        gid, P._dcode(29), P._dcode(0))
    r = replay(base)
    d["bloggers_total"] = (r.get("data") or {}).get("Total")
    d["bloggers"] = blogger_items(r.get("data"), 20)
    out("   达人 total=%s 取到=%s" % (d["bloggers_total"], len(d["bloggers"])))
    r2 = replay("/api/v3/goods/blogger/concentration?gid=%s&fromDateCode=%s&toDateCode=%s&PeriodType=10000" % (
        gid, P._dcode(29), P._dcode(0)))
    dd = r2.get("data") or {}
    d["concentration"] = {
        "top5": [{"uid": x.get("BloggerUid"), "name": x.get("BloggerName"),
                  "gmv": x.get("SaleGmvStr"), "rate": x.get("SaleGmvRateStr")}
                 for x in (dd.get("Top5Bloggers") or [])[:5]],
        "rate": dd.get("Top5GmvRateStr") or dd.get("ConcentrationRateStr"),
    }
    r3 = replay("/api/v3/goods/blogger/blogger/type/analysis?gid=%s&fromDateCode=%s&toDateCode=%s&PeriodType=10000" % (
        gid, P._dcode(29), P._dcode(0)))
    d["blogger_types"] = [{"type": x.get("BloggerTypeName"), "cnt": x.get("BloggerCountStr"),
                           "ratio": x.get("BloggerCountRatioStr"), "gmv": x.get("SaleGmvStr")}
                          for x in (r3.get("data") or [])[:10]]
    out("   达人类型 %s 类" % len(d["blogger_types"]))

    # ---------- 3. 带货直播（接口加密 → DOM 兜底） ----------
    P.ev("window.__clickText('带货直播')")
    time.sleep(9); P.ev("window.__killMask()")
    t2 = P.body_text()
    i = t2.find("带货直播")
    seg = t2[i:i + 1200] if i >= 0 else t2[-800:]
    d["live_text"] = seg.replace("\n", " | ")[:900]
    out("   直播 DOM 片段 %s 字" % len(d["live_text"]))

    P.wb("close_tab", {}, timeout=20)
    time.sleep(1)
    return d


def load_source():
    if SRC == "cards":
        cards = json.load(open(P.dpath("cards.json"), encoding="utf-8"))
        items = []
        for gid, c in cards.items():
            it = dict(c)
            it["gid"] = gid
            items.append(it)
        items.sort(key=lambda x: (x.get("榜_rank") or 999, -(x.get("price_est") or 0)))
        return items
    return json.load(open(P.dpath("top30.json"), encoding="utf-8"))


def has_deep(d):
    if not d or d.get("err"):
        return False
    return bool(d.get("videos")) or bool(d.get("bloggers")) or bool(d.get("wordcloud"))


def main():
    items = load_source()
    only = [x for x in (os.environ.get("DEEP_ONLY_GIDS", "").split(",")) if x.strip()]
    if only:
        items = [it for it in items if it["gid"] in only]
        out("只跑指定 gid：%s" % only)
    if TOPN:
        items = items[:TOPN]
    deep = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    out("login:", P.check_login(), " 源=%s 商品数=%s skip_done=%s" % (SRC, len(items), SKIPDONE))
    done = 0
    for i, it in enumerate(items):
        gid = it["gid"]
        have_cover = bool((deep.get(gid) or {}).get("cover"))
        if ONLYCOVER:
            todo = DOCOVER and not have_cover
        else:
            todo = not (SKIPDONE and has_deep(deep.get(gid)) and have_cover)
        if not todo:
            out("[%d/%d] skip 已有 %s" % (i + 1, len(items), (it.get("title") or "")[:26]))
            continue
        out("\n[%d/%d] %s" % (i + 1, len(items), (it.get("title") or "")[:40]))
        try:
            d = one(it, i)
        except Exception as e:
            out("   !! 异常:", e)
            old = deep.get(gid) or {}
            d = dict(old)
            d.update({"gid": gid, "title": it.get("title"), "err": str(e)})
        deep[gid] = d
        done += 1
        json.dump(deep, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    out("\n已写 data/%s (%d 个商品，本次处理 %d)" % (P.dname("deep.json"), len(deep), done))
    for g, d in deep.items():
        out("  %s 视频%s 达人%s 词云%s 封面%s" % (g[:12], len(d.get("videos") or []),
                                                len(d.get("bloggers") or []),
                                                len(d.get("wordcloud") or []),
                                                "有" if d.get("cover") else "-"))


if __name__ == "__main__":
    main()
