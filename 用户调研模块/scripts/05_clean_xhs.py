# -*- coding: utf-8 -*-
"""
05_clean_xhs.py — 清洗小红书候选标题（剥离作者名/时间），去重，生成干净的确认清单
输入: raw/xhs_links_<日期>.json
输出: raw/xhs_candidates_clean.json + 候选笔记确认清单.md
"""
import json, os, re, glob, urllib.parse
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 自动定位：.../用户调研模块
WORKSPACE = os.path.dirname(BASE)
RAW = os.path.join(BASE, "raw")
TODAY = datetime.now().strftime("%Y-%m-%d")

TIME_PAT = re.compile(r"^(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}|\d+分钟前|\d+小时前|\d+天前|昨天|刚刚|\d+月\d+日)$")
NOISE = ["美甲", "甲油胶", "指甲", "带鱼", "护发", "发油", "精油皂", "卸妆", "洗发", "沐浴", "香水", "口红"]


def clean_title(raw):
    parts = [p.strip() for p in raw.split("\n") if p.strip()]
    keep = [p for p in parts if not TIME_PAT.match(p)]
    if not keep: return None
    t = keep[0]
    if len(t) < 6: return None                      # 过短=作者昵称，丢弃
    if not re.search(r"眼|油养|以油", t): return None   # 必须与眼部护理强相关（过滤纯昵称）
    return t


def main():
    fs = sorted(glob.glob(os.path.join(RAW, "xhs_links_*.json")))
    links = json.load(open(fs[-1], encoding="utf-8"))["links"]
    seen, out = set(), []
    for l in links:
        t = clean_title(l.get("title", ""))
        if not t: continue
        if any(n in t for n in NOISE): continue
        m = re.search(r"(?:explore|discovery/item)/([0-9a-f]{16,32})", l.get("url", ""))
        nid = m.group(1) if m else l.get("url", "")[:40]
        if nid in seen: continue
        seen.add(nid)
        out.append({"title": t, "url": l["url"], "nid": nid,
                    "likes": l.get("likes") or "", "tag": l.get("tag", ""),
                    "keyword": l.get("keyword", ""), "fetchDate": TODAY})
    out.sort(key=lambda x: -float(re.sub(r"[^\d.]", "", x["likes"] or "0") or 0))
    json.dump({"cleanedAt": TODAY, "count": len(out), "candidates": out},
              open(os.path.join(RAW, "xhs_candidates_clean.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"[done] 清洗后 {len(out)} 条候选（原始 {len(links)} 条）\n")

    # 生成确认清单（取前 36 条）
    top = out[:36]
    md = ["# 小红书候选笔记清单（请乾颖确认）", "",
          f"> 采集时间：{TODAY} ｜ 清洗后共 **{len(out)}** 条候选，下表取前 {len(top)} 条",
          "> 用途：挖掘用户**购买原因** → 高频需求 TOP5（产出③）",
          "> **请回复「删几号 / 加几号 / 全选」**，确认后我用 xhs-note-scraper 批量采正文+评论", "",
          "| 序号 | 标题 | 点赞 | 类型 | 来源关键词 |", "|---|---|---|---|---|"]
    for i, c in enumerate(top, 1):
        md.append(f"| {i} | {c['title'][:46]} | {c['likes'] or '—'} | {c['tag']} | {c['keyword']} |")
    md += ["", "## 自动剔除的噪音（关键词误命中，非眼部护理）", ""]
    noises = [clean_title(l.get("title", "")) for l in links]
    noises = [n for n in noises if n and any(x in n for x in NOISE)][:12]
    for n in noises: md.append(f"- {n[:44]}")
    md += ["", "> 💡 我建议优先保留：**吐槽/避雷类 + 空瓶/用了N天感受类**（真实反馈密度最高）；"
                "纯手法教程类（如「跟着XX学抹眼油手法」）对需求挖掘价值较低，可删"]
    fp = os.path.join(BASE, "候选笔记确认清单.md")
    open(fp, "w", encoding="utf-8").write("\n".join(md))
    print(f"[done] {fp}\n")
    print("=== 前 20 条候选 ===")
    for i, c in enumerate(top[:20], 1):
        print(f"{i:>2}. [{c['tag']:<4}] {c['likes'] or '—':<5} {c['title'][:44]}")


if __name__ == "__main__":
    main()
