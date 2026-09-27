# -*- coding: utf-8 -*-
"""02b · 扩池（面部护理版）：飞瓜「商品销售榜」= 类目 个护家清 + 关键词搜索
★ 与 02_collect_pool.py 完全同一套逻辑，差别只有两点：
   ① 关键词按「三级类目」分组，每个三级类目各定稿 TOP-N（保证卡墙筛选里每个类目都有货）
   ② 每条结果带上 catePath = {L1, L2, L3}，供页面三级联动筛选真过滤

用法:
    python scripts/02b_collect_pool_face.py                 # 默认每类 TOP6
    FACE_QUOTA=8 python scripts/02b_collect_pool_face.py     # 每类 TOP8
产出: data/pool_raw_face.json（累加） / data/pool_face.json / data/top30_face.json
"""
import os, sys, json, time, re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
import pcommon as P

DATA = os.path.join(BASE, "data")
POOL = P.dpath("pool_raw.json")          # PCATE=face -> pool_raw_face.json
HELPER = open(os.path.join(BASE, "tmp", "_helper.js"), encoding="utf-8").read()

L1 = "个护家清"
L2 = "面部护理"
PERIOD = "月榜"
QUOTA = int(os.environ.get("FACE_QUOTA", "6"))

# ★ 顺序 = 归属优先级（越靠前越"专属"，避免一个商品被同时算进两个类目）
L3GROUPS = [
    ("面膜",     ["面膜", "补水面膜", "涂抹面膜"]),
    ("防晒",     ["防晒霜", "防晒", "隔离防晒"]),
    ("洁面",     ["洁面", "洗面奶", "洁面乳"]),
    ("爽肤水",   ["爽肤水", "化妆水", "精华水"]),
    ("面霜",     ["面霜", "抗皱面霜", "保湿面霜"]),
    ("面部精华", ["面部精华", "面部精华液", "精华液"]),
]

# 全域排除：非面部护理
BAD_ANY = ("眼", "睫毛", "眼影", "眼线", "眉笔", "眉粉", "美瞳", "眼镜", "洗发", "护发", "发膜",
           "头皮", "防脱", "固发", "生发", "育发", "发际",
           "沐浴", "身体", "护手", "足膜", "牙膏", "牙刷", "漱口", "洗衣", "洗洁", "纸品", "湿巾",
           "卫生巾", "私处", "宠物", "猫粮", "狗粮", "奶粉", "纸尿裤", "内衣", "袜子", "鞋", "帽",
           "口罩", "香水", "口红", "粉底", "遮瑕", "散粉", "腮红", "指甲", "假发", "剃须", "脱毛")
# 类目专属正向词
L3_REQ = {
    "面膜":     ("面膜",),
    "防晒":     ("防晒",),
    "洁面":     ("洁面", "洗面奶", "洁颜"),
    "爽肤水":   ("爽肤水", "化妆水", "精华水", "柔肤水", "保湿水"),
    "面霜":     ("面霜", "霜"),
    "面部精华": ("精华",),
}
# 防晒类目额外排除（防晒衣/伞/帽等非护肤品）
SUN_BAD = ("衣", "伞", "帽", "手套", "袖", "裤")

LOG = open(os.path.join(BASE, "tmp", "02b_pool_face.log"), "w", encoding="utf-8")


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
    title = (r.get("title") or "").strip() or (lines[0] if lines else "")
    if lines and lines[0] == title:
        lines = lines[1:]
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
        "cate": L1, "kw": r.get("_kw", ""),
    }


def do_search(kw, scroll_rounds=6):
    """一次「类目+关键词」搜索，返回结构化行"""
    P.wb("navigate", {"url": "https://dy.feigua.cn/app/#/product-rank/index?tab=product", "newTab": True}, wait=8)
    time.sleep(9)
    P.ev(HELPER); P.ev("window.__killMask()")
    out("   周期:", P.ev("window.__clickText('%s')" % PERIOD))
    time.sleep(2); P.ev("window.__killMask()")
    out("   类目:", P.ev("window.__clickText('%s')" % L1))
    time.sleep(2); P.ev("window.__killMask()")
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


def ok_l3(title, l3):
    """标题是否属于该三级类目"""
    t = title or ""
    if any(b in t for b in BAD_ANY):
        return False
    if l3 == "防晒" and any(b in t for b in SUN_BAD):
        return False
    if l3 == "面霜":
        if "面霜" in t:
            return True
        return ("霜" in t) and ("防晒" not in t) and ("洗面" not in t) and ("洁面" not in t)
    return any(k in t for k in L3_REQ[l3])


