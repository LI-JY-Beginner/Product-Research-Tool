# -*- coding: utf-8 -*-
"""
30_build_doc.py — 第 8 步：生成《小红书评论汇总》独立文档（md + html）

输入: data/raw_comments.json、data/filtered_log.json、data/overview.json
      raw/xhs_output/*.json（为了统计每篇「抓到多少条」）
输出: <outputDir>/<doc.title>_<日期>.md   留档 / 贴飞书
      <outputDir>/<doc.title>_<日期>.html 直接双击打开看

文档结构：
  一、采集与清洗概况（关键词数 / 笔记数 / 原始评论数 / 有效语料数 + 剔除规则分布）
  二、逐篇笔记 · 评论明细（每篇一张表，正文和评论分列标注来源）
  三、口径说明（怎么采的、什么算「有效」、有什么局限）

用法: python 30_build_doc.py [--cat cleanser]
"""
import html
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xcommon as X

RULE_DESC = {
    "R1": "营销文本（淘口令/加微/优惠券/外链等）",
    "R2": "空内容，或超短且无信息",
    "R3": "与本品类/品牌均无关（低相关）",
    "R4": "同文案跨笔记复刷（≥N 篇）",
    "R5": "同 IP 属地聚集",
    "R6": "零赞同同小时集中爆发",
    "R7": "营销号昵称特征",
    "R9": "不可改良项（物流/价格/客服）",
    "R10": "重复语料（同内容只计一条）",
    "R11": "纯话题标签串，无实质表述",
    "R12": "作者营销/购买引导",
}


def esc(s):
    return html.escape(str(s if s is not None else ""))


