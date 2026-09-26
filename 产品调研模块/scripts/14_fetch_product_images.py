# -*- coding: utf-8 -*-
"""14 · 抓真·商品主图（按用户给的路径）
路径：飞瓜商品详情页 → 头部那张商品缩略图（img.xImg.img-product）
     → 它的 src 本身就是 800×800 的商品主图（抖音电商图床 ecombdimg.com，
        页面上只是被缩到 138px 显示）→ 直接下载替换卡面图。
     顺带把它外面 <a> 的抖店商品链接一起记下来。

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
META = os.path.join(DATA, "prodimg.json")
LOG = open(os.path.join(BASE, "tmp", "14_prodimg.log"), "w", encoding="utf-8")


def out(*a):
    s = " ".join(str(x) for x in a)
    LOG.write(s + "\n"); LOG.flush(); print(s, flush=True)


JS = r"""
(function(){
  var im = document.querySelector('img.img-product') || document.querySelector('.xImg.img-product');
  if (!im) return JSON.stringify({src: null});
  var a = im.closest('a');
  return JSON.stringify({
    src: im.getAttribute('src') || '',
    href: a ? a.getAttribute('href') : null
  });
})()
"""


def dl(url, path):
    """下载并用 .part + os.replace 落盘（禁止 os.remove）"""
    ext = ".webp" if ".webp" in url.lower() else (".png" if ".png" in url.lower() else ".jpg")
    final = path + ext
    if os.path.exists(final) and os.path.getsize(final) > 3000:
        return final, "skip"
    part = final + ".part"
    try:
        r = subprocess.run(["curl", "-s", "-m", "30", "-A",
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
                            "-e", "https://dy.feigua.cn/", "-o", part, url],
                           capture_output=True, timeout=45)
        if os.path.exists(part) and os.path.getsize(part) > 3000:
            os.replace(part, final)
            return final, "ok %d" % os.path.getsize(final)
        return None, "small/fail"
    except Exception as e:
        return None, "err %s" % e


def main():
    cards = json.load(open(os.path.join(DATA, "cards.json"), encoding="utf-8"))
    items = []
    for gid, c in cards.items():
        c = dict(c); c["gid"] = gid; items.append(c)
    items.sort(key=lambda x: (x.get("榜_rank") or 999))
    ONLY = [x for x in os.environ.get("PRODIMG_ONLY_GIDS", "").split(",") if x.strip()]
    if ONLY:
        items = [i for i in items if i["gid"] in ONLY]

    meta = json.load(open(META, encoding="utf-8")) if os.path.exists(META) else {}
    todo = [i for i in items if not (meta.get(i["gid"]) or {}).get("src")]
    out("login:", P.check_login(), " 待抓商品图 =", len(todo), "/", len(items))
    if not todo:
        return

    for n, it in enumerate(todo):
        gid = it["gid"]
        url = ("https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=%s&tab=overview&ts=%s&sign=%s"
               % (gid, it.get("ts"), it.get("sign")))
        P.wb("navigate", {"url": url, "newTab": True}, wait=9)
        time.sleep(9)
        P.ev(HELPER)
        r = P.ev(JS, wait=3)
        P.wb("close_tab", {}, timeout=20)
        try:
            j = json.loads(r) if isinstance(r, str) else (r or {})
        except Exception:
            j = {}
        src = (j.get("src") or "").strip()
        href = j.get("href")
        if not src or src.startswith("data:"):
            out("[%d/%d] ✗ 无商品图 %s" % (n + 1, len(todo), (it.get("title") or "")[:22]))
            meta[gid] = {"src": None, "href": href, "title": it.get("title")}
        else:
            f, st = dl(src, os.path.join(OUTIMG, gid))
            out("[%d/%d] %s → %s (%s)" % (n + 1, len(todo), (it.get("title") or "")[:20],
                                          os.path.basename(f) if f else "FAIL", st))
            meta[gid] = {"src": src, "file": os.path.basename(f) if f else None,
                         "href": href, "title": it.get("title")}
        json.dump(meta, open(META, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    json.dump(meta, open(META, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ok = sum(1 for v in meta.values() if v.get("file"))
    out("\nDONE 有商品图 = %d / %d" % (ok, len(meta)))


if __name__ == "__main__":
    main()
