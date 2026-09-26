# -*- coding: utf-8 -*-
"""
00_parse_feigua.py — 把 webbridge 抓到的飞瓜商品库行文本解析成结构化 JSON
输入: tmp/feigua_rows1.json, tmp/feigua_rows2.json ...
输出: 用户调研模块/raw/feigua_goods_眼油_<日期>.json
"""
import json, re, os, sys
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 自动定位：.../用户调研模块
WORKSPACE = os.path.dirname(BASE)
RAW = os.path.join(BASE, "raw")
os.makedirs(RAW, exist_ok=True)
TODAY = datetime.now().strftime("%Y-%m-%d")

# 品牌词表（用于聚合同一品牌下的多个 SPU）
BRANDS = ["白云山", "效妆", "雏菊的天空", "雏菊", "美雀琳", "凌博士", "美诗",
          "优时颜", "鄭明明", "郑明明", "苏彤氏", "林清轩", "阿芙", "蜜葳特",
          "Melvita", "赏容", "珀莱雅", "韩束", "自然堂", "薇诺娜", "至本", "逐本"]

# 噪音词（非眼油品类，需剔除）
NOISE = ["甲油胶", "美甲", "指甲油", "护手", "发油", "精油皂", "卸妆", "洗发", "身体乳"]


def parse_row(txt, gid):
    parts = [p.strip() for p in txt.split("|")]
    if len(parts) < 9:
        return None
    # 从末尾倒推：上架时间 / 带货达人 / 带货直播 / 带货视频 / 商品卡销售额 / 直播销售额 / 视频销售额 / 销售额
    tail = parts[-8:]
    title = parts[0]
    sales_raw = tail[0]
    # 数字规范化（用于排序）
    def num(s):
        s = s.replace("w", "0000").replace("+", "")
        m = re.match(r"^([\d.]+)-([\d.]+)(w?)$", s.strip())
        if m:
            a, b = float(m.group(1)), float(m.group(2))
            unit = 10000 if m.group(3) == "w" else 1
            return (a + b) / 2 * unit
        m2 = re.match(r"^([\d.]+)(w?)$", s.strip())
        if m2:
            v = float(m2.group(1))
            return v * 10000 if m2.group(2) == "w" else v
        return 0.0
    brand = ""
    for b in BRANDS:
        if b in title:
            brand = b
            break
    return {
        "title": title,
        "brand": brand or "其他/白牌",
        "gid": gid,
        "sales": sales_raw, "salesNum": num(sales_raw),
        "salesVideo": tail[1], "salesLive": tail[2], "salesCard": tail[3],
        "videoCount": tail[4], "liveCount": tail[5], "talentCount": tail[6],
        "listedAt": tail[7],
        "isNoise": any(n in title for n in NOISE),
        "fetchDate": TODAY,
        "source": "飞瓜数据·商品库（个护家清/关键词：眼油，近30天）",
    }


def main():
    rows = []
    for i in range(1, 6):
        p = os.path.join(BASE, "tmp", f"feigua_rows{i}.json")
        if not os.path.exists(p):
            continue
        doc = json.load(open(p, encoding="utf-8"))
        val = json.loads(doc["data"]["value"])
        for r in val.get("rows", []):
            pr = parse_row(r["txt"], r["gid"])
            if pr:
                rows.append(pr)
    # 去重（同 gid）
    seen, uniq = set(), []
    for r in rows:
        if r["gid"] in seen:
            continue
        seen.add(r["gid"])
        uniq.append(r)
    uniq.sort(key=lambda x: -x["salesNum"])

    out = {"fetchedAt": TODAY, "keyword": "眼油", "category": "个护家清",
           "period": "近30天", "count": len(uniq), "goods": uniq}
    fp = os.path.join(RAW, f"feigua_goods_眼油_{TODAY.replace('-','')}.json")
    json.dump(out, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"[done] 保存 {len(uniq)} 条 → {fp}\n")
    print("=== 按销售额降序（含噪音标记）===")
    for i, g in enumerate(uniq, 1):
        flag = "❌噪音" if g["isNoise"] else ""
        print(f"{i:>2}. [{g['sales']:<10}] 达人{g['talentCount']:>5} 视频{g['videoCount']:>5} 直播{g['liveCount']:>5} | {g['brand']:<8} | {g['title'][:44]} {flag}")

    # 品牌聚合（用于 TOP10 玩家）
    agg = {}
    for g in uniq:
        if g["isNoise"]:
            continue
        b = agg.setdefault(g["brand"], {"brand": g["brand"], "spus": [], "talentSum": 0, "videoSum": 0})
        b["spus"].append(g["title"][:40])
        try:
            b["talentSum"] += int(str(g["talentCount"]).replace(",", ""))
            b["videoSum"] += int(str(g["videoCount"]).replace(",", ""))
        except Exception:
            pass
    print("\n=== 品牌聚合（候选 TOP 玩家）===")
    for b in sorted(agg.values(), key=lambda x: -(x["talentSum"] + x["videoSum"])):
        print(f"  {b['brand']:<12} SPU数={len(b['spus']):<2} 达人合计={b['talentSum']:<6} 视频合计={b['videoSum']:<6}")

if __name__ == "__main__":
    main()
