# -*- coding: utf-8 -*-
"""
21_analyze.py — 第 7 步：统计需求 TOP / 痛点红线 / 词库 / 决策权重

输入: data/raw_comments.json（上一步的保留语料）
输出: data/needs_top5.json   高频需求 TOP5（带引文）
      data/redline.json      痛点红线（带引文）
      data/lexicon.json      词云 + 好评率 + 决策权重
      data/overview.json     语料概况（页面上「数据口径」那栏用）

两条统计纪律（决定数据可不可信）：
  1) 痛点桶走「否定识别」——「不紧绷」「不假滑」「没长脂肪粒」不会被算成痛点。
     识别逻辑：命中词所在子句里，前面 10 字内出现 不/没/无/未/别/… 就跳过；
     同时排除「担心/怕/会不会」这类假设语境（那是需求信号，不是已发生的痛点）。
  2) 一条语料只进一个桶（第一个命中的），避免同一条话被重复计数导致频次虚高。

用法: python 21_analyze.py [--cat cleanser]
"""
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xcommon as X

NEG_RE = re.compile(r"(?:不|没|无|未|别|不会|不太|没有|绝不|毫无|并不|也不|都不|不算|谈不上)"
                    r"[^，。！？；;.!?\s]{0,8}$")
HYP_RE = re.compile(r"(?:担心|害怕|怕|会不会|会不|可能|容易|据说|听说|万一|想着|就算|如果|假如|希望|期待)"
                    r"[^，。！？、；\s]{0,3}$")
DEG_RE = re.compile(r"[很太超挺特别非常有点比]{1,3}$")
CLAUSE_RE = re.compile(r"[，,。！？；;.!?\n]")


def find_positive(text, pat):
    """返回第一个「非否定语境」的命中。全部命中都是否定/假设/疑问 → 返回 None。"""
    bounds = [0] + [c.end() for c in CLAUSE_RE.finditer(text)]
    for m in re.finditer(pat, text):
        cs = max([b for b in bounds if b <= m.start()] or [0])
        pre = text[max(cs, m.start() - 10):m.start()]
        pre2 = DEG_RE.sub("", DEG_RE.sub("", pre))
        if NEG_RE.search(pre2):
            continue
        if HYP_RE.search(pre2):
            continue
        if re.match(r"[^？?。！]{0,4}[吗呢][？?]?", text[m.end():m.end() + 6]):
            continue
        return m
    return None


def excerpt(text, m, win=72):
    """以命中词为中心截引文，保证证据一定出现在展示出来的那句话里"""
    start = max(0, m.start() - 18)
    end = min(len(text), start + win)
    return ("…" if start > 0 else "") + text[start:end] + ("…" if end < len(text) else "")


def pick_quotes(quotes, limit=4):
    """引文排序：亲历口吻优先（我买/用了/回购），其次信息量长句优先"""
    seen, out = set(), []

    def score(q):
        t = q["text"]
        first = 2 if re.search(r"我(用|买|入手|洗|涂|抹|上脸|最近|之前)|用了|买了|入手|回购|空瓶", t) else 0
        return (-first, -len(t))

    for q in sorted(quotes, key=score):
        if "#" in q["text"]:
            continue
        key = q["text"][:24]
        if key in seen:
            continue
        seen.add(key)
        out.append(q)
        if len(out) >= limit:
            break
    return out


