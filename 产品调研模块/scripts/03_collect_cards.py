# -*- coding: utf-8 -*-
"""B3-B5 · 卡片层：30 个商品各开一次详情页，从渲染好的 DOM 抽基础字段
用法:
    python scripts/03_collect_cards.py            # 全量 30 个
    python scripts/03_collect_cards.py 0 10       # 只跑第 1~10 个（分批用）
产出: data/cards.json （增量写，中断可续）
"""
import os, sys, json, time, re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
import pcommon as P

DATA = os.path.join(BASE, "data")
HELPER = open(os.path.join(BASE, "tmp", "_helper.js"), encoding="utf-8").read()
CARDS = os.path.join(DATA, "cards.json")

LOGP = os.path.join(BASE, "tmp", "03_cards.log")
LOG = open(LOGP, "w", encoding="utf-8")
def out(*a):
    s = " ".join(str(x) for x in a)
    LOG.write(s + "\n"); LOG.flush(); print(s, flush=True)

LABELS = ["销售额", "销量", "订单量", "浏览量", "转化率", "带货视频", "带货直播", "带货达人"]


def seg(txt, a, b):
    i, j = txt.find(a), txt.find(b)
    if i < 0:
        return ""
    return txt[i:j] if j > i else txt[i:]


def parse_overview(txt):
    d = {}
    # —— 头部：标题 / 榜单位置
    m = re.search(r"飞瓜抖音\n([^\n]+)\n复制标题", txt)
    if m:
        d["title"] = m.group(1).strip()
    m = re.search(r"商品销售榜/([^/\n]+)/([^\n]+?)第(\d+)名", txt)
    if m:
        d["rank_cate"], d["rank_period"], d["rank_no"] = m.group(1), m.group(2), int(m.group(3))

    # —— 基础信息段（更新时间 ~ 分析同类商品热度）
    s = seg(txt, "更新时间", "分析同类商品热度")
    m = re.search(r"更新时间：([^\n]+)", s)
    if m:
        d["update_time"] = m.group(1).strip()
    for key, pat in (("brand", r"\n品牌\n([^\n]+)"),
                     ("shop", r"\n小店\n([^\n]+)"),
                     ("cate", r"\n分类\n([^\n]+)")):
        m = re.search(pat, s)
        if m:
            d[key] = m.group(1).strip()
    m = re.search(r"\n小店\n[^\n]+\n([\d.]+)", s)
    if m:
        d["shop_score"] = m.group(1).strip()
    m = re.search(r"近30天销量：([^\n]+)", s)
    if m:
        d["volume_30d"] = m.group(1).strip()
    m = re.search(r"佣金率：([\d.]+)%[（(]\s*￥([\d.]+)\s*[）)]", s)
    if m:
        d["commission_rate"] = m.group(1) + "%"
        d["commission_fee"] = "￥" + m.group(2)
        try:
            d["price_est"] = round(float(m.group(2)) / (float(m.group(1)) / 100.0), 1)
        except Exception:
            pass
    m = re.search(r"上架时间：([\d/]+)", s)
    if m:
        d["onsale_date"] = m.group(1).strip()
    m = re.search(r"共([\d.]+[w万]?)条评价好评([\d.]+)%", s)
    if m:
        d["reviews"], d["praise"] = m.group(1), m.group(2) + "%"

    # —— 商品数据段
    s2 = seg(txt, "商品数据", "销售渠道")
    lines = [x.strip() for x in s2.split("\n") if x.strip()]
    for i, l in enumerate(lines):
        if l in LABELS and i + 1 < len(lines) and lines[i + 1] not in LABELS:
            d.setdefault(l, lines[i + 1])

    # —— 渠道结构 / 带货方式
    for tag, a, b in (("channel", "销售渠道", "带货方式"), ("selltype", "带货方式", "销售趋势")):
        s3 = seg(txt, a, b)
        got = re.findall(r"(视频|直播|商品卡|品牌自营|达人推广)\s*\n\s*([^\n]+?)\s*\n\s*([\d.]+)%", s3)
        d[tag] = [{"name": g[0], "gmv": g[1], "pct": g[2] + "%"} for g in got]
    return d


