# -*- coding: utf-8 -*-
"""P0 抽检：从 filtered_log.json 分层随机抽 20 条被过滤评论 + 10 条保留评论（查漏放）"""
import json, os, random, html, datetime

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SEED = 20260924
N = 20
N_KEPT = 10

log = json.load(open(os.path.join(BASE, "data", "filtered_log.json"), encoding="utf-8"))
kept = json.load(open(os.path.join(BASE, "data", "raw_comments.json"), encoding="utf-8"))
if isinstance(kept, dict):
    kept = kept.get("kept") or kept.get("comments") or []

rnd = random.Random(SEED)
filtered = log["filtered"]
by_rule = {}
for r in filtered:
    by_rule.setdefault(r.get("filterRule") or "?", []).append(r)

# 分层配额：R1 3 / R2 5 / R3 12（R3 基数最大且误杀风险最高，占多数）
QUOTA = {"R1": 3, "R2": 5, "R3": 12}
sample = []
for rule, q in QUOTA.items():
    pool = by_rule.get(rule, [])
    q = min(q, len(pool))
    pick = rnd.sample(pool, q)
    for r in pick:
        sample.append(r)
# 不足 20 时用剩余规则补齐
if len(sample) < N:
    rest = [r for r in filtered if r not in sample]
    sample += rnd.sample(rest, min(N - len(sample), len(rest)))
sample = sample[:N]

kept_sample = rnd.sample(kept, min(N_KEPT, len(kept)))

RULE_DESC = {
    "R1": "营销文本模式（广告/引流话术）",
    "R2": "空内容 / 超短且无信息（<6字且无品类品牌词）",
    "R3": "与品类、品牌均无关（低相关）",
    "R4": "同文案在 ≥3 篇笔记复刷（模板水军）",
    "R7": "营销号昵称特征",
}

OBSERVATIONS = [
    "第 2 条「第四个淘宝上还可以买啊，难道是假的？」→ 命中 R1 的「淘宝」关键词，但这是用户在讨论购买渠道与真假，不是引流广告，<b>疑似误杀</b>；建议给 R1 加例外语境（难道是假的 / 真的假的 / 是不是正品 / 哪个渠道买）。",
    "第 1、3 条「链接在哪？」→ 命中 R1 的「链接在」。是用户求链接而非发广告，信息量低，过滤勉强合理，属边缘案例。",
    "第 12 条「不是真精华油」→ R3 判低相关，但这是质疑产品成分的负面口碑，<b>可能误杀</b>。",
    "第 15 条「我也用了，没事儿啊」→ 有真实使用体验但无品类词，被 R3 过滤，<b>疑似误杀</b>；可考虑把「用了 / 上眼 / 入手 / 回购」等亲历动词也当作相关信号。",
    "第 17、19 条同一句「没有油光我真的会爱」出现 2 次 → 未触发 R4（要求同文案跨 ≥3 篇笔记），说明 2 次复刷目前放行了。",
    "附录第 6、7 条是纯话题标签串（#眼油 #眼油推荐…）被保留 → <b>疑似漏放</b>，与任务书 6.3 节「过滤含 # 的话题标签串」口径不一致。",
]

def cell(t):
    return (t or "").replace("|", "／").replace("\n", " ").strip()

def short(t, n=90):
    t = cell(t)
    return t if len(t) <= n else t[:n] + "…"

lines = []
lines.append("# P0 抽检 20 条 · 水军过滤人工校验（2026-09-24）")
lines.append("")
lines.append(f"- 抽样来源：`data/filtered_log.json`（被过滤 {log['count']} 条，规则分布 "
             + "、".join(f"{k} {v}" for k, v in sorted(log["ruleSummary"].items())) + "）")
lines.append(f"- 抽样方式：固定随机种子 {SEED} 分层抽样，配额 R1×3 / R2×5 / R3×12，可复现")
lines.append(f"- 附录：另抽 {len(kept_sample)} 条**已保留**评论，用于检查「漏放」")
lines.append("- 用法：看「原文内容」判断过滤是否冤枉（误杀）。最后两列留空，供乾颖手写结论。")
lines.append("")
lines.append("| # | 规则 | 过滤理由 | 原文内容 | 品类/品牌命中 | 点赞 | 是否误杀？ | 备注 |")
lines.append("|---|---|---|---|---|---|---|---|")
for i, r in enumerate(sample, 1):
    hits = "、".join((r.get("categoryHits") or []) + (r.get("brandHits") or [])) or "—"
    lines.append(f"| {i} | {r.get('filterRule')} | {cell(r.get('filterReason'))} | {short(r.get('content'), 110)} | {hits} | {r.get('likeCount', 0)} |  |  |")
