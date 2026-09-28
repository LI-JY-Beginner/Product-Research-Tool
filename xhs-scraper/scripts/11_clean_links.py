# -*- coding: utf-8 -*-
"""
11_clean_links.py — 第 2 步：清洗候选标题、去重、剔噪音

输入: raw/xhs_links_*.json
输出: raw/xhs_candidates_clean.json

做四件事：
  1) 从搜索卡片的整块文本里剥出真正的标题（卡片文本 = 标题\n作者昵称\n3天前\n1.2万）
  2) 标题必须命中「品类词」才算相关（否则多半是作者昵称被当成了标题）
  3) 剔除噪音词命中的标题（关键词误命中别的品类）
  4) 按 nid 去重（同一条笔记可能被多个关键词搜到）

用法: python 11_clean_links.py [--cat cleanser]
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xcommon as X


def main():
    opt, _ = X.cli("候选标题清洗")
    cfg = X.load_cfg(explicit=opt.config, cat=opt.cat)

    files = sorted(glob.glob(os.path.join(cfg._raw, "xhs_links_*.json")))
    if not files:
        raise SystemExit(f"[缺少输入] {cfg._raw} 下没有 xhs_links_*.json，请先跑 10_collect_links.py")
    src = files[-1]
    links = X.jload(src, {}).get("links", [])
    print(f"输入：{src}（{len(links)} 条原始链接）", flush=True)

    words = list(cfg.getpath("category.words", []) or [])
    noise = list(cfg.getpath("category.noise", []) or [])
    if not words:
        # 没填品类词就只做去重，不卡相关性（方便新类目先跑通流程）
        hit_re = None
        print("  ⚠️ 配置里 category.words 是空的，本步跳过相关性校验（只做去重/剥标题）", flush=True)
    else:
        hit_re = re.compile("|".join(re.escape(w) for w in words))

    seen, out = set(), []
    for l in links:
        u = l.get("url", "")
        if X.is_author_profile(u):
            continue
        t = X.clean_title(l.get("title", ""), hit_re, noise)
        if not t:
            continue
        nid = X.note_id_from_url(u)
        if not nid or nid in seen:
            continue
        seen.add(nid)
        out.append({"title": t, "url": u, "nid": nid,
                    "likes": l.get("likes") or "", "tag": l.get("tag", ""),
                    "keyword": l.get("keyword", ""), "fetchDate": cfg._today})

    def lk(x):
        v = re.sub(r"[^\d.]", "", str(x["likes"] or "0"))
        try:
            return float(v or 0)
        except Exception:
            return 0.0

    out.sort(key=lambda x: -lk(x))
    X.jdump({"cleanedAt": cfg._today, "category": cfg.project.name,
             "count": len(out), "candidates": out},
            os.path.join(cfg._raw, "xhs_candidates_clean.json"))

    print(f"[done] 清洗后 {len(out)} 条候选（原始 {len(links)} 条）", flush=True)
    for i, c in enumerate(out[:20], 1):
        print(f"{i:>2}. [{c['tag']:<4}] {str(c['likes'] or '—'):<6} {c['title'][:50]}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
