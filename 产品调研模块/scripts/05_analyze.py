# -*- coding: utf-8 -*-
"""B7 · 聚合分析：把 cards(30) + deep(5) 汇总成页面要用的 analysis.json
产出: data/analysis.json
"""
import os, sys, json, re, collections, statistics

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
import pcommon as P

DATA = os.path.join(BASE, "data")
top30 = json.load(open(os.path.join(DATA, "top30.json"), encoding="utf-8"))
cards = json.load(open(os.path.join(DATA, "cards.json"), encoding="utf-8"))
deep = json.load(open(os.path.join(DATA, "deep.json"), encoding="utf-8"))
pool = json.load(open(os.path.join(DATA, "pool_eye.json"), encoding="utf-8"))

A = {}


def pct(x, n):
    return round(100.0 * x / n, 1) if n else 0.0


def dist(items, key, norm=None, top=None):
    c = collections.Counter()
    for it in items:
        v = it.get(key)
        if v in (None, "", "--"):
            continue
        c[norm(v) if norm else v] += 1
    out = c.most_common()
    return out[:top] if top else out


# ============ 1. 卡片层：30 个商品 ============
rows = []
for it in top30:
    c = cards.get(it["gid"], {})
    r = dict(it)
    r.update({k: v for k, v in c.items() if not k.startswith("_") and k != "imgs"})
    rows.append(r)

A["n_top"] = len(rows)
A["n_pool"] = len(pool)

# 细分类目
A["cate_dist"] = [{"name": k, "n": v, "pct": pct(v, len(rows))}
                  for k, v in dist(rows, "cate")]
# 销售额档 / 销量档
A["sales_dist"] = [{"name": k, "n": v} for k, v in dist(rows, "销售额")]
A["volume_dist"] = [{"name": k, "n": v} for k, v in dist(rows, "销量")]
# 品牌
brands = collections.Counter()
brand_gmv = collections.defaultdict(float)
for r in rows:
    b = r.get("brand") or "未标注"
    brands[b] += 1
    brand_gmv[b] += P.tier_mid(r.get("销售额"))
A["brand_top"] = [{"name": b, "n": n, "gmv_mid": brand_gmv[b]}
                  for b, n in brands.most_common(12)]
A["brand_concentration"] = {
    "top3_share": pct(sum(n for _, n in brands.most_common(3)), len(rows)),
    "top5_share": pct(sum(n for _, n in brands.most_common(5)), len(rows)),
    "n_brands": len(brands),
}
# 上架时间 → 品龄
def age_bucket(d):
    if not d:
        return "未知"
    try:
        y, m, dd = [int(x) for x in d.split("/")]
    except Exception:
        return "未知"
    days = (2026 - y) * 365 + (9 - m) * 30 + (26 - dd)
    if days <= 180:
        return "新品(≤6个月)"
    if days <= 365:
        return "6-12个月"
    if days <= 730:
        return "1-2年"
    return "2年以上"

age_order = ["新品(≤6个月)", "6-12个月", "1-2年", "2年以上"]
c = collections.Counter(age_bucket(r.get("onsale_date")) for r in rows)
A["age_dist"] = [{"name": k, "n": c.get(k, 0), "pct": pct(c.get(k, 0), len(rows))}
                 for k in age_order if c.get(k)]

# 价格推算 / 佣金率 / 好评
def price_band(p):
    if not p:
        return None
    p = float(p)
    for lim, nm in ((50, "≤50元"), (100, "50-100元"), (200, "100-200元"),
                    (400, "200-400元"), (10 ** 9, "400元以上")):
        if p <= lim:
            return nm

c = collections.Counter(price_band(r.get("price_est")) for r in rows if r.get("price_est"))
A["price_dist"] = [{"name": k, "n": v} for k, v in c.most_common()]
A["price_stats"] = {
    "n": sum(1 for r in rows if r.get("price_est")),
    "median": round(statistics.median([r["price_est"] for r in rows if r.get("price_est")]), 1)
    if any(r.get("price_est") for r in rows) else None,
    "min": min([r["price_est"] for r in rows if r.get("price_est")], default=None),
    "max": max([r["price_est"] for r in rows if r.get("price_est")], default=None),
}
cr = [float(re.sub(r"[^\d.]", "", r["commission_rate"])) for r in rows if r.get("commission_rate")]
A["commission"] = {"n": len(cr), "avg": round(sum(cr) / len(cr), 2) if cr else None,
                   "max": max(cr) if cr else None, "min": min(cr) if cr else None}
pr = [float(re.sub(r"[^\d.]", "", r["praise"])) for r in rows if r.get("praise")]
A["praise"] = {"n": len(pr), "avg": round(sum(pr) / len(pr), 2) if pr else None,
               "min": min(pr) if pr else None, "max": max(pr) if pr else None}

