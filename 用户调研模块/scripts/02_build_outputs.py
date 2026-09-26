# -*- coding: utf-8 -*-
"""
02_build_outputs.py — 把飞瓜原始数据加工成「用户调研模块」的 5 个产出
输入: raw/feigua_goods_眼油_*.json（商品库列表）、raw/feigua_details_all.json（详情页画像+评价）
输出: data/{top10,audience,needs_top5,redline,lexicon,meta,overview}.json
"""
import json, os, re, glob
from collections import Counter, defaultdict
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 自动定位：.../用户调研模块
WORKSPACE = os.path.dirname(BASE)
RAW = os.path.join(BASE, "raw")
DATA = os.path.join(BASE, "data")
os.makedirs(DATA, exist_ok=True)
TODAY = datetime.now().strftime("%Y-%m-%d")

# 2026-09-25 用户要求：所有品牌一视同仁，不做「自家 vs 竞品」区分，置空即全品类平等对待
SELF_BRANDS = []

# ---------- 词性归类 ----------
NEED_WORDS = {  # 需求类（用户想要什么）
    "功效": ["淡纹", "抗皱", "紧致", "去眼袋", "黑眼圈", "细纹", "眼纹", "泪沟", "改善", "补水", "保湿", "抗老"],
    "质地体验": ["滋润", "吸收", "清爽", "不油腻", "水润", "轻薄", "好推开", "润滑", "冰冰凉凉", "清凉", "温和"],
    "设计便捷": ["滚珠", "方便", "便携", "小巧", "使用便捷", "按摩", "外观设计", "包装"],
    "价格": ["性价比", "实惠", "便宜", "价格", "划算", "不贵", "物超所值", "价廉"],
    "成分安全": ["成分", "安全", "温和", "敏感肌", "不过敏", "无刺激"],
}
PAIN_WORDS = {  # 痛点类（可改良的红线）
    "无效": ["没效果", "没有效果", "无效", "没用", "不起作用", "骗人", "智商税", "没一点效果"],
    "油腻闷": ["油腻", "油", "黏腻", "粘腻", "闷", "脂肪粒", "厚重"],
    "刺激过敏": ["辣眼睛", "辣眼", "刺激", "过敏", "红肿", "肿", "刺痛", "不适", "刺鼻"],
    "使用体验差": ["推不开", "搓泥", "卡粉", "难吸收", "假滑", "紧绷", "干"],
    "气味": ["难闻", "异味", "味道", "刺鼻", "香精"],
}
NON_FIXABLE = ["物流", "快递", "发货", "太贵", "价格贵", "客服", "服务态度", "退货", "退款", "退不了"]

def load():
    goods_f = sorted(glob.glob(os.path.join(RAW, "feigua_goods_眼油_*.json")))
    goods = json.load(open(goods_f[-1], encoding="utf-8"))["goods"] if goods_f else []
    dp = os.path.join(RAW, "feigua_details_all.json")
    details = json.load(open(dp, encoding="utf-8"))["details"] if os.path.exists(dp) else {}
    return goods, details

def is_self(brand):
    return any(b in (brand or "") for b in SELF_BRANDS)

