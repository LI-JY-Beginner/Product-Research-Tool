# -*- coding: utf-8 -*-
"""
20_filter.py — 第 6 步：R1–R12 去水军过滤（本工具包的核心质量关）

输入: raw/xhs_output/*.json
输出: data/raw_comments.json   保留语料（含 noteMeta，供出文档用）
      data/filtered_log.json  被剔除语料 + 剔除原因（可审计，能逐条回溯）

规则一览（词表全部读配置，换类目只改 yaml）：
  R1  营销文本（淘口令/加微/优惠券/外链…）
  R2  空内容，或超短且不含任何品类/品牌词
  R3  与品类/品牌均无关（低相关）        ← 最主力的一条，靠 category.words 判定
  R4  同文案出现在 >=N 个不同笔记（模板复刷）
  R5  同一属地占比过高且条数够多（疑似水军聚集；无属地数据时不启用，避免误杀整篇）
  R6  同笔记同一小时零赞评论 >=N 条（集中爆发）
  R7  营销号昵称特征
  R9  不可改良项打标（物流/价格/客服 —— 保留但统计时剔除）
  R10 完全重复的语料（同内容只计一条）
  R11 纯话题标签串，剥掉 #标签 后没有实质表述
  R12 作者置顶/购买引导（去某宝、戳我、主页有…）

用法: python 20_filter.py [--cat cleanser]
"""
import hashlib
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xcommon as X


def anon_id(uid):
    """脱敏：不可逆 hash，审计时能对簇但不暴露账号"""
    return hashlib.md5(str(uid).encode("utf-8")).hexdigest()[:12]


def norm_time(t):
    if t is None:
        return None, None
    from datetime import datetime as _dt
    dt = None
    if isinstance(t, (int, float)):
        ts = t if t < 1e12 else t / 1000
        try:
            dt = _dt.fromtimestamp(ts)
        except Exception:
            dt = None
    else:
        s = str(t)
        if s.isdigit() and len(s) >= 10:
            try:
                dt = _dt.fromtimestamp(int(s[:10]))
            except Exception:
                dt = None
        if dt is None:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    dt = _dt.strptime(s[:len(fmt) + 2], fmt)
                    break
                except Exception:
                    continue
    if not dt:
        return str(t), None
    return dt.strftime("%Y-%m-%d %H:%M:%S"), dt.strftime("%Y-%m-%d")