# 渠道结构 & 带货方式（按商品求平均占比）
def avg_share(field, names):
    acc = collections.defaultdict(list)
    for r in rows:
        for x in (r.get(field) or []):
            try:
                acc[x["name"]].append(float(x["pct"].replace("%", "")))
            except Exception:
                pass
    res = []
    for n in names:
        v = acc.get(n)
        if v:
            res.append({"name": n, "avg": round(sum(v) / len(v), 1), "n_goods": len(v)})
    return sorted(res, key=lambda x: -x["avg"])

A["channel_mix"] = avg_share("channel", ["视频", "直播", "商品卡"])
A["selltype_mix"] = avg_share("selltype", ["品牌自营", "达人推广", "商品卡"])

# 带货资源量：视频/直播/达人数（中位数）
for key, label in (("带货视频", "videos"), ("带货直播", "lives"), ("带货达人", "talents")):
    vs = [P.num(r.get(key)) for r in rows if P.num(r.get(key)) is not None]
    A["res_" + label] = {"n": len(vs), "median": round(statistics.median(vs)) if vs else None,
                         "max": max(vs) if vs else None}

A["rows"] = rows

# ============ 2. 深度层：TOP5 ============
all_videos = []
wc_agg = collections.Counter()
wc_goods = collections.defaultdict(set)
D = {}
for gid, d in deep.items():
    vs = d.get("videos") or []
    all_videos.extend(vs)
    for w in (d.get("wordcloud") or []):
        k = w.get("kw")
        if not k:
            continue
        try:
            n = P.num(w.get("cnt")) or 0
        except Exception:
            n = 0
        wc_agg[k] += int(n)
        wc_goods[k].add(gid)
    D[gid] = {
        "title": d.get("title"),
        "videos_total": d.get("videos_total"),
        "bloggers_total": d.get("bloggers_total"),
        "bloggers": d.get("bloggers") or [],
        "concentration": d.get("concentration"),
        "blogger_types": d.get("blogger_types") or [],
        "live_text": d.get("live_text"),
        "wordcloud": (d.get("wordcloud") or [])[:40],
        "videos": vs[:20],
    }
A["deep"] = D
A["n_videos"] = len(all_videos)

# 关键词分类（功效/成分/人群/场景/情绪）
CAT_RULES = [
    ("功效", r"紧致|抗皱|淡纹|提亮|保湿|修护|抗老|抗初老|补水|舒缓|去眼袋|黑眼圈|消肿|提升|弹润|滋养|抗衰|淡纹|去皱|填充|嘭"),
    ("成分", r"PDRN|玻尿酸|胶原|胜肽|咖啡因|视黄醇|A醇|烟酰胺|神经酰胺|氨基酸|叶黄素|草本|植物|精油|角鲨烷|虾青素|谷胱甘肽|麦角硫因|依克多因|六胜肽|蓝铜"),
    ("人群", r"姐姐|女性|男士|男女|孕妇|学生|上班族|熬夜|妈妈|中年|30岁|40岁|50岁|初老|同龄人"),
    ("场景", r"熬夜|睡前|早上|通勤|办公室|出差|旅行|中秋|礼物|送礼|节日|日常|上妆|妆前|医美后"),
    ("情绪", r"早|显老|显小|年轻|焦虑|救|急救|后悔|绝了|惊艳|真香|必入|宝藏|神器|绝绝子"),
    ("部位", r"眼周|眼部|眼纹|眼袋|泪沟|鱼尾纹|眼皮|眼尾|眼下|卧蚕"),
]
def kw_cat(k):
    for nm, pat in CAT_RULES:
        if re.search(pat, k):
            return nm
    return "其他"

A["wordcloud_top"] = [{"kw": k, "cnt": v, "goods": len(wc_goods[k]), "cat": kw_cat(k)}
                      for k, v in wc_agg.most_common(60)]
bycat = collections.defaultdict(int)
for w in A["wordcloud_top"]:
    bycat[w["cat"]] += w["cnt"]
tot = sum(bycat.values()) or 1
A["wordcloud_cat"] = [{"name": k, "cnt": v, "pct": pct(v, tot)}
                      for k, v in sorted(bycat.items(), key=lambda x: -x[1])]

# 视频：时长分档效率 / 达人层级 / 钩子类型
def dur_sec(s):
    if not s:
        return None
    m = re.match(r"(\d+)分(\d+)秒", str(s))
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    m = re.match(r"(\d+)秒", str(s))
    return int(m.group(1)) if m else None