lines.append("")
lines.append("## 附录：已保留评论 10 条（查漏放）")
lines.append("")
lines.append("| # | 原文内容 | 品类/品牌命中 | 点赞 | 是否该删？ | 备注 |")
lines.append("|---|---|---|---|---|---|")
for i, r in enumerate(kept_sample, 1):
    hits = "、".join((r.get("categoryHits") or []) + (r.get("brandHits") or [])) or "—"
    lines.append(f"| {i} | {short(r.get('content'), 110)} | {hits} | {r.get('likeCount', 0)} |  |  |")
lines.append("")
lines.append("## AI 初筛提示（需乾颖确认，不作为结论）")
lines.append("")
for t in OBSERVATIONS:
    lines.append(f"- {t}")
lines.append("")
lines.append("## 规则释义")
lines.append("")
for k, v in RULE_DESC.items():
    lines.append(f"- **{k}** = {v}")

md = "\n".join(lines)
out_md = os.path.join(BASE, "P0_抽检20条_20260924.md")
open(out_md, "w", encoding="utf-8").write(md)

# ---- HTML 版（肉眼过一遍用） ----
def esc(t):
    return html.escape(cell(t))

rows = "".join(
    f"<tr><td>{i}</td><td><span class='tag'>{esc(r.get('filterRule'))}</span></td>"
    f"<td>{esc(r.get('filterReason'))}</td><td class='c'>{esc(r.get('content'))}</td>"
    f"<td>{esc('、'.join((r.get('categoryHits') or []) + (r.get('brandHits') or [])) or '—')}</td>"
    f"<td class='n'>{r.get('likeCount', 0)}</td><td class='blank'></td><td class='blank'></td></tr>"
    for i, r in enumerate(sample, 1))
krows = "".join(
    f"<tr><td>{i}</td><td class='c'>{esc(r.get('content'))}</td>"
    f"<td>{esc('、'.join((r.get('categoryHits') or []) + (r.get('brandHits') or [])) or '—')}</td>"
    f"<td class='n'>{r.get('likeCount', 0)}</td><td class='blank'></td><td class='blank'></td></tr>"
    for i, r in enumerate(kept_sample, 1))

htm = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>P0 抽检 20 条 · 水军过滤人工校验</title>
<style>
body{{font-family:-apple-system,"Microsoft YaHei",sans-serif;margin:0;padding:28px 32px;color:#1f2328;background:#f7f8fa;line-height:1.6}}
h1{{font-size:22px;margin:0 0 6px}} .sub{{color:#6b7280;font-size:13px;margin-bottom:18px}}
.box{{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:18px;margin-bottom:20px}}
h2{{font-size:16px;margin:0 0 10px}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{border:1px solid #e5e7eb;padding:7px 9px;vertical-align:top}}
th{{background:#f3f4f6;text-align:left;font-weight:600;white-space:nowrap}}
td.c{{max-width:420px;word-break:break-all}}
td.n{{text-align:center;width:52px}}
td.blank{{background:#fcfcfd;width:90px}}
.tag{{display:inline-block;background:#eef2ff;color:#4338ca;border-radius:4px;padding:1px 6px;font-weight:600}}
tr:nth-child(even) td{{background:#fafafa}}
.rules{{font-size:13px;color:#374151}}
</style></head><body>
<h1>P0 抽检 20 条 · 水军过滤人工校验</h1>
<div class="sub">来源 data/filtered_log.json（被过滤 {log['count']} 条）｜随机种子 {SEED}（可复现）｜生成于 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
<div class="box">
<h2>被过滤的 20 条 —— 重点看有没有「误杀」</h2>
<table><thead><tr><th>#</th><th>规则</th><th>过滤理由</th><th>原文内容</th><th>品类/品牌命中</th><th>点赞</th><th>误杀？</th><th>备注</th></tr></thead>
<tbody>{rows}</tbody></table>
</div>
<div class="box">
<h2>附录：已保留的 {len(kept_sample)} 条 —— 重点看有没有「漏放」</h2>
<table><thead><tr><th>#</th><th>原文内容</th><th>品类/品牌命中</th><th>点赞</th><th>该删？</th><th>备注</th></tr></thead>
<tbody>{krows}</tbody></table>
</div>
<div class="box rules">
<h2>规则释义</h2>
{''.join(f'<div><b>{k}</b> = {v}</div>' for k, v in RULE_DESC.items())}
</div>
<div class="box rules">
<h2>AI 初筛提示（需乾颖确认，不作为结论）</h2>
<ol>{''.join(f'<li style="margin-bottom:6px">{t}</li>' for t in OBSERVATIONS)}</ol>
</div>
</body></html>"""
out_html = os.path.join(BASE, "P0_抽检20条_20260924.html")
open(out_html, "w", encoding="utf-8").write(htm)

print("MD:", out_md)
print("HTML:", out_html)
print("filtered sample:", len(sample), "kept sample:", len(kept_sample))