# ========== 产出1：TOP10 玩家 ==========
def build_top10(goods):
    agg = {}
    for g in goods:
        if g.get("isNoise"): continue
        b = g["brand"]
        a = agg.setdefault(b, {"brand": b, "spus": [], "talent": 0, "video": 0, "live": 0,
                               "salesTier": set(), "isSelf": is_self(b), "gids": []})
        a["spus"].append({"title": g["title"][:46], "gid": g["gid"], "sales": g["sales"],
                          "talent": g["talentCount"], "video": g["videoCount"], "live": g["liveCount"]})
        a["gids"].append(g["gid"])
        try: a["talent"] += int(str(g["talentCount"]).replace(",", ""))
        except Exception: pass
        try: a["video"] += int(str(g["videoCount"]).replace(",", ""))
        except Exception: pass
        try: a["live"] += int(str(g["liveCount"]).replace(",", ""))
        except Exception: pass
        a["salesTier"].add(g["sales"])
    items = []
    for b, a in agg.items():
        score = a["talent"] * 0.4 + a["video"] * 0.35 + a["live"] * 0.25
        items.append({
            "brand": b, "isSelf": a["isSelf"], "spuCount": len(a["spus"]),
            "talent": a["talent"], "video": a["video"], "live": a["live"],
            "salesTier": sorted(a["salesTier"], key=lambda s: -len(s))[:1] or ["—"],
            "score": round(score, 1), "spus": a["spus"][:4],
            "reason": f"达人{a['talent']} + 视频{a['video']} + 直播{a['live']}",
            "source": "飞瓜数据·商品库（个护家清/关键词：眼油，近30天）",
            "fetchDate": TODAY,
            "category": {"L1": "个护家清", "L2": "眼部护理", "L3": "眼部精华"},
        })
    items.sort(key=lambda x: -x["score"])
    excluded = [{"name": g["title"][:40], "reason": "品类噪音：非眼部护理产品（关键词误命中）"}
                for g in goods if g.get("isNoise")]
    return {"fetchDate": TODAY, "items": items[:10], "excluded": excluded,
            "criteria": "飞书工作流 3.1：月销>500万 或 近3月增速>50%；排除国际大牌、9.9福利款（飞瓜区间显示，按100w+档判定）"}

# ========== 产出2：受众画像 ==========
def build_audience(details, goods=None):
    # gid -> 商品库列表里的品牌名（用于回填详情页缺失的品牌）
    gid2brand = {}
    for g in (goods or []):
        gid2brand[g["gid"]] = g["brand"]
    rows = []
    for gid, d in details.items():
        a, inf = d.get("audience", {}), d.get("info", {})
        if not a.get("summary"): continue
        fem = next((x["pct"] for x in a.get("gender", []) if x["gender"] == "女性"), None)
        brand = inf.get("brand") or gid2brand.get(gid) or "—"
        rows.append({
            "brand": brand, "title": inf.get("title", "")[:40],
            "isSelf": is_self(inf.get("brand", "")),
            "summary": a.get("summary", ""), "femalePct": fem,
            "ageRange": (a.get("age") or {}).get("range"), "agePct": (a.get("age") or {}).get("pct"),
            "regionTop3": [x["region"] for x in a.get("region", [])[:3]],
            "regions": a.get("region", []), "gender": a.get("gender", []),
            "prefer": a.get("prefer", ""),
            "source": f"飞瓜商品详情页·受众画像（gid={gid[:12]}）", "fetchDate": d.get("fetchDate", TODAY),
        })
    rows.sort(key=lambda x: -(x["femalePct"] or 0))
    # 汇总洞察（全品类口径，不区分自家/竞品）
    ins = []
    fem = [r["femalePct"] for r in rows if r["femalePct"] is not None]
    if fem:
        ins.append({"text": f"品类女性占比均值 {sum(fem)/len(fem):.1f}%（区间 {min(fem):.1f}% ~ {max(fem):.1f}%，{len(fem)} 个商品）",
                    "evidence": "飞瓜受众画像·性别分布（各商品详情页）"})
    ages = [r["ageRange"] for r in rows if r["ageRange"]]
    if ages:
        top = "、".join(f"{k}（{v} 个商品）" for k, v in Counter(ages).most_common(3))
        ins.append({"text": f"主力人群年龄段分布：{top}",
                    "evidence": "飞瓜受众画像·年龄分布（各商品详情页）"})
    regs = Counter()
    for r in rows:
        for x in (r.get("regions") or [])[:5]:
            regs[x["region"]] += 1
    if regs:
        ins.append({"text": "高频地域 TOP5：" + "、".join(f"{k}（{v} 个商品）" for k, v in regs.most_common(5)),
                    "evidence": "飞瓜受众画像·地域分布（各商品详情页）"})
    return {"fetchDate": TODAY, "rows": rows, "insights": ins,
            "source": "飞瓜商品详情页 → 受众画像 Tab（消费者画像/视频观众画像）"}

