# -*- coding: utf-8 -*-
"""
08_pick_highvalue.py — 从候选中剔除「手法教程类」，挑选高挖掘价值笔记待采集
输出: raw/xhs_picked.json（待采集清单）+ 打印分类结果
"""
import json, os, re, glob

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 自动定位：.../用户调研模块
WORKSPACE = os.path.dirname(BASE)
RAW = os.path.join(BASE, "raw")

# 教程/手法类 → 排除（对"购买原因"挖掘价值低）
TUTORIAL = re.compile(
    r"手法|教程|跟练|小课堂|正确使用方法|怎么用|按摩|穴位|步骤|手法版|"
    r"秘诀|撑起|撑起来|榨干|轮廓紧致术|眼保健操|教学|示范|演示|手法教学")
# 高价值信号
HIGH = re.compile(
    r"避雷|避坑|别买|千万别|后悔|智商税|翻车|吐槽|踩雷|没用|无效|难用|差评|"
    r"空瓶|用完|用了|感受|体验|实测|测评|对比|真实|亲测|回购|"
    r"到底谁在用|值得买|推荐|求推荐|哪个好|用哪个|怎么样|可以吗|"
    r"过敏|脂肪粒|辣眼|糊眼|油腻|搓泥|卡粉|长粒|刺激|痒|味道|难闻")
# 品牌出现（竞品对标价值）
BRANDS = ["白云山", "效妆", "雏菊的天空", "雏菊", "美雀琳", "凌博士", "美诗", "优时颜",
          "郑明明", "鄭明明", "苏彤氏", "福来", "Freiol", "阿芙", "林清轩", "蜜葳特",
          "珀莱雅", "欧莱雅", "雅诗兰黛", "丸美", "瑷珂缦", "馥郁满铺", "兰蔻"]


def main():
    cands = json.load(open(os.path.join(RAW, "xhs_candidates_clean.json"), encoding="utf-8"))["candidates"]
    done = set()
    for f in glob.glob(os.path.join(RAW, "xhs_output", "*.json")):
        d = json.load(open(f, encoding="utf-8"))
        done.add(d.get("nid", ""))

    keep, drop = [], []
    for c in cands:
        t = c["title"]
        nid = re.search(r"/(?:search_result|explore|discovery/item)/([0-9a-f]{20,32})", c["url"])
        nid = nid.group(1) if nid else ""
        if nid in done:
            continue
        if TUTORIAL.search(t):
            drop.append((t, "教程/手法类")); continue
        score = 0
        if HIGH.search(t): score += 2
        if any(b in t for b in BRANDS): score += 2
        if c.get("tag") in ("吐槽", "测评", "求安利"): score += 1
        keep.append({**c, "nid": nid, "score": score,
                     "brands": [b for b in BRANDS if b in t]})
    keep.sort(key=lambda x: -x["score"])
    picked = [k for k in keep if k["score"] > 0][:30]

    json.dump({"pickedAt": "2026-09-24", "count": len(picked), "items": picked},
              open(os.path.join(RAW, "xhs_picked.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"候选 {len(cands)} 条，已采 {len(done)} 条，剔除教程类 {len(drop)} 条，新选高价值 {len(picked)} 条\n")
    print("=== 已剔除（教程/手法类）===")
    for t, why in drop[:12]: print(f"  ✗ {t[:44]}")
    print("\n=== 待采集高价值（前 20）===")
    for i, k in enumerate(picked[:20], 1):
        b = ("·" + ",".join(k["brands"])) if k["brands"] else ""
        print(f"{i:>2}. [分{k['score']}] {k['title'][:40]} {b}")


if __name__ == "__main__":
    main()
