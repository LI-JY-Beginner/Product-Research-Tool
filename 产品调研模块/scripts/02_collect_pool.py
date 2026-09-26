# -*- coding: utf-8 -*-
"""B2 · 扩池：飞瓜「商品销售榜」= 类目筛选 + 关键词搜索，滚动加载，抽 gid/ts/sign
用法:
    python scripts/02_collect_pool.py                 # 默认 个护家清 × 8 个眼部关键词
    python scripts/02_collect_pool.py 美妆            # 追加一轮别的类目
产出: data/pool_raw.json  (累加，不覆盖)
"""
import os, sys, json, time, re, io

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
import pcommon as P

DATA = os.path.join(BASE, "data")
os.makedirs(DATA, exist_ok=True)
POOL = os.path.join(DATA, "pool_raw.json")
HELPER = open(os.path.join(BASE, "tmp", "_helper.js"), encoding="utf-8").read()

CATE = sys.argv[1] if len(sys.argv) > 1 else "个护家清"
PERIOD = "月榜"          # 月榜=近30天销售额口径，与用户调研模块对齐
KEYWORDS = ["眼油", "眼部精华", "眼精华", "眼霜", "眼膜", "眼贴", "眼周", "眼部护理"]

LOG = open(os.path.join(BASE, "tmp", "02_pool_%s.log" % CATE), "w", encoding="utf-8")
def out(*a):
    s = " ".join(str(x) for x in a)
    LOG.write(s + "\n"); LOG.flush(); print(s, flush=True)


EXTRACT_JS = r"""
(function(){
  var res=[];
  [].slice.call(document.querySelectorAll('a[href*="gid="]')).forEach(function(a){
    var h=a.getAttribute('href')||'';
    var m=h.match(/gid=([^&]+)/); if(!m) return;
    var ts=(h.match(/ts=(\d+)/)||[])[1]||'';
    var sg=(h.match(/sign=([0-9a-f]+)/)||[])[1]||'';
    var row=a;
    for(var i=0;i<8 && row.parentElement;i++){
      row=row.parentElement;
      var t=(row.innerText||'').trim();
      if(/^\d{1,5}\s*\n/.test(t) && t.length>20) break;
    }
    var title=(a.innerText||'').trim();
    res.push({gid:m[1], ts:ts, sign:sg, title:title, raw:(row.innerText||'').trim()});
  });
  // 去重
  var seen={}, out=[];
  res.forEach(function(r){ if(!seen[r.gid]){seen[r.gid]=1; out.push(r);} });
  return JSON.stringify(out);
})()
"""


def parse_row(r):
    """把行文本解析成结构化字段（★ 标题一律从 raw 第二行取：a.innerText 在月榜版式里是空的）"""
    lines = [x.strip() for x in (r.get("raw") or "").split("\n") if x.strip()]
    if not lines:
        return None
    rank = None
    if re.match(r"^\d{1,5}$", lines[0]):
        rank = int(lines[0]); lines = lines[1:]
    # 第一行即商品标题
    title = (r.get("title") or "").strip() or (lines[0] if lines else "")
    if lines and lines[0] == title:
        lines = lines[1:]
    # 去标签、抽比率
    commission, praise = None, None
    keep = []
    for x in lines:
        if x in ("价格", "商品", "SPU"):
            continue
        if x.startswith("佣金率"):
            commission = x.replace("佣金率", "").strip()
        elif x.startswith("好评率"):
            praise = x.replace("好评率", "").strip()
        else:
            keep.append(x)
    nums = [x for x in keep if re.search(r"\d", x)]
    def g(i):
        return nums[i] if i < len(nums) else None
    return {
        "gid": r["gid"], "ts": r["ts"], "sign": r["sign"],
        "title": title, "rank_in_cate": rank,
        "sales_tier": g(0), "volume_tier": g(1), "views": g(2),
        "videos": g(3), "lives": g(4), "talents": g(5),
        "commission": commission, "praise": praise,
        "cate": CATE, "kw": r.get("_kw", ""),
    }