# ========== 产出3/4/5：需求、红线、话语体系 ==========
def analyze_reviews(details):
    all_pos, all_neg, wc_pool, senti_pool = [], [], Counter(), []
    per_brand = {}
    for gid, d in details.items():
        brand = (d.get("info", {}) or {}).get("brand") or "—"
        revs = d.get("reviews", []) or []
        if isinstance(revs, dict):            # 兼容 v1 格式（dict 内含 reviews）
            revs = revs.get("reviews", [])
        negs = d.get("negativeReviews", []) or []
        s = d.get("sentiment", {}) or {}
        if not s and isinstance(d.get("reviews"), dict):
            s = d["reviews"].get("sentiment", {}) or {}
        if s: senti_pool.append({"brand": brand, "isSelf": is_self(brand), **s})
        wc_src = d.get("wordcloud", []) or []
        if not wc_src and isinstance(d.get("reviews"), dict):
            wc_src = d["reviews"].get("wordcloud", []) or []
        for w in wc_src:
            wc_pool[w["word"]] += 1
        for r in negs:
            all_neg.append({"brand": brand, "isSelf": is_self(brand), **r})
        for r in revs:
            all_pos.append({"brand": brand, "isSelf": is_self(brand), **r})
        per_brand[brand] = {"reviewCount": (d.get("info", {}) or {}).get("reviewCount"),
                            "goodRate": (d.get("info", {}) or {}).get("goodRate"),
                            "sentiment": s, "negSample": [x["content"] for x in negs[:3]]}
    return all_pos, all_neg, wc_pool, senti_pool, per_brand

def bucket(text, mapping):
    for k, ws in mapping.items():
        for w in ws:
            if w in text: return k, w
    return None, None

def build_needs(all_pos, wc_pool):
    """高频需求 TOP5：从好评评价+词云提炼购买原因"""
    cnt = Counter(); quotes = defaultdict(list)
    for r in all_pos:
        b, w = bucket(r["content"], NEED_WORDS)
        if b:
            cnt[b] += 1
            if len(quotes[b]) < 3:
                quotes[b].append({"text": r["content"][:70], "source": f"{r['brand']}·{r['date']}", "likes": 0})
    items = [{"name": k, "count": v, "quotes": quotes[k],
              "words": [x for x in list(wc_pool)[:0]]} for k, v in cnt.most_common(5)]
    return {"generatedAt": TODAY, "items": items,
            "source": "飞瓜商品详情页·商品评价（好评+全部评价原文）+ 商品舆情词云"}

def build_redline(all_neg):
    """产品红线：从差评提炼可改良痛点"""
    cnt = Counter(); quotes = defaultdict(list); brands = defaultdict(set)
    for r in all_neg:
        txt = r["content"]
        if any(n in txt for n in NON_FIXABLE): continue   # 剔除不可改良
        b, w = bucket(txt, PAIN_WORDS)
        if not b: continue
        cnt[b] += 1; brands[b].add(r["brand"])
        if len(quotes[b]) < 3:
            quotes[b].append({"text": txt[:70], "source": f"{r['brand']}·{r['date']}", "likes": 0})
    items = [{"name": k, "count": v, "brandCount": len(brands[k]), "brands": sorted(brands[k]),
              "quotes": quotes[k]} for k, v in cnt.most_common(5)
             if len(brands[k]) >= 1]
    return {"generatedAt": TODAY, "items": items,
            "source": "飞瓜商品详情页·商品评价 → 差评筛选（已剔除物流/价格等不可改良项）"}