def main():
    out("login:", P.check_login())
    pool = P.load_json(POOL, {}) or {}
    out("已存在面部池子:", len(pool))
    eye_pool = P.load_json(os.path.join(DATA, "pool_eye.json"), []) or []
    eye_gids = set(x.get("gid") for x in eye_pool if x.get("gid"))
    out("眼部池子 gid 数（用于跨类目去重）:", len(eye_gids))

    for l3, kws in L3GROUPS:
        for kw in kws:
            key = "%s|%s" % (l3, kw)
            if any(r.get("_kw") == kw and r.get("_l3") == l3 for r in pool.values()):
                out("\n===== [%s] 关键词[%s] 已在池中，跳过 =====" % (l3, kw))
                continue
            out("\n===== [%s] 关键词[%s] =====" % (l3, kw))
            try:
                got = do_search(kw)
            except Exception as e:
                out("   !! 异常:", e); continue
            n_new = 0
            for gid, r in got.items():
                if gid not in pool:
                    r["_l3"] = l3
                    pool[gid] = r; n_new += 1
            out("   新增 %d / 面部池子 %d" % (n_new, len(pool)))
            json.dump(pool, open(POOL, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    finish(pool, eye_gids)


def finish(pool, eye_gids):
    """解析 → 类目归属（按 L3 优先级，互斥）→ 每个三级类目各取 TOP-N"""
    parsed = []
    for gid, r in pool.items():
        p = parse_row(r)
        if not p:
            continue
        p["gid"] = gid
        p["_l3"] = r.get("_l3") or ""
        parsed.append(p)

    out("\n===== 汇总 =====")
    out("面部池子:", len(pool), " 解析成功:", len(parsed))

    # 1) 全域校验
    kept, dropped = [], []
    for p in parsed:
        t = p.get("title") or ""
        if p["gid"] in eye_gids:
            dropped.append((t, "已在眼部护理池")); continue
        if any(b in t for b in BAD_ANY):
            dropped.append((t, "非面部护理")); continue
        kept.append(p)
    out("全域通过:", len(kept), " 剔除:", len(dropped))
    for t, why in dropped[:15]:
        out("   剔除[%s]:" % why, (t or "")[:52])

    # 2) 类目归属：以「命中它的三级类目关键词」为准（采集时已记录 _l3），
    #    没有关键词归属时才用标题规则。因为一个商品只会被记一个 _l3，所以各桶天然互斥。
    L3SET = [g[0] for g in L3GROUPS]
    assigned, taken_gids = {}, set()
    for l3, _ in L3GROUPS:
        bucket = []
        for p in kept:
            if p["gid"] in taken_gids:
                continue
            own = p.get("_l3") or ""
            if own in L3SET:
                belong = (own == l3)
            else:
                belong = ok_l3(p.get("title") or "", l3)
            if belong:
                bucket.append(p)
        # 3) 同品归一化去重（标题 jaccard ≥0.72，保留销售额档更高的）
        uniq = []
        for p in bucket:
            dup = None
            for u in uniq:
                if P.jaccard(P.norm_title(p["title"]), P.norm_title(u["title"])) >= 0.72:
                    dup = u; break
            if dup is None:
                uniq.append(p)
            elif P.tier_mid(p.get("sales_tier")) > P.tier_mid(dup.get("sales_tier")):
                dup.update(p)
        # 4) 排序：销售额档中位 → 销量档 → 浏览量
        uniq.sort(key=lambda x: (P.tier_mid(x.get("sales_tier")),
                                 P.tier_mid(x.get("volume_tier")),
                                 P.num(x.get("views")) or 0), reverse=True)
        for p in uniq:
            taken_gids.add(p["gid"])
        for i, p in enumerate(uniq, 1):
            p["rank_in_l3"] = i
        assigned[l3] = uniq
        out("\n[%s] 候选 %d → TOP%d" % (l3, len(uniq), QUOTA))
        for p in uniq[:QUOTA]:
            out("   %2d. %s | 销售额%s 销量%s 浏览%s 视频%s 达人%s" % (
                p["rank_in_l3"], (p.get("title") or "")[:40], p.get("sales_tier"),
                p.get("volume_tier"), p.get("views"), p.get("videos"), p.get("talents")))

    # 5) 定稿：每个三级类目各 TOP-N，全局 rank 按销售额降序
    final = []
    for l3, _ in L3GROUPS:
        for p in assigned.get(l3, [])[:QUOTA]:
            p["catePath"] = {"L1": L1, "L2": L2, "L3": l3}
            final.append(p)
    final.sort(key=lambda x: (P.tier_mid(x.get("sales_tier")),
                              P.tier_mid(x.get("volume_tier")),
                              P.num(x.get("views")) or 0), reverse=True)
    for i, p in enumerate(final, 1):
        p["rank"] = i

    out("\n===== 面部护理定稿 %d 条（每类 TOP%d）=====" % (len(final), QUOTA))
    for p in final:
        out("  %2d. [%s] %s | 销售额%s 浏览%s" % (
            p["rank"], p["catePath"]["L3"], (p.get("title") or "")[:38],
            p.get("sales_tier"), p.get("views")))

    json.dump(parsed, open(os.path.join(DATA, "pool_face.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(final, open(P.dpath("top30.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    out("\n已写 data/pool_face.json (%d) 与 data/%s (%d)" % (len(parsed), P.dname("top30.json"), len(final)))
    out("DONE")


if __name__ == "__main__":
    main()
