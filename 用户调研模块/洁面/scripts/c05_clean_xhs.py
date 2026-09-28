# -*- coding: utf-8 -*-
"""
c05_clean_xhs.py — 清洗洁面候选标题（剥离作者名/时间）、去重、剔除非面部洁面噪音
输入: raw/xhs_links_<日期>.json
输出: raw/xhs_candidates_clean.json
"""
import json, os, re, glob
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw")
TODAY = datetime.now().strftime("%Y-%m-%d")

TIME_PAT = re.compile(r"^(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}|\d+分钟前|\d+小时前|\d+天前|昨天|刚刚|\d+月\d+日)$")
# 必须与「面部洁面」强相关
HIT = re.compile(r"洗面奶|洗面|洁面|洗颜|洗脸|氨基酸|皂基|洁面乳|洁面慕斯|洁面膏|洗面乳|"
                 r"泡沫洁面|洗干净|洗不干净|清洁力|洗后|洗完|护肤|脸")
NOISE = ["沐浴", "洗发", "沐浴露", "洗发水", "卸妆", "美甲", "洗衣机", "洗洁精",
         "宠物", "狗狗", "猫", "洗碗", "洗手液", "私处", "内衣", "鞋", "地毯", "洗衣液"]


def clean_title(raw):
    parts = [p.strip() for p in raw.split("\n") if p.strip()]
    keep = [p for p in parts if not TIME_PAT.match(p)]
    if not keep:
        return None
    # 取最长的一段做标题（作者昵称通常很短）
    t = max(keep, key=len)
    if len(t) < 6:
        return None
    if not HIT.search(t):
        return None
    return t


def main():
    fs = sorted(glob.glob(os.path.join(RAW, "xhs_links_*.json")))
    if not fs:
        print("[err] 没找到 xhs_links_*.json，先跑 c04")
        return
    links = json.load(open(fs[-1], encoding="utf-8"))["links"]
    seen, out = set(), []
    for l in links:
        u = l.get("url", "")
        if "/user/profile/" in u:        # 作者主页链接，不是笔记
            continue
        t = clean_title(l.get("title", ""))
        if not t:
            continue
        if any(n in t for n in NOISE):
            continue
        m = re.search(r"(?:search_result|explore|discovery/item)/([0-9a-f]{16,32})", u)
        nid = m.group(1) if m else ""
        if not nid or nid in seen:
            continue
        seen.add(nid)
        out.append({"title": t, "url": l["url"], "nid": nid,
                    "likes": l.get("likes") or "", "tag": l.get("tag", ""),
                    "keyword": l.get("keyword", ""), "fetchDate": TODAY})

    def lk(x):
        s = re.sub(r"[^\d.]", "", x["likes"] or "0")
        try:
            v = float(s or 0)
        except Exception:
            v = 0.0
        return v

    out.sort(key=lambda x: -lk(x))
    json.dump({"cleanedAt": TODAY, "count": len(out), "candidates": out},
              open(os.path.join(RAW, "xhs_candidates_clean.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"[done] 清洗后 {len(out)} 条候选（原始 {len(links)} 条）", flush=True)
    for i, c in enumerate(out[:30], 1):
        print(f"{i:>2}. [{c['tag']:<4}] {c['likes'] or '—':<6} {c['title'][:50]}", flush=True)


if __name__ == "__main__":
    main()
