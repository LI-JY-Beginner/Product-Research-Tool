# -*- coding: utf-8 -*-
"""
c09_build_xhs_doc.py — 生成《洗面奶 · 小红书评论汇总》独立文档（md + html）
输入: data/raw_comments.json（保留语料，含 noteMeta）、data/filtered_log.json
输出: 洁面/洗面奶_小红书评论汇总_<日期>.md / .html
"""
import json, os, re, html
from collections import Counter, defaultdict
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
RAWX = os.path.join(BASE, "raw", "xhs_output")
TODAY = datetime.now().strftime("%Y%m%d")
TODAY_D = datetime.now().strftime("%Y-%m-%d")

RULE_DESC = {
    "R1": "营销文本（淘口令/加微/优惠券/外链等）",
    "R2": "空内容或超短且无信息",
    "R3": "与洁面品类/品牌均无关（低相关）",
    "R4": "同文案跨笔记复刷（≥3 篇）",
    "R5": "同 IP 属地聚集",
    "R6": "零赞同同小时集中爆发",
    "R7": "营销号昵称特征",
    "R9": "不可改良项（物流/价格/客服）",
    "R10": "重复语料（同内容只计一条）",
    "R11": "纯话题标签串，无实质表述",
    "R12": "作者营销/购买引导",
}


def esc(s):
    return html.escape(str(s or ""))