def fetch_one(it, idx):
    gid, ts, sg = it["gid"], it.get("ts", ""), it.get("sign", "")
    url = "https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=%s&tab=overview" % gid
    if ts and sg:
        url += "&ts=%s&sign=%s" % (ts, sg)
    P.wb("navigate", {"url": url, "newTab": True}, wait=8)
    time.sleep(5)
    P.ev(HELPER); P.ev("window.__killMask()")
    ok = False
    for _ in range(10):
        t = P.body_text()
        if "上架时间" in t or "近30天销量" in t:
            ok = True; break
        time.sleep(2.5)
        P.ev("window.__killMask()")
    if not ok:
        out("   !! 未渲染 gid=%s" % gid)
    time.sleep(2); P.ev("window.__killMask()")
    txt = P.body_text()
    d = parse_overview(txt)
    d["gid"] = gid
    d["ts"], d["sign"] = ts, sg
    d["_ok"] = ok
    # 商品主图 + 抖音商品链接
    imgs = P.ev("""
      (function(){var s=new Set();
        [].slice.call(document.querySelectorAll('img')).forEach(function(im){
          var src=im.getAttribute('src')||'';
          if(src.indexOf('http')===0 && src.length>25) s.add(src);});
        return JSON.stringify(Array.from(s).slice(0,6));})()
    """)
    try:
        arr = json.loads(imgs) if isinstance(imgs, str) else (imgs or [])
    except Exception:
        arr = []
    d["imgs"] = arr[:4]
    links = P.ev("""
      (function(){var s=new Set();
        [].slice.call(document.querySelectorAll('a')).forEach(function(a){
          var h=a.getAttribute('href')||'';
          if(/jinritemai|douyin\\.com|haohuo/.test(h)) s.add(h);});
        return JSON.stringify(Array.from(s).slice(0,4));})()
    """)
    try:
        lk = json.loads(links) if isinstance(links, str) else (links or [])
    except Exception:
        lk = []
    d["douyin_links"] = lk
    # 榜单字段（来自商品榜，兜底）
    for k in ("sales_tier", "volume_tier", "views", "videos", "lives", "talents", "kw", "rank"):
        d.setdefault("榜_" + k, it.get(k))
    P.wb("close_tab", {}, timeout=20)
    time.sleep(1)
    return d


def main():
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    b = int(sys.argv[2]) if len(sys.argv) > 2 else 999
    top = json.load(open(os.path.join(DATA, "top30.json"), encoding="utf-8"))
    cards = json.load(open(CARDS, encoding="utf-8")) if os.path.exists(CARDS) else {}
    out("login:", P.check_login(), " 待采集:", len(top), " 已有:", len(cards))
    for i, it in enumerate(top):
        if i < a or i >= b:
            continue
        gid = it["gid"]
        if gid in cards and cards[gid].get("_ok"):
            out("[%d] 跳过(已有) %s" % (i + 1, (it.get("title") or "")[:26]))
            continue
        out("\n[%d/%d] %s" % (i + 1, len(top), (it.get("title") or "")[:40]))
        try:
            d = fetch_one(it, i)
        except Exception as e:
            out("   !! 异常:", e)
            d = {"gid": gid, "_ok": False, "err": str(e)}
        cards[gid] = d
        json.dump(cards, open(CARDS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        out("   品牌=%s 小店=%s 分类=%s 上架=%s 佣金=%s 好评=%s 销售额=%s 销量=%s" % (
            d.get("brand"), d.get("shop"), d.get("cate"), d.get("onsale_date"),
            d.get("commission_rate"), d.get("praise"), d.get("销售额"), d.get("销量")))
    ok = sum(1 for v in cards.values() if v.get("_ok"))
    out("\n完成：%d/%d 成功" % (ok, len(cards)))
    out("已写 data/cards.json")


if __name__ == "__main__":
    main()