def main():
    opt, _ = X.cli("语料统计")
    cfg = X.load_cfg(explicit=opt.config, cat=opt.cat)

    rc_p = os.path.join(cfg._data, "raw_comments.json")
    rawc = X.jload(rc_p, {})
    if not rawc or not rawc.get("comments"):
        raise SystemExit(f"[缺少输入] {rc_p} 为空，请先跑 20_filter.py")

    note_meta = rawc.get("noteMeta", {})
    needs_cfg = [(n, p) for n, p in (cfg.getpath("buckets.needs", []) or [])]
    pains_cfg = [(n, p) for n, p in (cfg.getpath("buckets.pains", []) or [])]
    dec_map = dict(cfg.getpath("decisionMap", {}) or {})
    non_fixable = list(cfg.getpath("nonFixable", []) or [])
    top_needs = cfg.getpath("output.topNeeds", 5)
    top_pains = cfg.getpath("output.topPains", 8)

    if not needs_cfg or not pains_cfg:
        print("⚠️ 配置里 buckets.needs / buckets.pains 有空项，对应产出会为空。"
              "先跑通采集、看着语料再把桶补全即可。", flush=True)

    # 去重后的语料
    seen, corpus = set(), []
    for c in rawc["comments"]:
        t = X.norm(c.get("content", ""))
        if len(t) < 4 or t in seen:
            continue
        seen.add(t)
        corpus.append((t, c))
    print(f"语料 {len(corpus)} 条（去重后）", flush=True)

    def tally(buckets, neg_guard=False, skip_nonfixable=False):
        cnt = Counter()
        quotes = defaultdict(list)
        notes = defaultdict(set)
        for t, rec in corpus:
            if skip_nonfixable and any(n in t for n in non_fixable):
                continue
            for name, pat in buckets:
                try:
                    m = find_positive(t, pat) if neg_guard else re.search(pat, t)
                except re.error as e:
                    print(f"  ⚠️ 桶「{name}」正则写错了（{e}），本桶跳过", flush=True)
                    continue
                if m:
                    cnt[name] += 1
                    quotes[name].append({"text": excerpt(t, m), "source": "小红书",
                                         "noteId": rec.get("noteId", "")})
                    notes[name].add(rec.get("noteId", ""))
                    break
        for k in quotes:
            quotes[k] = pick_quotes(quotes[k])
        return cnt, quotes, notes

    nc, nq, nn = tally(needs_cfg)
    pc, pq, pn = tally(pains_cfg, neg_guard=True, skip_nonfixable=True)

    def mk(cnt, quotes, notes, topn):
        return [{"name": k, "count": v, "fgCount": 0, "xhsCount": v, "brandCount": 0,
                 "brands": [], "noteCount": len(notes.get(k, set())), "quotes": quotes[k]}
                for k, v in cnt.most_common(topn)]

    sources = [{"name": "小红书",
                "detail": f"{len(cfg.get('keywords') or [])} 组关键词搜索 → 笔记正文 + 评论，已过 R1–R12 水军过滤"}]
    needs = {"generatedAt": cfg._today, "items": mk(nc, nq, nn, top_needs),
             "corpus": {"total": len(corpus), "feigua": 0, "xhs": len(corpus)},
             "sources": sources}
    redline = {"generatedAt": cfg._today, "items": mk(pc, pq, pn, top_pains),
               "source": f"小红书笔记正文与评论（{cfg.project.name}）；已剔除物流/客服/价格等不可改良项"}

    # ---- 词云 / 好评率 ----
    gw, bw = Counter(), Counter()
    pain_ids = set()
    for t, rec in corpus:
        hit = None
        for _, pat in pains_cfg:
            try:
                hit = find_positive(t, pat)
            except re.error:
                hit = None
            if hit:
                break
        if hit:
            bw[hit.group(0)] += 1
            pain_ids.add(rec.get("id"))
    for t, rec in corpus:
        if rec.get("id") in pain_ids:
            continue
        for _, pat in needs_cfg:
            try:
                m = re.search(pat, t)
            except re.error:
                m = None
            if m:
                gw[m.group(0)] += 1
                break

    total = len(corpus) or 1
    good = total - len(pain_ids)
    good_rate = round(good / total * 100, 1)
    cloud = ([{"word": w, "count": n, "polarity": "good"} for w, n in gw.most_common(30)] +
             [{"word": w, "count": n, "polarity": "bad"} for w, n in bw.most_common(30)])
    cloud = sorted(cloud, key=lambda x: -x["count"])[:56]

    # ---- 决策权重 ----
    dw = Counter()
    for name, crit in dec_map.items():
        dw[crit] += nc.get(name, 0)
    dsum = sum(dw.values()) or 1
    decision = [{"criterion": k, "weight": v, "pct": round(v / dsum * 100, 1)}
                for k, v in dw.most_common()]
    if not decision:                       # 没配 decisionMap 就用需求桶兜底
        decision = [{"criterion": k, "weight": v, "pct": round(v / (sum(nc.values()) or 1) * 100, 1)}
                    for k, v in nc.most_common(top_needs)]

    lexicon = {"generatedAt": cfg._today,
               "sentimentDist": [{"name": "好评", "value": good},
                                 {"name": "差评", "value": len(pain_ids)}],
               "cloud": cloud,
               "goodWords": [{"word": w, "count": n} for w, n in gw.most_common(15)],
               "badWords": [{"word": w, "count": n} for w, n in bw.most_common(15)],
               "decision": decision,
               "source": "小红书笔记与评论（好评=未命中痛点桶；差评=命中痛点桶且非否定语境）",
               "quick": {"goodTop": [x["word"] for x in sorted(cloud, key=lambda x: -x["count"])
                                     if x["polarity"] == "good"][:5],
                         "badTop": [x["word"] for x in sorted(cloud, key=lambda x: -x["count"])
                                    if x["polarity"] == "bad"][:5],
                         "goodRate": good_rate, "decision": decision}}

    overview = {"corpusTotal": len(corpus), "corpusFeigua": 0, "corpusXhs": len(corpus),
                "noteCount": len(note_meta), "category": cfg.project.name, "sources": sources}

    X.jdump(needs, os.path.join(cfg._data, "needs_top5.json"))
    X.jdump(redline, os.path.join(cfg._data, "redline.json"))
    X.jdump(lexicon, os.path.join(cfg._data, "lexicon.json"))
    X.jdump(overview, os.path.join(cfg._data, "overview.json"))

    print(f"\n=== 高频需求 TOP{top_needs} ===", flush=True)
    for i, x in enumerate(needs["items"], 1):
        print(f"{i}. {x['count']:>4}  {x['name']}", flush=True)
    print(f"\n=== 痛点红线 ===", flush=True)
    for i, x in enumerate(redline["items"], 1):
        print(f"{i}. {x['count']:>4}  {x['name']}", flush=True)
    print(f"\n=== 决策权重 ===", flush=True)
    for x in decision:
        print(f"   {x['criterion']}  {x['pct']}%", flush=True)
    print(f"\n好评率 {good_rate}%（好评 {good} / 差评 {len(pain_ids)}）", flush=True)
    print(f"→ {cfg._data}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