def main():
    rc = json.load(open(os.path.join(DATA, "raw_comments.json"), encoding="utf-8"))
    fl = {}
    fp2 = os.path.join(DATA, "filtered_log.json")
    if os.path.exists(fp2):
        fl = json.load(open(fp2, encoding="utf-8"))
    meta = rc.get("noteMeta", {})
    kept = rc.get("comments", [])

    by_note = defaultdict(list)
    for c in kept:
        by_note[c["noteId"]].append(c)

    # 每篇笔记原始抓到的评论数
    raw_cnt = {}
    for f in os.listdir(RAWX):
        if not f.endswith(".json"):
            continue
        try:
            d = json.load(open(os.path.join(RAWX, f), encoding="utf-8"))
            raw_cnt[d.get("nid", "")] = len(d.get("comments", []) or [])
        except Exception:
            pass

    notes = sorted(by_note.items(), key=lambda kv: -len(kv[1]))
    total_kept = len(kept)
    total_raw = sum(raw_cnt.values())
    rule_cnt = Counter(x.get("filterRule") for x in fl.get("filtered", []))

    # ---------- Markdown ----------
    md = []
    md.append("# 洗面奶 · 小红书评论汇总")
    md.append("")
    md.append(f"> 采集日期：{TODAY_D}　｜　类目路径：个护家清 / 面部护理 / 洁面（洗面奶）　｜　"
              f"数据源：小红书（Web 端搜索 + 笔记详情页）")
    md.append("")
    md.append("## 一、采集与清洗概况")
    md.append("")
    md.append("| 项目 | 数值 |")
    md.append("|---|---|")
    md.append(f"| 搜索关键词 | 20 组（洗面奶 / 洁面 / 氨基酸洗面奶 / 洗面奶避雷 / 洗面奶测评 / 油皮 / 干皮 / 敏感肌 / 痘肌 / 智商税 / 紧绷 / 假滑 / 黑头 / 平价 / 男士洗面奶 等） |")
    md.append(f"| 采集笔记 | {len(meta)} 篇 |")
    md.append(f"| 抓取评论（原始） | {total_raw} 条 |")
    md.append(f"| 清洗后有效语料 | **{total_kept} 条**（其中笔记正文 {sum(1 for c in kept if c.get('isNoteDesc'))} 条、真实评论 {sum(1 for c in kept if not c.get('isNoteDesc'))} 条） |")
    md.append(f"| 被剔除语料 | {fl.get('count', 0)} 条 |")
    md.append("")
    md.append("### 剔除规则分布（沿用眼油模块 R1–R12）")
    md.append("")
    md.append("| 规则 | 含义 | 剔除条数 |")
    md.append("|---|---|---|")
    for r, n in rule_cnt.most_common():
        md.append(f"| {r} | {RULE_DESC.get(r, '')} | {n} |")
    md.append("")
    md.append("> 说明：每条语料只归入一个最相关的需求/痛点桶；重复文案（R10）只计一条，避免频次虚高。")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 二、逐篇笔记 · 评论明细")
    md.append("")
    md.append(f"> 共 {len(notes)} 篇笔记，按有效评论数从多到少排列。「笔记正文」为作者原文，一并计入语料。")
    md.append("")
    for i, (nid, cs) in enumerate(notes, 1):
        m = meta.get(nid, {})
        title = m.get("title") or "(无标题)"
        url = m.get("url", "")
        md.append(f"### {i}. {title}")
        md.append("")
        md.append(f"- 链接：{url}")
        md.append(f"- 来源关键词：{m.get('keyword', '—')}　｜　类型：{m.get('tag', '—')}　｜　"
                  f"点赞：{m.get('likes') or '—'}　｜　该篇抓到评论 {raw_cnt.get(nid, 0)} 条，有效 {len(cs)} 条")
        if m.get("desc"):
            d = re.sub(r"\s+", " ", m["desc"])[:200]
            md.append(f"- 笔记正文摘要：{d}…")
        md.append("")
        md.append("| # | 语料内容 | 来源 |")
        md.append("|---|---|---|")
        for j, c in enumerate(cs, 1):
            t = re.sub(r"\s+", " ", c.get("content", "")).replace("|", "丨")
            src = "笔记正文" if c.get("isNoteDesc") else "评论"
            md.append(f"| {j} | {t[:220]} | {src} |")
        md.append("")
    md.append("---")
    md.append("")
    md.append("## 三、口径说明")
    md.append("")
    md.append("- **采集方式**：小红书 Web 端按关键词搜索，进入笔记详情页后多次下滑并点击「展开更多回复」，"
              "抓 `#detail-title` / `#detail-desc` / `.parent-comment` 的可见文本。")
    md.append("- **仅采公开可见评论**，不做任何推测性补全；未取到的字段留空。")
    md.append("- **「有效」判定**：命中洁面品类词或品牌词，且未命中的 R1–R12 任一剔除规则。")
    md.append("- 本表为**原始语料留档**，需求 TOP5 / 痛点红线 / 决策权重的统计结果见主模块页面。")
    md.append("")
    mdp = os.path.join(BASE, f"洗面奶_小红书评论汇总_{TODAY}.md")
    open(mdp, "w", encoding="utf-8").write("\n".join(md))

    # ---------- HTML ----------
    h = []
    h.append("""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>洗面奶 · 小红书评论汇总</title><style>
:root{--bg:#f5f6fa;--card:#fff;--ink:#1e293b;--ink2:#64748b;--line:#e2e8f0;--pri:#4f46e5;--pri-soft:#eef2ff;--good:#0d9488;--bad:#e11d48}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font:14px/1.65 "Microsoft YaHei","PingFang SC",system-ui,sans-serif;padding-bottom:40px}
.wrap{max-width:1080px;margin:0 auto;padding:0 24px}
header{background:var(--card);border-bottom:1px solid var(--line);padding:16px 0;position:sticky;top:0;z-index:10}
header h1{font-size:18px}header .sub{font-size:12px;color:var(--ink2);margin-top:3px}
.sec{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 20px;margin:16px 0}
.sec h2{font-size:16px;margin-bottom:10px}
table{width:100%;border-collapse:collapse;font-size:13px;margin-top:6px}
th,td{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top}
th{background:#f8fafc;font-weight:600;font-size:12px}
.note{border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin-bottom:12px;background:#fff}
.note h3{font-size:14.5px;margin-bottom:6px}
.note .mt{font-size:12px;color:var(--ink2);margin-bottom:6px}
.note .mt a{color:var(--pri);text-decoration:none;word-break:break-all}
.tag{font-size:11px;background:#f1f5f9;color:var(--ink2);border-radius:3px;padding:1px 6px;margin-left:4px}
.tag.d{background:#fff1f2;color:var(--bad)}
.desc{font-size:12.5px;color:var(--ink2);background:#f8fafc;border-left:3px solid var(--pri);padding:6px 10px;margin:6px 0;border-radius:0 6px 6px 0}
ul{margin-left:18px;font-size:13px;color:var(--ink2)}
li{margin:3px 0}
</style></head><body><header><div class="wrap">
<h1>洗面奶 · 小红书评论汇总</h1>
<div class="sub">类目路径：个护家清 / 面部护理 / 洁面　｜　数据源：小红书公开笔记与评论　｜　采集日期：""")
    h.append(TODAY_D)
    h.append("""</div></div></header><main class="wrap">""")
    h.append('<div class="sec"><h2>一、采集与清洗概况</h2><table>')
    h.append("<tr><th>项目</th><th>数值</th></tr>")
    h.append(f"<tr><td>搜索关键词</td><td>20 组（洗面奶 / 洁面 / 氨基酸洗面奶 / 洗面奶避雷 / 洗面奶测评 / 油皮 / 干皮 / 敏感肌 / 痘肌 / 智商税 / 紧绷 / 假滑 / 黑头 / 平价 / 男士洗面奶 等）</td></tr>")
    h.append(f"<tr><td>采集笔记</td><td>{len(meta)} 篇</td></tr>")
    h.append(f"<tr><td>抓取评论（原始）</td><td>{total_raw} 条</td></tr>")
    h.append(f"<tr><td>清洗后有效语料</td><td><b>{total_kept}</b> 条（笔记正文 {sum(1 for c in kept if c.get('isNoteDesc'))} · 真实评论 {sum(1 for c in kept if not c.get('isNoteDesc'))}）</td></tr>")
    h.append(f"<tr><td>被剔除语料</td><td>{fl.get('count', 0)} 条</td></tr>")
    h.append("</table>")
    h.append('<h2 style="font-size:14px;margin-top:14px">剔除规则分布（沿用眼油模块 R1–R12）</h2><table>')
    h.append("<tr><th>规则</th><th>含义</th><th>剔除条数</th></tr>")
    for r, n in rule_cnt.most_common():
        h.append(f"<tr><td>{esc(r)}</td><td>{esc(RULE_DESC.get(r,''))}</td><td>{n}</td></tr>")
    h.append("</table></div>")
    h.append(f'<div class="sec"><h2>二、逐篇笔记 · 评论明细</h2>'
             f'<div style="font-size:12.5px;color:#64748b">共 {len(notes)} 篇笔记，按有效评论数从多到少排列</div></div>')
    for i, (nid, cs) in enumerate(notes, 1):
        m = meta.get(nid, {})
        h.append('<div class="note">')
        h.append(f'<h3>{i}. {esc(m.get("title") or "(无标题)")}</h3>')
        h.append(f'<div class="mt"><a href="{esc(m.get("url",""))}" target="_blank">{esc(m.get("url",""))}</a></div>')
        h.append(f'<div class="mt">来源关键词 <span class="tag">{esc(m.get("keyword","—"))}</span>'
                 f'类型 <span class="tag">{esc(m.get("tag","—"))}</span>'
                 f'点赞 <span class="tag">{esc(m.get("likes") or "—")}</span>'
                 f'抓到评论 <span class="tag">{raw_cnt.get(nid,0)}</span>'
                 f'有效 <span class="tag d">{len(cs)}</span></div>')
        if m.get("desc"):
            h.append(f'<div class="desc">笔记正文摘要：{esc(re.sub(r"\s+"," ",m["desc"])[:200])}…</div>')
        h.append("<table><tr><th style='width:38px'>#</th><th>语料内容</th><th style='width:78px'>来源</th></tr>")
        for j, c in enumerate(cs, 1):
            t = esc(re.sub(r"\s+", " ", c.get("content", ""))[:240])
            src = '<span class="tag">正文</span>' if c.get("isNoteDesc") else '<span class="tag d">评论</span>'
            h.append(f"<tr><td>{j}</td><td>{t}</td><td>{src}</td></tr>")
        h.append("</table></div>")
    h.append('<div class="sec"><h2>三、口径说明</h2><ul>'
             "<li>采集方式：小红书 Web 端按关键词搜索，进入笔记详情页后多次下滑并点击「展开更多回复」，抓可见文本。</li>"
             "<li>仅采公开可见内容，不做推测性补全；未取到的字段留空。</li>"
             "<li>「有效」判定：命中洁面品类词或品牌词，且未命中 R1–R12 任一剔除规则。</li>"
             "<li>本页为原始语料留档；需求 TOP5 / 痛点红线 / 决策权重的统计结果见主模块页面。</li>"
             "</ul></div>")
    h.append("</main></body></html>")
    hp = os.path.join(BASE, f"洗面奶_小红书评论汇总_{TODAY}.html")
    open(hp, "w", encoding="utf-8").write("".join(h))

    print(f"[done] 笔记 {len(meta)} 篇｜有效语料 {total_kept} 条", flush=True)
    print(f"  → {mdp}", flush=True)
    print(f"  → {hp}", flush=True)


if __name__ == "__main__":
    main()
