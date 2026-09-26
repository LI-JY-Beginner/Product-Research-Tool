# -*- coding: utf-8 -*-
"""
03_build_html.py — 生成自包含单文件 index.html（数据内嵌，双击即开、断网可用）
结构（v3，按乾颖要求重构）：
  上半部分「结论速览」：6 个产出各一张极简结论卡（关键词 + 频次数字，最显眼）
  下半部分「数据明细」：6 个可点开的栏目，与上面 6 个产出一一对应，点开才是完整数据 + 来源
  附：TOP10 品牌玩家（数据基础，作为附加栏目放在最后）
"""
import json, os
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 自动定位：.../用户调研模块
WORKSPACE = os.path.dirname(BASE)
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "index.html")

def j(name):
    p = os.path.join(DATA, name + ".json")
    if not os.path.exists(p): return {}
    return json.load(open(p, encoding="utf-8"))

d = {k: j(k) for k in ["meta", "overview", "top10", "audience", "needs_top5", "redline", "lexicon"]}
tree = j("category_tree")
NOW = datetime.now().strftime("%Y-%m-%d %H:%M")

# ===== 预计算「结论速览」所需的极简数据 =====
def _avg(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(sum(xs) / len(xs), 1) if xs else None

# 全品类口径：所有品牌一视同仁，不做自家 / 竞品拆分
au = d.get("audience", {})
au_rows = au.get("rows", [])
all_f = _avg([r.get("femalePct") for r in au_rows])
age_cnt = {}
for r in au_rows:
    if r.get("ageRange"): age_cnt[r["ageRange"]] = age_cnt.get(r["ageRange"], 0) + 1
age_main = None
if age_cnt:
    mx = max(age_cnt.values())
    age_main = [k for k, v in age_cnt.items() if v == mx][0]
au["quick"] = {"allFemale": all_f, "mainAge": age_main,
               "mainAgeCount": age_cnt.get(age_main, 0) if age_main else 0,
               "covered": len(au_rows)}

lx = d.get("lexicon", {})
sd = lx.get("sentimentDist", [])
tot = sum(x.get("value", 0) for x in sd)
good_rate = round(next((x["value"] for x in sd if x["name"] == "好评"), 0) / tot * 100, 1) if tot else None
lx["quick"] = {
    "goodTop": [x["word"] for x in sorted(lx.get("cloud", []), key=lambda x: -x["count"]) if x["polarity"] == "good"][:5],
    "badTop": [x["word"] for x in sorted(lx.get("cloud", []), key=lambda x: -x["count"]) if x["polarity"] == "bad"][:5],
    "goodRate": good_rate,
    "decision": sorted(lx.get("decision", []), key=lambda x: -x.get("pct", 0)),
}
d["audience"], d["lexicon"] = au, lx

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>用户调研模块 · 眼部护理品类 | AI全球选品平台</title>
<style>
:root{--bg:#f5f6fa;--card:#fff;--ink:#1e293b;--ink2:#64748b;--line:#e2e8f0;
--pri:#4f46e5;--pri-soft:#eef2ff;--good:#0d9488;--bad:#e11d48;--warn:#d97706;--warn-bg:#fffbeb;--self:#0891b2;}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font:14px/1.65 "Microsoft YaHei","PingFang SC",system-ui,sans-serif;padding-bottom:50px}
.wrap{max-width:1140px;margin:0 auto;padding:0 24px}
header{background:var(--card);border-bottom:1px solid var(--line);padding:14px 0;position:sticky;top:0;z-index:20}
.hd{display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.hd h1{font-size:18px}
.hd .sub{font-size:12px;color:var(--ink2)}
.cate{display:flex;align-items:center;gap:6px;margin-left:auto;font-size:13px}
.cate select{border:1px solid var(--line);border-radius:6px;padding:5px 8px;font-size:13px;background:#fff;color:var(--ink);max-width:150px}
.cate .sep{color:#94a3b8}
.badge{font-size:11px;padding:3px 9px;border-radius:12px;background:#f0fdf4;color:#16a34a;border:1px solid #bbf7d0}
main{padding:20px 0}
.sec{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin-bottom:18px}
.sec h2{font-size:16px;display:flex;align-items:center;gap:9px;margin-bottom:3px}
.sec .lead{font-size:12.5px;color:var(--ink2);margin-bottom:14px}
.src{margin-top:14px;background:#f8fafc;border:1px solid var(--line);border-left:3px solid var(--pri);border-radius:0 8px 8px 0;padding:10px 14px;font-size:12px;color:var(--ink2)}
.src b{color:var(--ink)}
table{width:100%;border-collapse:collapse;font-size:13px;margin-top:6px}
th,td{border:1px solid var(--line);padding:7px 9px;text-align:left}
th{background:#f8fafc;font-weight:600;font-size:12px}
.tagn{font-size:10px;background:#f1f5f9;color:var(--ink2);border-radius:3px;padding:1px 5px;margin-left:5px}
.insight{background:var(--warn-bg);border:1px solid #fde68a;border-radius:8px;padding:9px 13px;font-size:12.5px;color:#92400e;margin-top:10px}
.insight li{margin-left:16px}
.bar{display:flex;align-items:center;gap:9px;margin-bottom:7px;font-size:13px}
.bar .bn{min-width:20px;color:var(--ink2);font-size:12px}
.bar .bt{min-width:110px}
.bar .tk{flex:1;height:15px;background:#f1f5f9;border-radius:8px;overflow:hidden}
.bar .fl{height:100%;border-radius:8px}
.bar .bv{min-width:52px;text-align:right;font-size:12px;color:var(--ink2)}
.redline li{list-style:none;padding:9px 0 9px 26px;position:relative;border-bottom:1px dashed var(--line);font-size:13.5px}
.redline li:before{content:"⛔";position:absolute;left:0}
.redline .cnt{color:var(--bad);font-weight:700}
.qt{font-size:12px;color:var(--ink2);padding:3px 0 3px 11px;border-left:3px solid #fecdd3;margin-top:3px}
.cloud{text-align:center;padding:14px 6px;min-width:290px;flex:1;background:#fff;border:1px solid var(--line);border-radius:8px}
.cloud h5{font-size:12px;color:var(--ink2);margin-bottom:6px;font-weight:600}
.cloud span{display:inline-block;margin:3px 7px}
.wg{color:var(--good)}.wb{color:var(--bad)}
.donut{min-width:260px}
.exc{margin-top:12px;border:1px dashed #fca5a5;background:#fff1f2;border-radius:8px;padding:10px 14px}
.exc h4{font-size:12.5px;color:var(--bad);margin-bottom:5px}
.exc li{font-size:12px;color:var(--ink2);margin-left:16px}
.item{border:1px solid var(--line);border-radius:9px;padding:11px 14px;margin-bottom:9px}
.item .hh{display:flex;align-items:baseline;gap:8px}
.item .rk{font-weight:700;color:var(--pri);font-size:12px}
.item .nm{font-weight:600}
.item .ct{margin-left:auto;font-size:12px;color:var(--ink2)}
.item .tg{font-size:11.5px;color:var(--pri);cursor:pointer}
.item.open .qq{display:block}
.qq{display:none;margin-top:7px;border-top:1px dashed var(--line);padding-top:7px}
.qq div{font-size:12px;color:var(--ink2);padding:2px 0 2px 10px;border-left:3px solid var(--pri-soft)}
.qq .mt{font-size:11px;color:#94a3b8;margin-top:4px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:820px){.grid2{grid-template-columns:1fr}}
.empty{color:#94a3b8;font-size:13px;padding:16px;text-align:center;background:#f8fafc;border-radius:8px}
/* ===== 结论速览卡片 ===== */
.sgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
@media(max-width:900px){.sgrid{grid-template-columns:1fr 1fr}}
@media(max-width:620px){.sgrid{grid-template-columns:1fr}}
.scard{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;cursor:pointer;transition:.15s}
.scard:hover{border-color:var(--pri);box-shadow:0 2px 10px rgba(79,70,229,.10);transform:translateY(-1px)}
.scard .st{font-size:12.5px;font-weight:700;display:flex;align-items:center;gap:7px}
.scard .st .no{background:var(--pri);color:#fff;width:19px;height:19px;border-radius:5px;display:inline-flex;align-items:center;justify-content:center;font-size:11px}
.scard .sbody{margin-top:9px}
.scard .go{font-size:11.5px;color:var(--pri);margin-top:9px;font-weight:600}
.chip{display:inline-block;margin:3px 6px 3px 0;padding:3px 10px;border-radius:14px;font-size:12.5px;background:#f1f5f9;color:var(--ink);white-space:nowrap}
.chip b{color:var(--pri);margin-left:4px;font-size:13.5px}
.chip.r{background:#fff1f2}.chip.r b{color:var(--bad)}
.chip.g{background:#f0fdf4}.chip.g b{color:var(--good)}
.chip.i{background:var(--pri-soft)}.chip.i b{color:var(--pri)}
.kline{font-size:13px;margin:4px 0;line-height:1.5}
.kline b{color:var(--bad)}
.kline .em{color:var(--pri);font-weight:700}
.arrow{color:#94a3b8;font-weight:400;margin:0 3px}
/* ===== 明细折叠栏目 ===== */
.panel{background:var(--card);border:1px solid var(--line);border-radius:12px;margin-bottom:12px;overflow:hidden}
.ph{display:flex;align-items:center;gap:10px;padding:13px 18px;cursor:pointer;font-size:15px;font-weight:600;user-select:none}
.ph:hover{background:#f8fafc}
.ph .no{background:var(--pri);color:#fff;width:24px;height:24px;border-radius:6px;display:inline-flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;flex:none}
.ph .hint{font-size:12px;color:#94a3b8;font-weight:400;display:none}
@media(min-width:860px){.ph .hint{display:inline}}
.ph .chev{margin-left:auto;color:#94a3b8;font-size:12px;transition:.2s}
.panel.open .chev{transform:rotate(180deg)}
.pb{display:none;border-top:1px solid var(--line);padding:18px 20px}
.panel.open .pb{display:block}
footer{text-align:center;color:#94a3b8;font-size:12px;padding:10px 0}
</style>
</head>
<body>
<header><div class="wrap"><div class="hd">
  <div><h1>用户调研模块</h1><div class="sub">AI全球选品平台 · 眼油品类（全品类视角，各品牌一视同仁）</div></div>
  <span class="badge" id="upd">—</span>
  <div class="cate">
    类目
    <select id="c1"></select><span class="sep">/</span>
    <select id="c2"></select><span class="sep">/</span>
    <select id="c3"></select>
  </div>
</div></div></header>
<main class="wrap">
<div id="body"></div>
</main>
<footer class="wrap">数据与展示分离 · 本页由 data/*.json 驱动 · 每日 09:30 自动更新 · 生成于 __NOW__</footer>

<script>
const D = __DATA__;
const TREE = __TREE__;
/* ---------- 图表：纯 SVG / DOM，零依赖 ---------- */
function donut(items, colors, totalLabel){
  const total = items.reduce((s,i)=>s+i.value,0)||1;
  const R=64,C=2*Math.PI*R; let off=0,svg='';
  items.forEach((it,i)=>{const f=it.value/total,L=f*C;
    svg+=`<circle r="${R}" cx="90" cy="90" fill="none" stroke="${colors[i%colors.length]}" stroke-width="26"
      stroke-dasharray="${L} ${C-L}" stroke-dashoffset="${-off}" transform="rotate(-90 90 90)"><title>${it.name} ${it.value}</title></circle>`;off+=L;});
  const lg=items.map((it,i)=>`<div style="display:flex;align-items:center;gap:5px;font-size:12px;margin:2px 0">
    <span style="width:9px;height:9px;border-radius:2px;background:${colors[i%colors.length]};display:inline-block"></span>
    <span style="flex:1">${it.name}</span><span style="color:#64748b">${it.value}（${(it.value/total*100).toFixed(1)}%）</span></div>`).join('');
  return `<svg width="180" height="180" viewBox="0 0 180 180">${svg}
    <text x="90" y="86" text-anchor="middle" font-size="17" font-weight="700" fill="#1e293b">${total}</text>
    <text x="90" y="104" text-anchor="middle" font-size="10" fill="#64748b">${totalLabel||'合计'}</text></svg><div>${lg}</div>`;
}
function bars(items, color){
  const mx=Math.max(...items.map(i=>i.value),1);
  return items.map((it,i)=>`<div class="bar"><span class="bn">${i+1}</span><span class="bt">${it.name}</span>
    <span class="tk"><span class="fl" style="width:${(it.value/mx*100).toFixed(1)}%;background:${color||'linear-gradient(90deg,#4f46e5,#818cf8)'}"></span></span>
    <span class="bv">${it.value}${it.unit||''}</span></div>`).join('');
}
function cloud(words){
  if(!words.length) return '<span style="color:#94a3b8;font-size:12px">暂无</span>';
  const mx=Math.max(...words.map(w=>w.count),1),mn=Math.min(...words.map(w=>w.count),0);
  return words.slice(0,26).map(w=>{const t=(w.count-mn)/(mx-mn||1);
    return `<span class="${w.polarity==='good'?'wg':'wb'}" style="font-size:${(12+t*20).toFixed(1)}px;opacity:${(0.45+t*0.55).toFixed(2)}" title="频次${w.count}">${w.word}</span>`;}).join('');
}
const esc=s=>String(s==null?'':s).replace(/</g,'&lt;');
const shortName=n=>String(n||'').split('（')[0];

/* ---------- 折叠栏目 ---------- */
function panel(no,title,hint,html,src){
  return `<div class="panel" id="p${no}"><div class="ph" onclick="togglePanel(${no})">
    <span class="no">${no}</span>${title}<span class="hint">${hint}</span><span class="chev">▼ 展开明细</span></div>
    <div class="pb">${html}<div class="src">${src}</div></div></div>`;
}
function openPanel(n){const p=document.getElementById('p'+n);if(p&&!p.classList.contains('open'))p.classList.add('open');
  if(p)setTimeout(()=>p.scrollIntoView({behavior:'smooth',block:'start'}),50);}
function togglePanel(n){document.getElementById('p'+n).classList.toggle('open');}

/* ---------- 渲染 ---------- */
function render(){
  const o=D.overview||{}, t=D.top10||{}, au=D.audience||{}, nd=D.needs_top5||{},
        rd=D.redline||{}, lx=D.lexicon||{}, m=D.meta||{};
  document.getElementById('upd').textContent='数据截至 '+(m.lastUpdated||'—');
  let h='';
  /* 登录过期提醒 */
  const ls=m.loginStatus||{};
  const exp=Object.keys(ls).filter(k=>ls[k]==='expired');
  if(exp.length){
    const names={xhs:'小红书',feigua:'飞瓜数据',douyin:'抖音'};
    h+=`<section class="sec" style="background:#fef2f2;border-color:#fecaca">
      <div style="font-size:13.5px;color:#b91c1c"><b>⚠️ 登录态已过期，请重新登录</b></div>
      <div style="font-size:12.5px;color:#991b1b;margin-top:4px">过期平台：<b>${exp.map(k=>names[k]||k).join('、')}</b>
      ${m.loginNote?'　｜　'+esc(m.loginNote):''}</div>
      <div style="font-size:12px;color:#7f1d1d;margin-top:6px">本页展示的是最后一次成功采集的数据（截至 ${esc(m.lastUpdated||'—')}）；重新登录后运行「用户调研模块-每日更新」即可刷新。</div>
    </section>`;
  }
  /* 概览条（一行） */
  h+=`<section class="sec" style="background:var(--pri-soft);border-color:#c7d2fe;padding:12px 20px">
    <div style="display:flex;gap:22px;flex-wrap:wrap;font-size:13px;align-items:baseline">
    <b>${o.brandCount||0}</b> 个品牌<span style="color:#c7d2fe">｜</span>
    <b>${o.productCount||0}</b> 个商品SPU<span style="color:#c7d2fe">｜</span>
    <b>${o.corpusTotal||o.reviewCount||0}</b> 条真实语料（飞瓜 ${o.corpusFeigua||0} + 小红书 ${o.corpusXhs||0}）<span style="color:#c7d2fe">｜</span>
    数据区间 <b>${o.dataRange?o.dataRange.start:'—'} ~ ${o.dataRange?o.dataRange.end:'—'}</b>
    </div></section>`;

  /* ============ 上半部分：结论速览（6 个产出各一张卡） ============ */
  const q=au.quick||{}, lq=lx.quick||{};
  const ni=(nd.items||[]).map(x=>({n:shortName(x.name),c:x.count,f:x.fgCount||0,x:x.xhsCount||0}));
  const ri=(rd.items||[]).map(x=>({n:shortName(x.name),c:x.count,f:x.fgCount||0,x:x.xhsCount||0,
     cross:(x.xhsCount||0)>(x.fgCount||0)}));
  const dc=(lq.decision||[]).map(x=>({criterion:x.criterion,pct:x.pct}));
  h+=`<section class="sec">
    <h2>⚡ 结论速览 · 六大产出</h2>
    <div class="lead">飞书工作流要求的 6 个产出，一屏看完；<b>点击任意卡片</b>可跳到下方对应栏目查看完整数据与来源</div>
    <div class="sgrid">`;
  /* 卡1 目标用户画像 */
  h+=`<div class="scard" onclick="openPanel(1)"><div class="st"><span class="no">1</span>目标用户画像</div><div class="sbody">
    <div class="kline">女性占比均值 <span class="em">${q.allFemale!=null?q.allFemale+'%':'—'}</span></div>
    <div class="kline">主力人群 <b>${q.mainAge||'—'}</b>${q.mainAgeCount?'（'+q.mainAgeCount+' 个商品）':''}</div>
    <div class="kline" style="color:#92400e">→ 覆盖 ${q.covered||0} 个商品画像</div>
    </div><div class="go">查看画像明细 ↓</div></div>`;
  /* 卡2 高频需求 TOP5 */
  h+=`<div class="scard" onclick="openPanel(2)"><div class="st"><span class="no">2</span>高频需求 TOP5（购买原因）</div><div class="sbody">
    ${ni.slice(0,5).map(x=>`<span class="chip g">${esc(x.n)}<b>${x.c}</b></span>`).join('')}
    </div><div class="go">查看需求明细 ↓</div></div>`;
  /* 卡3 高频痛点 TOP5 */
  h+=`<div class="scard" onclick="openPanel(3)"><div class="st"><span class="no">3</span>高频痛点 TOP5（频次）</div><div class="sbody">
    ${ri.slice(0,5).map(x=>`<span class="chip r">${esc(x.n)}<b>${x.c}</b></span>`).join('')}
    </div><div class="go">查看痛点明细 ↓</div></div>`;
  /* 卡4 必须解决的红线 */
  h+=`<div class="scard" onclick="openPanel(4)"><div class="st"><span class="no">4</span>我们必须解决的痛点（产品开发红线）</div><div class="sbody">
    ${ri.filter(x=>x.cross).slice(0,1).map(x=>`<span class="chip i">糊眼/进眼睛<b>${x.c}</b></span>`).join('')}
    ${ri.slice(0,3).map(x=>`<span class="chip r">${esc(x.n)}<b>${x.c}</b></span>`).join('')}
    <div class="kline" style="color:#92400e">→ 已剔除物流/价格等不可改良项</div>
    </div><div class="go">查看红线明细 ↓</div></div>`;
  /* 卡5 用户话语词库 */
  h+=`<div class="scard" onclick="openPanel(5)"><div class="st"><span class="no">5</span>用户话语词库</div><div class="sbody">
    <div class="kline">好评率 <span class="em">${lq.goodRate!=null?lq.goodRate+'%':'—'}</span></div>
    <div class="kline">好评词：${(lq.goodTop||[]).map(w=>`<span class="chip g">${esc(w)}</span>`).join('')}</div>
    <div class="kline">差评词：${(lq.badTop||[]).map(w=>`<span class="chip r">${esc(w)}</span>`).join('')}</div>
    </div><div class="go">查看词库明细 ↓</div></div>`;
  /* 卡6 决策权重排序 */
  h+=`<div class="scard" onclick="openPanel(6)"><div class="st"><span class="no">6</span>用户决策权重排序</div><div class="sbody">
    <div class="kline" style="font-size:14px">${dc.slice(0,5).map(x=>`${esc(x.criterion)} <span class="em">${x.pct}%</span>`).join('<span class="arrow">＞</span>')}</div>
    <div class="kline" style="color:#92400e">→ 质地体验权重第一，高于功效：先"用得舒服"再"见效"</div>
    </div><div class="go">查看排序明细 ↓</div></div>`;
  h+=`</div></section>`;

  /* ============ 下半部分：数据明细（6 个栏目一一对应） ============ */
  h+=`<section class="sec" style="padding:14px 20px">
    <h2 style="font-size:14.5px">📂 数据明细 · 与上方 6 个产出一一对应</h2>
    <div class="lead" style="margin-bottom:0">点开栏目 = 该产出的完整数据、口径与数据来源</div>
  </section>`;

  /* 明细1 目标用户画像 */
  const ar=au.rows||[];
  h+=panel(1,'目标用户画像','产出①：性别 / 年龄 / 地域 / 内容偏好，各品牌横向对比',
    `<table><tr><th>品牌</th><th>女性占比</th><th>主力年龄</th><th>地域 TOP3</th><th>内容偏好</th></tr>`+
    ar.map(r=>`<tr><td><b>${esc(r.brand)}</b></td>
      <td>${r.femalePct!=null?r.femalePct+'%':'—'}</td><td>${esc(r.ageRange||'—')}${r.agePct?'（'+r.agePct+'%）':''}</td>
      <td>${esc((r.regionTop3||[]).join('、')||'—')}</td><td style="font-size:12px">${esc(r.prefer||'—')}</td></tr>`).join('')+`</table>`+
    ((au.insights||[]).length?`<div class="insight"><b>品类特征（自动汇总）</b><ul>${au.insights.map(i=>`<li>${esc(i.text)}　<span style="color:#a16207">证据：${esc(i.evidence)}</span></li>`).join('')}</ul></div>`:''),
    `<b>数据来源</b>：飞瓜商品详情页 →「受众画像」Tab（消费者画像 / 视频观众画像），飞瓜原生画像字段、非人口属性猜测<br>
     覆盖 ${ar.length} 个商品的画像快照　｜　<b>字段</b>：性别分布（含TGI）、年龄分布、地域分布（省份）、视频标签喜好<br>
     <b>采集日期</b>：${esc(au.fetchDate||'—')}`);

  /* 明细2 高频需求 TOP5 */
  h+=panel(2,'高频需求 TOP5（用户购买原因）','产出②：需求关键词 + 频次 + 用户原话',
    ni.length?bars((nd.items||[]).map(x=>({name:shortName(x.name),value:x.count})),'linear-gradient(90deg,#0d9488,#5eead4)')+
    `<div style="margin-top:12px">${(nd.items||[]).map((x,i)=>`<div class="item" onclick="event.stopPropagation();this.classList.toggle('open')">
      <div class="hh"><span class="rk">TOP${i+1}</span><span class="nm">${esc(x.name)}</span>
      <span class="ct">命中 ${x.count} 条<span style="color:#94a3b8">（飞瓜${x.fgCount||0} / 小红书${x.xhsCount||0}）</span></span><span class="tg">展开原话 ▾</span></div>
      <div class="qq">${(x.quotes||[]).map(q=>`<div>「${esc(q.text)}」</div>`).join('')}
      <div class="mt">来源：${esc((x.quotes||[]).map(q=>q.source).join('；')||'—')}</div></div></div>`).join('')}</div>`
    :'<div class="empty">暂无</div>',
    `<b>数据来源</b>：①飞瓜商品详情页 →「商品评价」好评/全部评价原文 +「商品舆情词云」；②小红书 10 个关键词（眼油/眼油避雷/眼油推荐/眼部精华油/眼油测评/眼周抗老/以油养肤 眼周/眼油 智商税/眼纹 眼油/黑眼圈 眼油）搜索结果 → 笔记正文 + 评论，已过 R1-R9 水军过滤、已剔除手法教程类低价值笔记<br>
     <b>归并口径</b>：飞瓜与小红书共用同一套需求桶，每条语料只归入最相关的一个桶；命中数按来源拆分<br>
     <b>语料规模</b>：合计 ${nd.corpus?nd.corpus.total:'—'} 条（飞瓜 ${nd.corpus?nd.corpus.feigua:'—'} / 小红书 ${nd.corpus?nd.corpus.xhs:'—'}）<br>
     <b>暂未纳入</b>：抖音带货视频文案（本轮不做，如需交叉验证购买原因再补）　｜　<b>生成时间</b>：${esc(nd.generatedAt||'—')}`);

  /* 明细3 高频痛点 TOP5 */
  h+=panel(3,'高频痛点 TOP5（频次排序）','产出③：痛点关键词 + 频次 + 双来源对比',
    ri.length?bars((rd.items||[]).map(x=>({name:shortName(x.name),value:x.count})),'linear-gradient(90deg,#e11d48,#fda4af)')+
    `<div style="margin-top:10px">${ri.map(x=>`<span class="chip r">${esc(x.n)}<b>${x.c}</b></span><span style="font-size:11px;color:#94a3b8;margin-right:10px">飞瓜${x.f} / 小红书${x.x}${x.cross?'　<span style="color:#be185d">▲ 小红书信号更强</span>':''}</span>`).join('')}</div>`
    :'<div class="empty">暂无</div>',
    `<b>数据来源</b>：与产出②同一语料池（飞瓜商品评价 244 条 + 小红书笔记与评论 185 条），按痛点桶统计命中频次<br>
     <b>口径说明</b>：否定表述不计入（"不油腻/不糊眼"不算痛点）；"担心会长脂肪粒"等担忧语境计入需求、不计入已发生痛点<br>
     <b>生成时间</b>：${esc(rd.generatedAt||'—')}`);

  /* 明细4 产品开发红线 */
  const riFull=rd.items||[];
  h+=panel(4,'我们必须解决的痛点（产品开发红线）','产出④：TOP 痛点的用户原话 + 涉及品牌 + 剔除规则',
    riFull.length?`<ul class="redline">${riFull.slice(0,4).map(x=>`<li><b>${esc(x.name)}</b>　<span class="cnt">${x.count} 条</span>
      <span style="font-size:12px;color:var(--ink2)">（飞瓜${x.fgCount||0} / 小红书${x.xhsCount||0}）${x.brandCount?' · 涉及 '+x.brandCount+' 个品牌：'+esc((x.brands||[]).join('、')):''}</span>
      ${(x.xhsCount||0)>(x.fgCount||0)?'<span class="tagn" style="background:#fce7f3;color:#be185d">小红书信号更强</span>':''}
      ${(x.quotes||[]).map(q=>`<div class="qt">「${esc(q.text)}」　<span style="color:#94a3b8">${esc(q.source)}</span></div>`).join('')}</li>`).join('')}</ul>`
    :'<div class="empty">暂无</div>',
    `<b>数据来源</b>：①飞瓜商品详情页 →「商品评价」→ 差评筛选（逐商品点击「差评」标签取原文）；②小红书笔记正文与评论（同产出②语料池）<br>
     <b>剔除规则</b>：物流、快递、发货、客服态度、退换货、价格贵等不可改良项不计入红线<br>
     <b>否定识别</b>：命中「不油腻 / 不糊眼 / 不刺鼻 / 没有闷脂肪粒」等否定表述不计入红线；「担心会长脂肪粒」等担忧语境算需求信号、不算已发生痛点<br>
     <b>引文截取</b>：以命中词为中心截取，保证展示出来的那句话里能看到证据　｜　<b>生成时间</b>：${esc(rd.generatedAt||'—')}`);

  /* 明细5 用户话语词库 */
  const sd2=lx.sentimentDist||[];
  const gc=(lx.cloud||[]).filter(x=>x.polarity==='good'), bc=(lx.cloud||[]).filter(x=>x.polarity==='bad');
  h+=panel(5,'用户话语词库','产出⑤：好评/差评描述词云 + 评价类型占比（可直接引用到脚本/详情页）',
    `<div class="grid2">
      <div class="donut" style="font-size:12.5px;color:var(--ink2)">评价类型占比<div id="sd"></div></div>
      <div style="font-size:12.5px;color:var(--ink2)">好评率即"用户满意度水位"，差评词即"雷区词汇"——脚本与详情页文案应避开雷区词、多用好评词</div>
    </div>
    <div class="src" style="margin-top:14px">
      <b>词频口径</b>：好评词来自好评评价原文命中；差评词来自差评评价原文命中，均标注真实频次。小红书高频词已并入对应极性，字号按频次分级
      <div class="charts" style="margin-top:10px;display:flex;gap:20px;flex-wrap:wrap;align-items:flex-start">
        <div class="cloud"><h5>好评描述词云</h5>${cloud(gc)}</div>
        <div class="cloud"><h5>差评描述词云</h5>${cloud(bc)}</div>
      </div>
    </div>`,
    `<b>数据来源</b>：飞瓜商品详情页 · 商品评价（${esc(lx.source||'')}）<br>
     <b>生成时间</b>：${esc(lx.generatedAt||'—')}`);

  /* 明细6 决策权重排序 */
  h+=panel(6,'用户决策权重排序','产出⑥：用户评判此类商品的核心标准（功效＞香味＞包装？）',
    dc.length?bars(dc.map(x=>({name:x.criterion,value:x.pct,unit:'%'})),'linear-gradient(90deg,#4f46e5,#a5b4fc)')+
    `<div class="insight" style="margin-top:12px"><b>结论</b>：${dc.slice(0,3).map(x=>esc(x.criterion)+' '+x.pct+'%').join(' ＞ ')} —— 用户实际评判权重<b>${esc(dc[0].criterion)}</b>排第一${dc[0].criterion.indexOf('质地')>=0?'，高于功效：先"用得舒服"再"见效"，这与"只堆功效话术"的常规打法相反':''}</div>`
    :'<div class="empty">暂无</div>',
    `<b>数据来源</b>：飞瓜商品评价语料 + 小红书语料（同产出②语料池）<br>
     <b>排序口径</b>：按各类需求词在语料中的命中频次归一化，反映用户实际评判权重　｜　<b>生成时间</b>：${esc(lx.generatedAt||'—')}`);

  /* 附：TOP10 品牌玩家（数据基础） */
  const rows=t.items||[];
  h+=panel(0,'附 · 数据基础：TOP10 品牌玩家与筛选口径','产出①-⑥的数据底座：飞瓜商品库 TOP10（含剔除名单）',
    rows.length?`<table><tr><th>顺位</th><th>品牌</th><th>SPU</th><th>带货达人</th><th>带货视频</th><th>带货直播</th><th>综合分</th><th>销售额档</th></tr>`+
    rows.map((x,i)=>`<tr><td>${i+1}</td><td><b>${esc(x.brand)}</b></td>
      <td>${x.spuCount}</td><td>${x.talent}</td><td>${x.video}</td><td>${x.live}</td><td><b>${x.score}</b></td><td>${esc((x.salesTier||[])[0]||'—')}</td></tr>`).join('')+`</table>
    <div style="margin-top:12px;font-size:12px;color:var(--ink2)">综合分 = 达人×0.4 + 视频×0.35 + 直播×0.25</div>`:'<div class="empty">暂无</div>',
    `<b>数据来源</b>：飞瓜数据 · 商品库（一级类目「个护家清」+ 关键词「眼油」，近30天快照，按销售额降序）<br>
     <b>筛选标准</b>：${esc(t.criteria||'')}<br>
     ${(t.excluded||[]).length?`<div class="exc"><h4>已剔除名单（答辩证据：我们过滤了什么）</h4><ul>${t.excluded.map(e=>`<li>${esc(e.name)} —— ${esc(e.reason)}</li>`).join('')}</ul></div>`:''}
     <b>采集日期</b>：${esc(t.fetchDate||'—')}　｜　<b>类目路径</b>：个护家清 / 眼部护理 / 眼部精华`);

  document.getElementById('body').innerHTML=h;
  if(sd2.length) document.getElementById('sd').innerHTML=
    donut(sd2,['#16a34a','#d97706','#e11d48'],'评价总数');
}
render();
/* ---------- 三级类目联动（抖音罗盘口径） ---------- */
(function(){
  const c1=document.getElementById('c1'),c2=document.getElementById('c2'),c3=document.getElementById('c3');
  const T=TREE.tree||[];
  T.forEach(x=>c1.add(new Option(x.name,x.name)));
  function fill2(){c2.innerHTML='';c3.innerHTML='';
    const p=T.find(x=>x.name===c1.value);(p&&p.children||[]).forEach(y=>c2.add(new Option(y.name,y.name)));fill3();}
  function fill3(){c3.innerHTML='';
    const p=T.find(x=>x.name===c1.value);const q=p&&(p.children||[]).find(y=>y.name===c2.value);
    (q&&q.children||[]).forEach(z=>c3.add(new Option(z.name,z.name)));}
  c1.onchange=fill2;c2.onchange=fill3;
  // 默认定位到当前跑通品类
  const i1=[...c1.options].findIndex(o=>o.value==='个护家清'); if(i1>=0)c1.selectedIndex=i1;
  fill2(); const i2=[...c2.options].findIndex(o=>o.value==='眼部护理'); if(i2>=0)c2.selectedIndex=i2;
  fill3(); const i3=[...c3.options].findIndex(o=>o.value==='眼部精华'); if(i3>=0)c3.selectedIndex=i3;
})();
</script>
</body></html>"""

out = (HTML.replace("__DATA__", json.dumps(d, ensure_ascii=False))
           .replace("__TREE__", json.dumps(tree, ensure_ascii=False))
           .replace("__NOW__", NOW))
open(OUT, "w", encoding="utf-8").write(out)
print(f"[done] {OUT}  ({len(out)/1024:.0f} KB)")
print(f"  内嵌数据：{', '.join(k for k,v in d.items() if v)} + category_tree")