def do_search(kw, scroll_rounds=6):
    """一次「类目+关键词」搜索，返回结构化行"""
    P.wb("navigate", {"url": "https://dy.feigua.cn/app/#/product-rank/index?tab=product", "newTab": True}, wait=8)
    time.sleep(9)
    P.ev(HELPER); P.ev("window.__killMask()")
    # 周期
    out("   周期:", P.ev("window.__clickText('%s')" % PERIOD))
    time.sleep(2); P.ev("window.__killMask()")
    # 类目
    out("   类目:", P.ev("window.__clickText('%s')" % CATE))
    time.sleep(2); P.ev("window.__killMask()")
    # 关键词
    out("   填词:", P.ev("window.__fillInput('%s','请输入商品关键词搜索')" % kw))
    time.sleep(2)
    out("   搜索:", P.ev("""
      (function(){var bs=[].slice.call(document.querySelectorAll('button')).filter(function(b){
        var r=b.getBoundingClientRect(); return (b.innerText||'').trim()==='搜索' && r.y>350 && r.width>0;});
        return bs.length? window.__clickEl(bs[0]) : 'no-btn';})()
    """))
    time.sleep(10); P.ev("window.__killMask()")

    seen = {}
    for i in range(scroll_rounds):
        raw = P.ev(EXTRACT_JS)
        try:
            rows = json.loads(raw) if isinstance(raw, str) else (raw or [])
        except Exception:
            rows = []
        new = 0
        for r in rows:
            if r["gid"] not in seen:
                r["_kw"] = kw; seen[r["gid"]] = r; new += 1
        out("     轮%d: 本页%d 新增%d 累计%d" % (i + 1, len(rows), new, len(seen)))
        if i == scroll_rounds - 1 or (new == 0 and i > 0):
            break
        P.ev("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(3)
        P.ev("window.__killMask()")
    P.wb("close_tab", {}, timeout=20)
    time.sleep(1)
    return seen


def main():
    MODE = sys.argv[2] if len(sys.argv) > 2 else "scrape"
    out("login:", P.check_login())
    pool = {}
    if os.path.exists(POOL):
        try:
            pool = json.load(open(POOL, encoding="utf-8"))
            out("已存在池子:", len(pool))
        except Exception:
            pool = {}

    if MODE == "reparse":
        finish(pool)
        return

    for kw in KEYWORDS:
        out("\n===== 类目[%s] 关键词[%s] =====" % (CATE, kw))
        try:
            got = do_search(kw)
        except Exception as e:
            out("   !! 异常:", e); continue
        n_new = 0
        for gid, r in got.items():
            if gid not in pool:
                pool[gid] = r; n_new += 1
        out("   新增 %d / 池子 %d" % (n_new, len(pool)))
        json.dump(pool, open(POOL, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    finish(pool)


def finish(pool):
    """解析 + 准确性过滤 + 排序 + 定稿 TOP30"""
    # 1) 统一解析
    parsed = []
    for gid, r in pool.items():
        p = parse_row(r)
        if not p:
            continue
        p["gid"] = gid
        parsed.append(p)

    # 2) 准确性过滤：标题必须含眼部词，排除彩妆类
    BAD = ("眼影", "眼线", "睫毛", "眉笔", "眉粉", "眼镜", "美瞳", "双眼皮")
    ok, bad = [], []
    for p in parsed:
        t = p.get("title") or ""
        if any(b in t for b in BAD):
            bad.append(t); continue
        if "眼" in t:
            ok.append(p)
        else:
            bad.append(t)
    out("\n===== 汇总 =====")
    out("池子总数:", len(pool), " 解析成功:", len(parsed), " 通过眼部校验:", len(ok), " 剔除:", len(bad))
    for t in bad[:20]:
        out("   剔除:", (t or "")[:60])

    # 3) 同品归一化去重（标题 jaccard）
    uniq = []
    for p in ok:
        dup = None
        for u in uniq:
            if P.jaccard(P.norm_title(p["title"]), P.norm_title(u["title"])) >= 0.72:
                dup = u; break
        if dup is None:
            uniq.append(p)
        else:
            # 保留销售额更高的那条
            if P.tier_mid(p.get("sales_tier")) > P.tier_mid(dup.get("sales_tier")):
                dup.update(p)
    out("归一化去重后:", len(uniq))

    # 4) 排序：销售额档中位数 → 销量档 → 浏览量
    def key(p):
        return (P.tier_mid(p.get("sales_tier")),
                P.tier_mid(p.get("volume_tier")),
                P.num(p.get("views")) or 0)
    uniq.sort(key=key, reverse=True)

    for i, p in enumerate(uniq, 1):
        p["rank"] = i
    top30 = uniq[:30]

    out("\n===== TOP30 =====")
    for p in top30:
        out("  %2d. [%s] %s | 销售额%s 销量%s 浏览%s 视频%s 直播%s 达人%s 好评%s" % (
            p["rank"], p.get("kw"), (p.get("title") or "")[:38], p.get("sales_tier"),
            p.get("volume_tier"), p.get("views"), p.get("videos"), p.get("lives"),
            p.get("talents"), p.get("praise")))

    json.dump(parsed, open(os.path.join(DATA, "pool_eye.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(top30, open(os.path.join(DATA, "top30.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    out("\n已写 data/pool_eye.json (%d) 与 data/top30.json (%d)" % (len(parsed), len(top30)))
    out("DONE")


if __name__ == "__main__":
    main()
