# -*- coding: utf-8 -*-
"""
12_pick_notes.py — 第 3 步：从候选里挑「高挖掘价值」的笔记

打分规则（可配）：
  +2  标题命中 high 正则（避雷/空瓶/紧绷/假滑…）
  +2  标题命中品牌词（说明是具体产品的真实反馈，不是泛泛而谈）
  +1  来源 tag 属于 tagBonus（吐槽/测评/求安利 —— 真实反馈密度最高）
  剔除：标题命中 tutorial 正则（手法/教程类，对"为什么买"挖掘价值低）

输出: raw/xhs_picked.json   ← 下一步按这个清单去抓正文和评论

用法: python 12_pick_notes.py [--limit 40] [--cat cleanser]
      --limit 就是本次最多挑几篇（不传则用配置里的 defaultPick）
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xcommon as X


def main():
    opt, _ = X.cli("高价值笔记挑选")
    cfg = X.load_cfg(explicit=opt.config, cat=opt.cat)

    cand_p = os.path.join(cfg._raw, "xhs_candidates_clean.json")
    cands = X.jload(cand_p, {}).get("candidates", [])
    if not cands:
        raise SystemExit(f"[缺少输入] {cand_p} 为空，请先跑 11_clean_links.py")

    limit = opt.limit or cfg.getpath("pick.defaultPick", 40)
    tut = cfg.getpath("pick.tutorial")
    high = cfg.getpath("pick.high")
    tag_bonus = list(cfg.getpath("pick.tagBonus", []) or [])
    brands = list(cfg.getpath("category.brands", []) or [])
    tut_re = re.compile(tut) if tut else None
    high_re = re.compile(high) if high else None

    # 已经抓过的笔记不再重复挑（支持断点续跑）
    done = set()
    for f in glob.glob(os.path.join(cfg._notes, "*.json")):
        d = X.jload(f, {}) or {}
        if d.get("nid"):
            done.add(d["nid"])

    keep, drop = [], []
    for c in cands:
        t = c.get("title", "")
        if c.get("nid") in done:
            continue
        if tut_re and tut_re.search(t):
            drop.append(t)
            continue
        score = 0
        if high_re and high_re.search(t):
            score += 2
        bs = [b for b in brands if b.lower() in t.lower()]
        if bs:
            score += 2
        if c.get("tag") in tag_bonus:
            score += 1
        keep.append({**c, "score": score, "brands": bs})

    keep.sort(key=lambda x: (-x["score"], -len(x.get("title", ""))))
    picked = [k for k in keep if k["score"] > 0][:limit]

    X.jdump({"pickedAt": cfg._today, "category": cfg.project.name,
             "count": len(picked), "items": picked},
            os.path.join(cfg._raw, "xhs_picked.json"))

    print(f"候选 {len(cands)} 条｜已采 {len(done)} 条｜剔教程 {len(drop)} 条｜"
          f"本次新挑 {len(picked)} 条（上限 {limit}）", flush=True)
    if drop:
        print("\n=== 已剔除（教程/手法类）===", flush=True)
        for t in drop[:10]:
            print(f"  ✗ {t[:46]}", flush=True)
    print("\n=== 待采集（前 25）===", flush=True)
    for i, k in enumerate(picked[:25], 1):
        b = ("·" + ",".join(k["brands"])) if k["brands"] else ""
        print(f"{i:>2}. [分{k['score']}] {k['title'][:40]} {b}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