def build_lexicon(all_pos, all_neg, wc_pool, senti_pool):
    """用户话语体系：评价类型占比 + 好评/差评词云 + 决策排序"""
    # 评价类型占比（用有情感统计的品牌）
    dist = Counter()
    for s in senti_pool:
        def n(v):
            v = str(v or "0")
            return float(v.replace("w", "")) * 10000 if "w" in v else (float(v) if v.replace(".", "").isdigit() else 0)
        dist["好评"] += n(s.get("好评")); dist["中评"] += n(s.get("中评")); dist["差评"] += n(s.get("差评"))
    good_w, bad_w = Counter(), Counter()
    for r in all_pos:
        for k, ws in NEED_WORDS.items():
            for w in ws:
                if w in r["content"]: good_w[w] += 1
    for r in all_neg:
        for k, ws in PAIN_WORDS.items():
            for w in ws:
                if w in r["content"]: bad_w[w] += 1
    def to_cloud(c, pol):
        out = [{"word": w, "count": n, "polarity": pol} for w, n in c.most_common(30)]
        for x in out: x["sensitive"] = x["word"] in ("淡纹", "抗皱", "祛皱", "去眼袋")
        return out
    # 决策排序：按词云总频次推导用户评判标准权重
    decision = []
    for k, ws in list(NEED_WORDS.items()):
        s = sum(good_w.get(w, 0) for w in ws)
        if s: decision.append({"criterion": k, "weight": s})
    decision.sort(key=lambda x: -x["weight"])
    total = sum(d["weight"] for d in decision) or 1
    for d in decision: d["pct"] = round(d["weight"] / total * 100, 1)
    return {"generatedAt": TODAY,
            "sentimentDist": [{"name": k, "value": int(v)} for k, v in dist.items() if v],
            "cloud": to_cloud(good_w, "good") + to_cloud(bad_w, "bad"),
            "goodWords": [{"word": w, "count": n} for w, n in good_w.most_common(15)],
            "badWords": [{"word": w, "count": n} for w, n in bad_w.most_common(15)],
            "decision": decision,
            "source": "飞瓜商品评价（评价情感分布 + 舆情词云 + 好评/差评原文）"}

def main():
    goods, details = load()
    print(f"商品库 {len(goods)} 条 / 详情 {len(details)} 个")
    out = {}
    out["top10"] = build_top10(goods)
    out["audience"] = build_audience(details, goods)
    all_pos, all_neg, wc, senti, per_brand = analyze_reviews(details)
    out["needs_top5"] = build_needs(all_pos, wc)
    out["redline"] = build_redline(all_neg)
    out["lexicon"] = build_lexicon(all_pos, all_neg, wc, senti)
    out["overview"] = {
        "productCount": len([g for g in goods if not g.get("isNoise")]),
        "brandCount": len({g["brand"] for g in goods if not g.get("isNoise")}),
        "detailCount": len(details),
        "reviewCount": len(all_pos) + len(all_neg),
        "negCount": len(all_neg),
        "filteredCount": len([g for g in goods if g.get("isNoise")]),
        "dataRange": {"start": "2026-08-25", "end": TODAY},  # 近30天
    }
    # meta：保留历史 updateLog 与既有 loginStatus，避免每日重跑覆盖掉归档记录
    meta_path = os.path.join(DATA, "meta.json")
    prev = {}
    if os.path.exists(meta_path):
        try:
            prev = json.load(open(meta_path, encoding="utf-8"))
        except Exception:
            prev = {}
    log = [x for x in prev.get("updateLog", []) if x.get("date") != TODAY]
    log.append({"date": TODAY, "note": "飞瓜商品库+详情页产出重建（TOP10/画像/评价）"})
    out["meta"] = {"isPlaceholder": False, "dataRange": out["overview"]["dataRange"],
                   "lastUpdated": datetime.now().strftime("%Y-%m-%d %H:%M"),
                   "loginStatus": prev.get("loginStatus", {"xhs": "unknown", "feigua": "normal"}),
                   "updateLog": log}
    for k, v in out.items():
        with open(os.path.join(DATA, k + ".json"), "w", encoding="utf-8") as f:
            json.dump(v, f, ensure_ascii=False, indent=1)
        print(f"[done] data/{k}.json")
    print("\n=== 需求 TOP5 ===")
    for i in out["needs_top5"]["items"]: print(f"  {i['count']:>3} {i['name']}")
    print("=== 产品红线 ===")
    for i in out["redline"]["items"]: print(f"  {i['count']:>3} {i['name']}（{i['brandCount']}个品牌）")
    print("=== 决策排序 ===")
    for d in out["lexicon"]["decision"]: print(f"  {d['pct']:>5}% {d['criterion']}")

if __name__ == "__main__":
    main()