def dur_band(sec):
    if sec is None:
        return "未知"
    if sec <= 15:
        return "≤15秒"
    if sec <= 30:
        return "16-30秒"
    if sec <= 60:
        return "31-60秒"
    if sec <= 120:
        return "1-2分钟"
    return "2分钟以上"

band_gmv = collections.defaultdict(list)
band_n = collections.Counter()
for v in all_videos:
    b = dur_band(dur_sec(v.get("duration")))
    band_n[b] += 1
    g = P.tier_mid(v.get("gmv"))
    if g:
        band_gmv[b].append(g)
order = ["≤15秒", "16-30秒", "31-60秒", "1-2分钟", "2分钟以上"]
A["dur_band"] = [{"name": b, "n": band_n.get(b, 0),
                  "avg_gmv": round(sum(band_gmv.get(b, [0])) / len(band_gmv[b]), 0) if band_gmv.get(b) else 0}
                 for b in order if band_n.get(b)]

def fan_band(f):
    if not f:
        return "未知"
    s = str(f)
    if "w" in s:
        try:
            v = float(re.sub(r"[^\d.]", "", s))
        except Exception:
            return "未知"
        if v < 1:
            return "小于1万"
        if v < 10:
            return "1-10万"
        if v < 50:
            return "10-50万"
        return "50万以上"
    try:
        v = float(re.sub(r"[^\d.]", "", s))
    except Exception:
        return "未知"
    return "小于1万" if v < 10000 else "1-10万"

fb = collections.Counter()
fb_gpm = collections.defaultdict(list)
for v in all_videos:
    b = fan_band(v.get("fans"))
    fb[b] += 1
    g = P.tier_mid(v.get("gmv"))
    if g:
        fb_gpm[b].append(g)
A["fan_band"] = [{"name": b, "n": fb.get(b, 0),
                  "avg_gmv": round(sum(fb_gpm.get(b, [0])) / len(fb_gpm[b]), 0) if fb_gpm.get(b) else 0}
                 for b in ["小于1万", "1-10万", "10-50万", "50万以上", "未知"] if fb.get(b)]

HOOKS = [
    ("痛点直击", r"松垮|眼纹|眼袋|黑眼圈|泪沟|鱼尾纹|显老|干纹|细纹|暗沉|浮肿"),
    ("年龄锚定", r"\d+岁|同龄人|40不|30不|年纪|年轻"),
    ("效果承诺", r"抚纹|淡纹|紧致|提拉|嘭|淡化|消失|不见|改善|变"),
    ("权威背书", r"代言|推荐|官方|专研|院线|医美|博士|专利|认证|国货之光"),
    ("促销机制", r"拍一发|买一送|福利|补贴|限时|特惠|到手|礼盒|赠"),
    ("场景代入", r"熬夜|睡前|早上|上班|中秋|送礼|日常"),
]
hc = collections.Counter()
for v in all_videos:
    t = (v.get("desc") or "")[:60]
    hit = None
    for nm, pat in HOOKS:
        if re.search(pat, t):
            hit = nm
            break
    hc[hit or "其他"] += 1
A["hook_dist"] = [{"name": k, "n": v, "pct": pct(v, len(all_videos))}
                  for k, v in hc.most_common()]

# 话题标签
tags = collections.Counter()
for v in all_videos:
    for t in re.findall(r"#([^\s#]+)", v.get("desc") or ""):
        tags[t] += 1
A["tags_top"] = [{"name": k, "n": v} for k, v in tags.most_common(30)]

# TOP 视频（按销售额档）
def vkey(v):
    return (P.tier_mid(v.get("gmv")), P.tier_mid(v.get("volume")), P.num(v.get("play")) or 0)
A["top_videos"] = sorted(all_videos, key=vkey, reverse=True)[:15]

# 达人层级汇总（深度层 5 个商品的 TOP20 达人）
tal = []
for gid, d in D.items():
    for b in d["bloggers"]:
        b = dict(b); b["_gid"] = gid; tal.append(b)
tal.sort(key=lambda x: -(P.tier_mid(x.get("gmv"))))
A["top_talents"] = tal[:25]
A["n_talents"] = len(tal)

json.dump(A, open(os.path.join(DATA, "analysis.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

print("TOP30:", A["n_top"], " 池子:", A["n_pool"], " 视频:", A["n_videos"], " 达人:", A["n_talents"])
print("类目:", A["cate_dist"])
print("品牌集中度:", A["brand_concentration"])
print("品龄:", A["age_dist"])
print("价格:", A["price_stats"], " 佣金:", A["commission"], " 好评:", A["praise"])
print("渠道:", A["channel_mix"], " 带货方式:", A["selltype_mix"])
print("时长带:", A["dur_band"])
print("粉丝带:", A["fan_band"])
print("钩子:", A["hook_dist"])
print("词云分类:", A["wordcloud_cat"])