def main():
    opt, _ = X.cli("语料去水军过滤")
    cfg = X.load_cfg(explicit=opt.config, cat=opt.cat)

    files = [os.path.join(cfg._notes, f) for f in sorted(os.listdir(cfg._notes))
             if f.endswith(".json")] if os.path.isdir(cfg._notes) else []
    if not files:
        raise SystemExit(f"[缺少输入] {cfg._notes} 下没有笔记 JSON，请先跑 13_scrape_notes.py")

    # ---- 词表 ----
    cat_words = list(cfg.getpath("category.words", []) or [])
    brand_words = list(cfg.getpath("category.brands", []) or [])
    f = cfg.getpath("filter", {}) or {}
    max_len = f.get("maxLen", 300)
    # ★ 笔记正文和评论用两个不同的截断长度，别合并成一个：
    #   正文很长，R4「同文案复刷」是按完整文本比对 noteId 集合的，
    #   正文若截得太短会和评论撞成同一串，把正文误判成复刷（会少掉十几条语料）。
    desc_len = f.get("descMaxLen", 400)
    r4_n = f.get("r4CrossNotes", 3)
    r5_rate = f.get("r5IpHitRate", 0.4)
    r5_min = f.get("r5MinCount", 5)
    r6_n = f.get("r6HourBurst", 8)
    R1 = re.compile(f.get("R1_营销文本", "$^"))
    R7 = re.compile(f.get("R7_营销昵称", "$^"))
    R9 = re.compile(f.get("R9_不可改良", "$^"))
    R12 = re.compile(f.get("R12_购买引导", "$^"))

    def hits_any(text, words):
        t = text.lower()
        return [w for w in words if str(w).lower() in t]

    # ---- 读入所有笔记，摊平成行 ----
    all_rows = []
    note_meta = {}
    for fp in files:
        doc = X.jload(fp, {}) or {}
        nid = doc.get("nid") or os.path.basename(fp).replace(".json", "")
        note_meta[nid] = {"title": doc.get("title", ""), "url": doc.get("url", ""),
                          "author": doc.get("author", ""), "keyword": doc.get("keyword", ""),
                          "tag": doc.get("tag", ""), "likes": doc.get("likes", ""),
                          "desc": doc.get("desc", "")}
        if doc.get("desc"):
            all_rows.append({"id": nid + "_desc", "nickname": doc.get("author", ""),
                             "userId": nid, "content": doc["desc"][:desc_len], "likeCount": 0,
                             "ipLocation": None, "createTime": doc.get("fetchDate"),
                             "_noteId": nid, "_isDesc": True})
        for c in (doc.get("comments") or []):
            for sub in (c.get("subComments") or []):
                sub["_parent"] = c.get("id")
            for c2 in [c] + (c.get("subComments") or []):
                c2["_noteId"] = nid
                all_rows.append(c2)

    print(f"输入 {len(files)} 篇笔记 → 摊平 {len(all_rows)} 条语料", flush=True)

    # ---- 预扫描：R4 复刷簇、R5 属地分布 ----
    note_sets = defaultdict(set)
    for r in all_rows:
        ct = (r.get("content") or "").strip()
        if ct:
            note_sets[ct].add(r["_noteId"])
    dup_texts = {t for t, notes in note_sets.items() if len(notes) >= r4_n}
    per_note_ip = defaultdict(Counter)
    for r in all_rows:
        per_note_ip[r["_noteId"]][r.get("ipLocation") or "未知"] += 1

    kept, filtered = [], []
    kept_texts = set()

    def filter_one(r):
        content = (r.get("content") or "").strip()
        nickname = r.get("nickname") or ""
        if not content:
            return False, "R2", "空内容"
        if R1.search(content):
            return False, "R1", "营销文本模式"
        cat_hit = hits_any(content, cat_words)
        brand_hit = hits_any(content, brand_words)
        if len(content) < 6 and not cat_hit and not brand_hit:
            return False, "R2", "超短且无信息"
        if not cat_hit and not brand_hit:
            return False, "R3", "与品类/品牌均无关（低相关）"
        if content in dup_texts:
            return False, "R4", "同文案复刷簇"
        if R7.search(nickname):
            return False, "R7", "营销号昵称特征"
        if "#" in content and len(re.sub(r"#[^\s#]+", "", content).strip()) < 10:
            return False, "R11", "纯话题标签串，无实质表述"
        if R12.search(content):
            return False, "R12", "作者营销/购买引导"
        if content in kept_texts:
            return False, "R10", "重复语料（同内容只计一条）"
        return True, None, None

    for r in all_rows:
        content = (r.get("content") or "").strip()[:max_len]
        nt, day = norm_time(r.get("createTime"))
        ok, rule, reason = filter_one({**r, "content": content})
        rec = {"id": r.get("id"), "noteId": r["_noteId"], "isSub": bool(r.get("_parent")),
               "isNoteDesc": bool(r.get("_isDesc")), "content": content,
               "likeCount": r.get("likeCount", 0), "createTime": nt, "date": day,
               "fetchDate": cfg._today, "ipLocation": r.get("ipLocation"),
               "userHash": anon_id(r.get("userId")),
               "r9NonFixable": bool(R9.search(content)),
               "categoryHits": hits_any(content, cat_words),
               "brandHits": hits_any(content, brand_words)}
        if ok:
            kept_texts.add(content)
            kept.append(rec)
        else:
            rec["filterRule"], rec["filterReason"] = rule, reason
            filtered.append(rec)

    # ---- R5：同笔记内属地聚集（无属地数据则跳过，避免误杀）----
    keep2 = []
    for r in kept:
        ip = r.get("ipLocation") or ""
        if not ip or ip == "未知":
            keep2.append(r)
            continue
        cnt = per_note_ip[r["noteId"]][ip]
        total = sum(per_note_ip[r["noteId"]].values()) or 1
        if cnt / total > r5_rate and cnt >= r5_min:
            r2 = dict(r)
            r2.update({"filterRule": "R5", "filterReason": f"同IP属地占比>{cnt * 100 // total}%（疑似水军聚集）"})
            filtered.append(r2)
            continue
        keep2.append(r)

    # ---- R6：同笔记同一小时零赞集中爆发 ----
    hour_key = defaultdict(list)
    for r in keep2:
        if r.get("createTime"):
            hour_key[(r["noteId"], r["createTime"][:13])].append(r)
    drop6 = set()
    for k, rows in hour_key.items():
        if len(rows) >= r6_n and all((x.get("likeCount") or 0) == 0 for x in rows):
            drop6.update(x["id"] for x in rows)
    if drop6:
        final = []
        for r in keep2:
            if r["id"] in drop6:
                r2 = dict(r)
                r2.update({"filterRule": "R6", "filterReason": "零赞同小时集中爆发"})
                filtered.append(r2)
            else:
                final.append(r)
        keep2 = final

    X.jdump({"fetchedAt": cfg._today, "category": cfg.project.name,
             "count": len(keep2), "noteMeta": note_meta, "comments": keep2},
            os.path.join(cfg._data, "raw_comments.json"))
    rule_counter = Counter(x.get("filterRule") for x in filtered)
    X.jdump({"fetchedAt": cfg._today, "count": len(filtered),
             "ruleSummary": dict(rule_counter), "filtered": filtered},
            os.path.join(cfg._data, "filtered_log.json"))

    print(f"\n[done] 输入 {len(all_rows)} 条 → 保留 {len(keep2)} 条，过滤 {len(filtered)} 条", flush=True)
    for k, v in sorted(rule_counter.items() or []):
        print(f"   {k}: {v} 条", flush=True)
    print(f"   → {os.path.join(cfg._data, 'raw_comments.json')}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