def main():
    opt, _ = X.cli("评论汇总文档生成")
    cfg = X.load_cfg(explicit=opt.config, cat=opt.cat)

    rc = X.jload(os.path.join(cfg._data, "raw_comments.json"), {})
    if not rc or not rc.get("comments"):
        raise SystemExit("[缺少输入] 请先跑 21_analyze.py（或 20_filter.py）")
    fl = X.jload(os.path.join(cfg._data, "filtered_log.json"), {})
    ov = X.jload(os.path.join(cfg._data, "overview.json"), {})

    meta = rc.get("noteMeta", {})
    kept = rc.get("comments", [])
    max_per_note = cfg.getpath("output.maxPerNote", 120)

    by_note = defaultdict(list)
    for c in kept:
        by_note[c["noteId"]].append(c)

    raw_cnt = {}
    if os.path.isdir(cfg._notes):
        for f in os.listdir(cfg._notes):
            if not f.endswith(".json"):
                continue
            d = X.jload(os.path.join(cfg._notes, f), {}) or {}
            raw_cnt[d.get("nid", "")] = len(d.get("comments") or [])

    notes = sorted(by_note.items(), key=lambda kv: -len(kv[1]))
    total_kept = len(kept)
    total_raw = sum(raw_cnt.values())
    n_desc = sum(1 for c in kept if c.get("isNoteDesc"))
    rule_cnt = Counter(x.get("filterRule") for x in fl.get("filtered", []))
    kws = cfg.get("keywords") or []
    title = cfg.doc.title
    path = cfg.doc.path
    stamp = cfg._stamp

    # ============================== Markdown ==============================
    md = []
    md.append(f"# {title}")
    md.append("")
    md.append(f"> 采集日期：{cfg._today}　｜　类目路径：{path}　｜　"
              f"数据源：小红书（Web 端搜索 + 笔记详情页公开可见内容）")
    md.append("")
    md.append("## 一、采集与清洗概况")
    md.append("")
    md.append("| 项目 | 数值 |")
    md.append("|---|---|")
    md.append(f"| 搜索关键词 | {len(kws)} 组 |")
    md.append(f"| 采集笔记 | {len(meta)} 篇 |")
    md.append(f"| 抓取评论（原始） | {total_raw} 条 |")
    md.append(f"| 清洗后有效语料 | **{total_kept} 条**（笔记正文 {n_desc} 条 · 真实评论 {total_kept - n_desc} 条） |")
    md.append(f"| 被剔除语料 | {fl.get('count', 0)} 条 |")
    md.append("")
    md.append("### 剔除规则分布（R1–R12）")
    md.append("")
    md.append("| 规则 | 含义 | 剔除条数 |")
    md.append("|---|---|---|")
    for r, n in rule_cnt.most_common():
        md.append(f"| {r} | {RULE_DESC.get(r, '')} | {n} |")
    md.append("")
    md.append("### 搜索关键词")
    md.append("")
    md.append("| # | 关键词 | 类型 |")
    md.append("|---|---|---|")
    for i, kv in enumerate(kws, 1):
        k, t = (kv + ["—"])[:2] if isinstance(kv, (list, tuple)) else (kv, "—")
        md.append(f"| {i} | {k} | {t} |")
    md.append("")
    md.append("> 说明：一条语料只归入一个最相关的桶；重复文案（R10）只计一条，避免频次虚高。")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 二、逐篇笔记 · 评论明细")
    md.append("")
    md.append(f"> 共 {len(notes)} 篇笔记，按有效评论数从多到少排列。「笔记正文」为作者原文，一并计入语料。")
    md.append("")
    for i, (nid, cs) in enumerate(notes, 1):
        m = meta.get(nid, {})
        md.append(f"### {i}. {m.get('title') or '(无标题)'}")
        md.append("")
        md.append(f"- 链接：{m.get('url', '')}")
        md.append(f"- 来源关键词：{m.get('keyword', '—')}　｜　类型：{m.get('tag', '—')}　｜　"
                  f"点赞：{m.get('likes') or '—'}　｜　该篇抓到评论 {raw_cnt.get(nid, 0)} 条，有效 {len(cs)} 条")
        if m.get("desc"):
            md.append(f"- 笔记正文摘要：{re.sub(r'\\s+', ' ', m['desc'])[:200]}…")
        md.append("")
        md.append("| # | 语料内容 | 来源 |")
        md.append("|---|---|---|")
        for j, c in enumerate(cs[:max_per_note], 1):
            t = re.sub(r"\s+", " ", c.get("content", "")).replace("|", "丨")
            src = "笔记正文" if c.get("isNoteDesc") else "评论"
            md.append(f"| {j} | {t[:220]} | {src} |")
        if len(cs) > max_per_note:
            md.append(f"| … | 其余 {len(cs) - max_per_note} 条见 HTML 版 / data/raw_comments.json | — |")
        md.append("")
    md.append("---")
    md.append("")
    md.append("## 三、口径说明")
    md.append("")
    md.append("- **采集方式**：小红书 Web 端按关键词搜索 → 打开笔记详情页 → 多次下滑并点击"
              "「展开更多回复」→ 抓 `#detail-title` / `#detail-desc` / `.parent-comment` 的可见文本。")
    md.append("- **仅采公开可见内容**，不做任何推测性补全；未取到的字段留空。")
    md.append(f"- **「有效」判定**：命中本类目品类词或品牌词，且未命中 R1–R12 任一剔除规则。")
    md.append("- **已知局限**：小红书只渲染部分评论，页面声明 1000 条的笔记实际通常只能读到几十到一百多条；"
              "`xsec_token` 过期后重刷旧链接几乎无新增，扩量需重新搜索。")
    md.append("- 本表为**原始语料留档**；需求 TOP5 / 痛点红线 / 决策权重的统计结果见 `data/` 下 json。")
    md.append("")
    mdp = os.path.join(cfg._out, f"{title}_{stamp}.md")
    open(mdp, "w", encoding="utf-8").write("\n".join(md))

    # ============================== HTML ==============================
    h = [f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{esc(title)}</title><style>
:root{{--bg:#f5f6fa;--card:#fff;--ink:#1e293b;--ink2:#64748b;--line:#e2e8f0;--pri:#4f46e5;--pri-soft:#eef2ff;--bad:#e11d48}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--bg);color:var(--ink);font:14px/1.65 "Microsoft YaHei","PingFang SC",system-ui,sans-serif;padding-bottom:40px}}
.wrap{{max-width:1080px;margin:0 auto;padding:0 24px}}
header{{background:var(--card);border-bottom:1px solid var(--line);padding:16px 0;position:sticky;top:0;z-index:10}}
header h1{{font-size:18px}}header .sub{{font-size:12px;color:var(--ink2);margin-top:3px}}
.sec{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 20px;margin:16px 0}}
.sec h2{{font-size:16px;margin-bottom:10px}}
table{{width:100%;border-collapse:collapse;font-size:13px;margin-top:6px}}
th,td{{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top}}
th{{background:#f8fafc;font-weight:600;font-size:12px}}
.note{{border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin-bottom:12px;background:#fff}}
.note h3{{font-size:14.5px;margin-bottom:6px}}
.note .mt{{font-size:12px;color:var(--ink2);margin-bottom:6px}}
.note .mt a{{color:var(--pri);text-decoration:none;word-break:break-all}}
.tag{{font-size:11px;background:#f1f5f9;color:var(--ink2);border-radius:3px;padding:1px 6px;margin-left:4px}}
.tag.d{{background:#fff1f2;color:var(--bad)}}
.desc{{font-size:12.5px;color:var(--ink2);background:#f8fafc;border-left:3px solid var(--pri);padding:6px 10px;margin:6px 0;border-radius:0 6px 6px 0}}
ul{{margin-left:18px;font-size:13px;color:var(--ink2)}}li{{margin:3px 0}}
</style></head><body><header><div class="wrap">
<h1>{esc(title)}</h1>
<div class="sub">类目路径：{esc(path)}　｜　{esc(cfg.doc.get('subtitle', ''))}　｜　采集日期：{cfg._today}</div>
</div></header><main class="wrap">"""]

    h.append('<div class="sec"><h2>一、采集与清洗概况</h2><table>')
    h.append("<tr><th>项目</th><th>数值</th></tr>")
    h.append(f"<tr><td>搜索关键词</td><td>{len(kws)} 组</td></tr>")
    h.append(f"<tr><td>采集笔记</td><td>{len(meta)} 篇</td></tr>")
    h.append(f"<tr><td>抓取评论（原始）</td><td>{total_raw} 条</td></tr>")
    h.append(f"<tr><td>清洗后有效语料</td><td><b>{total_kept}</b> 条（笔记正文 {n_desc} · 真实评论 {total_kept - n_desc}）</td></tr>")
    h.append(f"<tr><td>被剔除语料</td><td>{fl.get('count', 0)} 条</td></tr>")
    h.append("</table>")
    h.append('<h2 style="font-size:14px;margin-top:14px">剔除规则分布（R1–R12）</h2><table>')
    h.append("<tr><th>规则</th><th>含义</th><th>剔除条数</th></tr>")
    for r, n in rule_cnt.most_common():
        h.append(f"<tr><td>{esc(r)}</td><td>{esc(RULE_DESC.get(r, ''))}</td><td>{n}</td></tr>")
    h.append("</table></div>")

    h.append(f'<div class="sec"><h2>二、逐篇笔记 · 评论明细</h2>'
             f'<div style="font-size:12.5px;color:#64748b">共 {len(notes)} 篇笔记，按有效评论数从多到少排列</div></div>')
    for i, (nid, cs) in enumerate(notes, 1):
        m = meta.get(nid, {})
        h.append('<div class="note">')
        h.append(f'<h3>{i}. {esc(m.get("title") or "(无标题)")}</h3>')
        h.append(f'<div class="mt"><a href="{esc(m.get("url", ""))}" target="_blank">{esc(m.get("url", ""))}</a></div>')
        h.append(f'<div class="mt">来源关键词 <span class="tag">{esc(m.get("keyword", "—"))}</span>'
                 f'类型 <span class="tag">{esc(m.get("tag", "—"))}</span>'
                 f'点赞 <span class="tag">{esc(m.get("likes") or "—")}</span>'
                 f'抓到评论 <span class="tag">{raw_cnt.get(nid, 0)}</span>'
                 f'有效 <span class="tag d">{len(cs)}</span></div>')
        if m.get("desc"):
            h.append(f'<div class="desc">笔记正文摘要：{esc(re.sub(r"\\s+", " ", m["desc"])[:200])}…</div>')
        h.append("<table><tr><th style='width:38px'>#</th><th>语料内容</th><th style='width:78px'>来源</th></tr>")
        for j, c in enumerate(cs[:max_per_note], 1):
            t = esc(re.sub(r"\s+", " ", c.get("content", ""))[:240])
            src = '<span class="tag">正文</span>' if c.get("isNoteDesc") else '<span class="tag d">评论</span>'
            h.append(f"<tr><td>{j}</td><td>{t}</td><td>{src}</td></tr>")
        h.append("</table></div>")

    h.append('<div class="sec"><h2>三、口径说明</h2><ul>'
             "<li>采集方式：小红书 Web 端按关键词搜索 → 笔记详情页多次下滑 + 展开更多回复 → 抓可见文本。</li>"
             "<li>仅采公开可见内容，不做推测性补全；未取到的字段留空。</li>"
             "<li>「有效」判定：命中本类目品类词或品牌词，且未命中 R1–R12 任一剔除规则。</li>"
             "<li>已知局限：平台只渲染部分评论；xsec_token 过期后重刷旧链接几乎无新增，扩量需重新搜索。</li>"
             "<li>本页为原始语料留档；需求 TOP5 / 痛点红线 / 决策权重见 data/ 下 json。</li>"
             "</ul></div>")
    h.append("</main></body></html>")
    hp = os.path.join(cfg._out, f"{title}_{stamp}.html")
    open(hp, "w", encoding="utf-8").write("".join(h))

    print(f"[done] 笔记 {len(meta)} 篇｜原始评论 {total_raw} 条｜有效语料 {total_kept} 条", flush=True)
    print(f"  → {mdp}", flush=True)
    print(f"  → {hp}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
