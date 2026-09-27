# -*- coding: utf-8 -*-
"""15 · 抓真·商品主图（800×800，抖音电商图床）

★ 发现（2026-09-26）：飞瓜商品详情页 DOM 里的 img.img-product 恒为 1491B 的 base64 占位图，
  但**明文接口** /api/v1/goods/getSegmentCommentsV2 的响应里带 GoodsInfo.CoverUrl，
  就是 800×800 的真商品主图（p*-aio.ecombdimg.com/img/ecom-shop-material/...）。
  前提：必须先点开该链接的「商品评价」tab 建立上下文，否则接口返空 / Code500。

★ 一商品一独立标签页（同页批量会「假返空」）
产出：data/prodimg.json + assets/products/<gid>.<ext>
"""
import os, sys, json, time, subprocess

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
import pcommon as P

DATA = os.path.join(BASE, "data")
OUTIMG = os.path.join(BASE, "assets", "products")
os.makedirs(OUTIMG, exist_ok=True)
HELPER = open(os.path.join(BASE, "tmp", "_helper.js"), encoding="utf-8").read()
JP_HOOK = open(os.path.join(BASE, "tmp", "_jp_hook.js"), encoding="utf-8").read()
META = P.dpath("prodimg.json")
LOG = open(os.path.join(BASE, "tmp", "15_prodimg_%s.log" % (P.CATE_NS or "eye")), "w", encoding="utf-8")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def out(*a):
    s = " ".join(str(x) for x in a)
    LOG.write(s + "\n"); LOG.flush(); print(s, flush=True)


JS_SCAN = r"""
(function(){
  var hits = [];
  (window.__jp || []).forEach(function(s){
    var m = s.match(/"(?:Original)?CoverUrl":"(https?:[^"]+)"/g) || [];
    m.forEach(function(x){
      var u = x.replace(/^"(?:Original)?CoverUrl":"/, '').replace(/"$/, '');
      if (hits.indexOf(u) < 0) hits.push(u);
    });
  });
  return JSON.stringify({n: (window.__jpN || 0), cap: (window.__jp || []).length, hits: hits});
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


def dl(url, stem):
    """下载；.part + os.replace 落盘（禁止 os.remove）"""
    ext = ".webp" if ".webp" in url.lower() else (".png" if ".png" in url.lower() else ".jpg")
    final = stem + ext
    if os.path.exists(final) and os.path.getsize(final) > 3000:
        return final, "skip"
    part = final + ".part"
    try:
        subprocess.run(["curl", "-s", "-m", "30", "-A", UA,
                        "-e", "https://dy.feigua.cn/", "-o", part, url],
                       capture_output=True, timeout=45)
        if os.path.exists(part) and os.path.getsize(part) > 3000:
            os.replace(part, final)
            return final, "ok %d" % os.path.getsize(final)
        return None, "small/fail"
    except Exception as e:
        return None, "err %s" % e


def main():
    cards = json.load(open(P.dpath("cards.json"), encoding="utf-8"))
    items = []
    for gid, c in cards.items():
        c = dict(c); c["gid"] = gid; items.append(c)
    items.sort(key=lambda x: (x.get("榜_rank") or 999))

    ONLY = [x for x in os.environ.get("PRODIMG_ONLY_GIDS", "").split(",") if x.strip()]
    if ONLY:
        items = [i for i in items if i["gid"] in ONLY]

    D1, D2 = P._dcode(29), P._dcode(0)
    meta = json.load(open(META, encoding="utf-8")) if os.path.exists(META) else {}
    todo = [i for i in items if not (meta.get(i["gid"]) or {}).get("file")]
    out("login:", P.check_login(), " 待抓商品主图 =", len(todo), "/", len(items))
    if not todo:
        return

    for n, it in enumerate(todo):
        gid = it["gid"]
        url = ("https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=%s&tab=overview&ts=%s&sign=%s"
               % (gid, it.get("ts"), it.get("sign")))
        cover, hits, j = "", [], {}
        for attempt in range(2):
            P.wb("navigate", {"url": url, "newTab": True}, wait=9)
            time.sleep(9)
            P.ev(HELPER)
            # ★ 装 JSON.parse 钩子：页面自己的请求是加密返回的，只有解密后 parse 的那一刻才是明文
            P.ev(JP_HOOK)
            P.click_tab_full("商品评价")
            time.sleep(11)
            P.ev("window.__killMask && window.__killMask()")
            j = ev_json(JS_SCAN, wait=8, tries=2) or {}
            hits = [h for h in (j.get("hits") or []) if h.startswith("http")]
            cover = hits[0] if hits else ""
            try:
                P.wb("close_tab", {}, timeout=20)
            except Exception:
                pass
            if cover:
                break
            out("    第%d次没拿到，换个干净标签页重试" % (attempt + 1))
            time.sleep(3)

        if not cover:
            out("[%d/%d] ✗ %s | %s" % (n + 1, len(todo), (it.get("title") or "")[:22], str(j)[:300]))
            meta[gid] = {"src": None, "file": None, "title": it.get("title")}
        else:
            f, st = dl(cover, os.path.join(OUTIMG, gid))
            out("[%d/%d] %s → %s (%s) 命中%d张" % (n + 1, len(todo), (it.get("title") or "")[:20],
                                                    os.path.basename(f) if f else "FAIL", st, len(hits)))
            meta[gid] = {"src": cover, "file": os.path.basename(f) if f else None,
                         "all": hits[:6], "title": it.get("title")}
        json.dump(meta, open(META, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        time.sleep(1.5)

    json.dump(meta, open(META, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ok = sum(1 for v in meta.values() if v.get("file"))
    out("\nDONE 有商品主图 = %d / %d" % (ok, len(meta)))


if __name__ == "__main__":
    main()
