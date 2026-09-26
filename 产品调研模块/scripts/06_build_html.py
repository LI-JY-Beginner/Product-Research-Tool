# -*- coding: utf-8 -*-
"""B9 · 建页：由 data/*.json 生成自包含的两页 HTML
产出: 产品调研模块/品类聚合视图.html（跨商品汇总，附属视图） + 产品调研模块/deep.html
注意：入口页 index.html 由 10_build_pages.py 生成（商品卡墙），本脚本不得覆盖它。
"""
import os, sys, json, re, html, collections, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
import pcommon as P

DATA = os.path.join(BASE, "data")
OUT = BASE
A = json.load(open(os.path.join(DATA, "analysis.json"), encoding="utf-8"))
cards = json.load(open(os.path.join(DATA, "cards.json"), encoding="utf-8"))
deep = json.load(open(os.path.join(DATA, "deep.json"), encoding="utf-8"))
top30 = json.load(open(os.path.join(DATA, "top30.json"), encoding="utf-8"))

NOW = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
RANGE = "%s ~ %s" % (P._dcode(29), P._dcode(0))
RANGE_D = "%s ~ %s" % (datetime.datetime.strptime(P._dcode(29), "%Y%m%d").strftime("%Y-%m-%d"),
                       datetime.datetime.strptime(P._dcode(0), "%Y%m%d").strftime("%Y-%m-%d"))

E = lambda s: html.escape(str(s if s is not None else ""))

CSS = """
:root{--bg:#f5f6fa;--card:#fff;--ink:#1e293b;--ink2:#64748b;--line:#e2e8f0;
--pri:#4f46e5;--pri-soft:#eef2ff;--good:#0d9488;--bad:#e11d48;--warn:#d97706;--warn-bg:#fffbeb;}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font:14px/1.65 "Microsoft YaHei","PingFang SC",system-ui,sans-serif;padding-bottom:50px}
.wrap{max-width:1180px;margin:0 auto;padding:0 24px}
header{background:var(--card);border-bottom:1px solid var(--line);padding:14px 0;position:sticky;top:0;z-index:20}
.hd{display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.hd h1{font-size:18px}
.hd .sub{font-size:12px;color:var(--ink2)}
.badge{font-size:11px;padding:3px 9px;border-radius:12px;background:#f0fdf4;color:#16a34a;border:1px solid #bbf7d0}
.navlinks{margin-left:auto;display:flex;gap:8px}
.navlinks a{font-size:12.5px;color:var(--pri);text-decoration:none;border:1px solid #c7d2fe;background:var(--pri-soft);
  border-radius:7px;padding:5px 11px}
.navlinks a:hover{background:#e0e7ff}
main{padding:20px 0}
.sec{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin-bottom:18px}
.sec h2{font-size:16px;display:flex;align-items:center;gap:9px;margin-bottom:3px}
.sec .lead{font-size:12.5px;color:var(--ink2);margin-bottom:14px}
.src{margin-top:14px;background:#f8fafc;border:1px solid var(--line);border-left:3px solid var(--pri);border-radius:0 8px 8px 0;padding:10px 14px;font-size:12px;color:var(--ink2)}
.src b{color:var(--ink)}
table{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:6px}
th,td{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{background:#f8fafc;font-weight:600;font-size:11.5px;position:sticky;top:0}
tr:nth-child(even) td{background:#fcfdfe}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}
@media(max-width:900px){.grid2,.grid3{grid-template-columns:1fr}}
.sgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
@media(max-width:960px){.sgrid{grid-template-columns:1fr 1fr}}
@media(max-width:640px){.sgrid{grid-template-columns:1fr}}
.scard{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;cursor:pointer;transition:.15s}
.scard:hover{border-color:var(--pri);box-shadow:0 2px 10px rgba(79,70,229,.10);transform:translateY(-1px)}
.scard .st{font-size:12.5px;font-weight:700;display:flex;align-items:center;gap:7px}
.scard .st .no{background:var(--pri);color:#fff;width:19px;height:19px;border-radius:5px;display:inline-flex;align-items:center;justify-content:center;font-size:11px}
.scard .sbody{margin-top:9px}
.scard .go{font-size:11.5px;color:var(--pri);margin-top:9px;font-weight:600}
.chip{display:inline-block;margin:3px 6px 3px 0;padding:3px 10px;border-radius:14px;font-size:12.5px;background:#f1f5f9;white-space:nowrap}
.chip b{color:var(--pri);margin-left:4px;font-size:13.5px}
.chip.r{background:#fff1f2}.chip.r b{color:var(--bad)}
.chip.g{background:#f0fdf4}.chip.g b{color:var(--good)}
.chip.i{background:var(--pri-soft)}.chip.i b{color:var(--pri)}
.chip.w{background:var(--warn-bg)}.chip.w b{color:var(--warn)}
.kline{font-size:13px;margin:4px 0;line-height:1.55}
.kline b{color:var(--bad)}
.kline .em{color:var(--pri);font-weight:700}
.bar{display:flex;align-items:center;gap:9px;margin-bottom:7px;font-size:13px}
.bar .bn{min-width:18px;color:var(--ink2);font-size:12px}
.bar .bt{min-width:96px}
.bar .tk{flex:1;height:15px;background:#f1f5f9;border-radius:8px;overflow:hidden}
.bar .fl{height:100%;border-radius:8px}
.bar .bv{min-width:56px;text-align:right;font-size:12px;color:var(--ink2)}
.panel{background:var(--card);border:1px solid var(--line);border-radius:12px;margin-bottom:12px;overflow:hidden}
.ph{display:flex;align-items:center;gap:10px;padding:13px 18px;cursor:pointer;font-size:15px;font-weight:600;user-select:none}
.ph:hover{background:#f8fafc}
.ph .no{background:var(--pri);color:#fff;width:24px;height:24px;border-radius:6px;display:inline-flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;flex:none}
.ph .hint{font-size:12px;color:#94a3b8;font-weight:400;display:none}
@media(min-width:880px){.ph .hint{display:inline}}
.ph .chev{margin-left:auto;color:#94a3b8;font-size:12px;transition:.2s}
.panel.open .chev{transform:rotate(180deg)}
.pb{display:none;border-top:1px solid var(--line);padding:18px 20px}
.panel.open .pb{display:block}
.insight{background:var(--warn-bg);border:1px solid #fde68a;border-radius:8px;padding:9px 13px;font-size:12.5px;color:#92400e;margin-top:10px}
.insight li{margin-left:16px}
.tagn{font-size:10px;background:#f1f5f9;color:var(--ink2);border-radius:3px;padding:1px 5px;margin-left:5px}
.wg{color:var(--good)}.wb{color:var(--bad)}
.desc{font-size:12px;color:var(--ink);max-width:420px;word-break:break-all}
.mini{font-size:11.5px;color:var(--ink2)}
.rk{font-weight:700;color:var(--pri)}
.goods{border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin-bottom:14px;background:#fff}
.goods h3{font-size:14.5px;margin-bottom:4px;display:flex;gap:8px;align-items:baseline}
.goods h3 .rk{font-size:12px}
.gmeta{font-size:12px;color:var(--ink2);margin-bottom:8px}
footer{text-align:center;color:#94a3b8;font-size:12px;padding:14px 0}
.scrollx{overflow-x:auto}
.note{font-size:12px;color:var(--ink2);background:#f8fafc;border:1px dashed var(--line);border-radius:8px;padding:8px 12px;margin-top:8px}
.step{border-left:3px solid var(--pri);padding:6px 0 6px 12px;margin:8px 0;font-size:13px}
.step b{color:var(--pri)}
"""


def donut_js(items, colors, label):
    return "donut(%s,%s,'%s')" % (json.dumps(items, ensure_ascii=False), json.dumps(colors), label)


def bars(items, color=None):
    mx = max([i["value"] for i in items], default=1) or 1
    out = []
    for i, it in enumerate(items, 1):
        out.append('<div class="bar"><span class="bn">%d</span><span class="bt">%s</span>'
                   '<span class="tk"><span class="fl" style="width:%.1f%%;background:%s"></span></span>'
                   '<span class="bv">%s%s</span></div>'
                   % (i, E(it["name"]), it["value"] / mx * 100.0,
                      color or "linear-gradient(90deg,#4f46e5,#818cf8)",
                      E(it["value"]), E(it.get("unit", ""))))
    return "".join(out)


JS_COMMON = """
function donut(items,colors,totalLabel){
  const total=items.reduce((s,i)=>s+i.value,0)||1;const R=64,C=2*Math.PI*R;let off=0,svg='';
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
function openPanel(n){const p=document.getElementById('p'+n);if(p){if(!p.classList.contains('open'))p.classList.add('open');
  setTimeout(()=>p.scrollIntoView({behavior:'smooth',block:'start'}),60);}}
function togglePanel(n){document.getElementById('p'+n).classList.toggle('open');}
function goDeep(g){location.href='deep.html#g-'+g;}
"""


# ============================ 页面 1：总览 ============================
def build_index():
    n = A["n_top"]
    bc = A["brand_concentration"]
    cm = {x["name"]: x["avg"] for x in A["channel_mix"]}
    sm = {x["name"]: x["avg"] for x in A["selltype_mix"]}
    ps = A["price_stats"]; pr = A["praise"]; cmm = A["commission"]
    cate = A["cate_dist"]
    dur = A["dur_band"]
    hk = A["hook_dist"]

    # ---- 结论速览 6 卡 ----
    cards_html = []
    # 1
    c1 = "".join(['<span class="chip %s">%s<b>%s%%</b></span>' % (
        "i" if i == 0 else "", E(x["name"]), x["pct"]) for i, x in enumerate(cate[:5])])
    cards_html.append(("品类盘面：谁在卖、卖什么价",
        '<div class="mb">%s</div>'
        '<div class="kline">TOP30 集中在 <span class="em">眼膜+眼霜</span>（合计 %.1f%%），'
        '眼部精华仅 %.1f%%</div>'
        '<div class="kline">推算价格中位 <b>%.0f 元</b>（区间 %.0f–%.0f 元，n=%d）；'
        '佣金均值 <b>%.2f%%</b>（最高 %.0f%%）</div>'
        '<div class="kline">好评率均值 <b>%.2f%%</b>（最低 %.2f%%）</div>'
        % (c1, cate[0]["pct"] + cate[1]["pct"] if len(cate) > 1 else 0,
           next((x["pct"] for x in cate if x["name"] == "眼部精华"), 0),
           ps["median"] or 0, ps["min"] or 0, ps["max"] or 0, ps["n"],
           cmm["avg"] or 0, cmm["max"] or 0, pr["avg"] or 0, pr["min"] or 0)))
    # 2
    cards_html.append(("竞争格局：没有垄断者",
        '<div class="kline"><span class="em">%d 个品牌</span>分食 TOP30，'
        'TOP3 仅占 <b>%.1f%%</b>、TOP5 占 <b>%.1f%%</b></div>'
        '<div class="kline">品龄两极：<b>%.0f%%</b> 是 6 个月内新品，'
        '<b>%.0f%%</b> 是 2 年以上老品</div>'
        '<div class="kline">→ 新品牌靠新品打切入、老品靠存量续命，'
        '<span class="em">窗口仍开着</span></div>'
        % (bc["n_brands"], bc["top3_share"], bc["top5_share"],
           next((x["pct"] for x in A["age_dist"] if x["name"] == "新品(≤6个月)"), 0),
           next((x["pct"] for x in A["age_dist"] if x["name"] == "2年以上"), 0))))
    # 3
    cards_html.append(("渠道真相：这是直播品类",
        '<div class="kline">销售额渠道结构：<b>直播 %.1f%%</b> ／ 视频 %.1f%% ／ 商品卡 %.1f%%</div>'
        '<div class="kline">带货方式：品牌自营 <b>%.1f%%</b> ＞ 达人推广 %.1f%%</div>'
        '<div class="kline">→ 眼油不是「铺视频就能起量」的品类，'
        '<span class="em">自播/店播是主力盘</span></div>'
        % (cm.get("直播", 0), cm.get("视频", 0), cm.get("商品卡", 0),
           sm.get("品牌自营", 0), sm.get("达人推广", 0))))
    # 4
    best_dur = max(dur, key=lambda x: x["avg_gmv"]) if dur else {"name": "-", "avg_gmv": 0}
    cards_html.append(("爆款内容公式",
        '<div class="kline">%d 条带货视频：开头钩子以 <b>痛点直击</b> 为主（%.1f%%），'
        '其次效果承诺 %.1f%%、权威背书 %.1f%%</div>'
        '<div class="kline">时长效率倒挂：<b>%s</b> 单位产出最高（均值 %s），'
        '2 分钟以上最低（均值 %s）</div>'
        '<div class="kline">→ 短、狠、直接给结论，别拍长测评</div>'
        % (A["n_videos"],
           next((x["pct"] for x in hk if x["name"] == "痛点直击"), 0),
           next((x["pct"] for x in hk if x["name"] == "效果承诺"), 0),
           next((x["pct"] for x in hk if x["name"] == "权威背书"), 0),
           E(best_dur["name"]), fmt_money(best_dur["avg_gmv"]),
           fmt_money(next((x["avg_gmv"] for x in dur if x["name"] == "2分钟以上"), 0)))))
    # 5
    fb = A["fan_band"]
    rates = [(d.get("concentration") or {}).get("top5", [{}])[0].get("rate", "")
             for d in A["deep"].values() if (d.get("concentration") or {}).get("top5")]
    top_rate = max(rates) if rates else "—"
    cards_html.append(("达人矩阵：双极高效",
        '<div class="kline">%d 位达人样本：粉丝 <b>1–10 万</b> 与 <b>50 万以上</b> 单位产出最高</div>'
        '<div class="kline">小于 1 万的尾部达人数量最多（%d 条视频）但均值最低（%s）</div>'
        '<div class="kline">头部集中度极高：单品 TOP5 达人最高吃掉 <b>%s</b> 销售额</div>'
        % (A["n_talents"],
           next((x["n"] for x in fb if x["name"] == "小于1万"), 0),
           fmt_money(next((x["avg_gmv"] for x in fb if x["name"] == "小于1万"), 0)),
           E(top_rate))))
    # 6
    cards_html.append(("研发与选品建议",
        '<div class="kline">价格锚：<b>100–200 元</b>主销带；佣金 <b>5–10%%</b> 才有达人愿意带</div>'
        '<div class="kline">形态：眼膜/眼霜是走量主力，眼油（眼部精华）是差异化切口</div>'
        '<div class="kline">卖点：功效词占词云 <b>%.1f%%</b>，部位词 %.1f%%，成分词仅 %.1f%% '
        '→ <span class="em">说功效+说部位，别堆成分</span></div>'
        % (next((x["pct"] for x in A["wordcloud_cat"] if x["name"] == "功效"), 0),
           next((x["pct"] for x in A["wordcloud_cat"] if x["name"] == "部位"), 0),
           next((x["pct"] for x in A["wordcloud_cat"] if x["name"] == "成分"), 0))))

    sc = ""
    for i, (t, body) in enumerate(cards_html, 1):
        sc += ('<div class="scard" onclick="openPanel(%d)"><div class="st"><span class="no">%d</span>%s</div>'
               '<div class="sbody">%s</div><div class="go">展开明细 ➀ ➝</div></div>' % (i, i, E(t), body))

    # ---- 明细 6 栏目 ----
    panels = []

    # ① TOP30 卡片明细
    rows = []
    for i, r in enumerate(A["rows"], 1):
        rows.append("<tr><td class='rk'>%d</td><td style='max-width:320px'>%s</td><td>%s</td><td>%s</td>"
                    "<td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                    "<td>%s</td></tr>"
                    % (i, E((r.get("title") or "")[:46]), E(r.get("brand") or "—"), E(r.get("shop") or "—"),
                       E(r.get("cate") or "—"), E(r.get("onsale_date") or "—"),
                       ("￥%.0f" % r["price_est"]) if r.get("price_est") else "—",
                       E(r.get("commission_rate") or "—"), E(r.get("praise") or "—"),
                       E(r.get("销售额") or r.get("sales_tier") or "—"), E(r.get("销量") or r.get("volume_tier") or "—"),
                       E(r.get("带货视频") if r.get("带货视频") else r.get("videos") or "—"),
                       E(r.get("带货达人") if r.get("带货达人") else r.get("talents") or "—")))
    tbl = ("<div class='scrollx'><table><tr><th>#</th><th>商品</th><th>品牌</th><th>小店</th><th>分类</th>"
           "<th>上架</th><th>推算价格</th><th>佣金率</th><th>好评</th><th>销售额</th><th>销量</th>"
           "<th>带货视频</th><th>带货达人</th></tr>%s</table></div>" % "".join(rows))
    panels.append(("TOP30 商品卡片明细", "30 条 · 品牌/店铺/分类/上架/价格/佣金/好评/量级",
                   tbl + '<div class="insight"><ul>'
                   '<li>推算价格 = 佣金金额 ÷ 佣金率（飞瓜详情页只给佣金，不直接给价格），n=%d</li>'
                   '<li>销售额/销量为飞瓜档位口径（如 100w+ / 10w+），不是精确值</li></ul></div>' % ps["n"],
                   "飞瓜商品销售榜（个护家清 / 月榜=近30天 / 8 个眼部关键词）→ 商品详情页概览 · %s" % RANGE_D))

    # ② 竞争格局
    bt = [{"name": x["name"], "value": x["n"]} for x in A["brand_top"][:10]]
    g2 = ('<div class="grid2"><div><h4 style="font-size:13px;margin-bottom:6px">细分类目分布</h4>'
          + bars([{"name": x["name"], "value": x["n"], "unit": "款"} for x in A["cate_dist"]],
                 "linear-gradient(90deg,#0d9488,#5eead4)")
          + '</div><div><h4 style="font-size:13px;margin-bottom:6px">品龄分布</h4>'
          + bars([{"name": x["name"], "value": x["n"], "unit": "款"} for x in A["age_dist"]],
                 "linear-gradient(90deg,#d97706,#fcd34d)")
          + '</div></div>'
          + '<h4 style="font-size:13px;margin:14px 0 6px">品牌上榜款数 TOP10（共 %d 个品牌）</h4>' % bc["n_brands"]
          + bars(bt, "linear-gradient(90deg,#4f46e5,#818cf8)")
          + '<div class="insight"><ul><li>品牌高度分散：TOP3 只占 %.1f%%，说明<b>没有绝对头部</b>，'
            '白牌/新品牌仍有进入空间</li>'
            '<li>新品（≤6 个月）占 %.0f%%，说明这个类目<b>上新迭代快</b>，靠新品冲榜是可行路径</li></ul></div>'
            % (bc["top3_share"],
               next((x["pct"] for x in A["age_dist"] if x["name"] == "新品(≤6个月)"), 0)))
    panels.append(("竞争格局与品牌集中度", "23 个品牌 / TOP3 仅 26.7% / 品龄两极", g2,
                   "飞瓜商品详情页「品牌/小店/上架时间」字段 + 商品销售榜分类 · %s" % RANGE_D))

    # ③ 渠道结构
    cm2 = A["channel_mix"]; sm2 = A["selltype_mix"]
    g3 = ('<div class="grid2"><div><h4 style="font-size:13px;margin-bottom:6px">销售额渠道结构（30 款均值占比）</h4>'
          + bars([{"name": x["name"], "value": x["avg"], "unit": "%"} for x in cm2],
                 "linear-gradient(90deg,#e11d48,#fb7185)")
          + '</div><div><h4 style="font-size:13px;margin-bottom:6px">带货方式结构（30 款均值占比）</h4>'
          + bars([{"name": x["name"], "value": x["avg"], "unit": "%"} for x in sm2],
                 "linear-gradient(90deg,#4f46e5,#818cf8)")
          + '</div></div>'
          + '<div class="scrollx" style="margin-top:12px"><table><tr><th>#</th><th>商品</th>'
            '<th>视频占比</th><th>直播占比</th><th>商品卡占比</th><th>自营占比</th><th>达人推广占比</th></tr>'
          + "".join(["<tr><td class='rk'>%d</td><td style='max-width:300px'>%s</td>%s%s%s%s%s</tr>"
                     % (i, E((r.get("title") or "")[:40]),
                        *[td_share(r.get("channel"), n) for n in ("视频", "直播", "商品卡")],
                        *[td_share(r.get("selltype"), n) for n in ("品牌自营", "达人推广")])
                     for i, r in enumerate(A["rows"], 1)])
          + '</table></div>'
          + '<div class="insight"><ul>'
            '<li><b>直播 %.1f%%</b> 是绝对主力 —— 眼油品类的起量盘在直播间，不在短视频</li>'
            '<li>品牌自营 %.1f%% ＞ 达人推广 %.1f%%，头部商家普遍<b>自播闭环</b></li>'
            '<li>但达人推广仍贡献三成以上，<b>达人分销是放大器不是主力</b></li></ul></div>'
            % (cm.get("直播", 0), sm.get("品牌自营", 0), sm.get("达人推广", 0)))
    panels.append(("渠道与带货方式真相", "直播 75.7% / 视频 16.8% / 自营 55.1%", g3,
                   "飞瓜商品详情页「销售渠道 / 带货方式」模块（近30天）· %s" % RANGE_D))

    # ④ 爆款视频
    tv = A["top_videos"][:15]
    vrows = "".join(["<tr><td class='rk'>%d</td><td class='desc'>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                     "<td>%s</td><td>%s</td><td>%s</td><td>%s</td><td><a href='%s' target='_blank'>抖音原视频</a></td></tr>"
                     % (i, E((v.get("desc") or "")[:80]), E(v.get("duration") or "—"),
                        E(v.get("pubTime") or "—")[:10], E(v.get("gmv") or "—"), E(v.get("volume") or "—"),
                        E(v.get("play") or "—"), E(v.get("like") or "—"), E(v.get("gpm") or "—"),
                        E(v.get("shareUrl") or "#"))
                     for i, v in enumerate(tv, 1)])
    g4 = ('<div class="grid2"><div><h4 style="font-size:13px;margin-bottom:6px">时长带 × 平均销售额档</h4>'
          + bars([{"name": x["name"], "value": int(x["avg_gmv"]), "unit": ""} for x in A["dur_band"]],
                 "linear-gradient(90deg,#4f46e5,#818cf8)")
          + '<div class="mini">柱长为该时长带视频的销售额档中位数均值（元）</div></div>'
          + '<div><h4 style="font-size:13px;margin-bottom:6px">开头钩子类型分布</h4>'
          + bars([{"name": x["name"], "value": x["n"], "unit": "条"} for x in A["hook_dist"]],
                 "linear-gradient(90deg,#0d9488,#5eead4)")
          + '</div></div>'
          + '<h4 style="font-size:13px;margin:14px 0 6px">高频话题标签 TOP15</h4><div>'
          + "".join(['<span class="chip i">#%s<b>%d</b></span>' % (E(x["name"]), x["n"])
                     for x in A["tags_top"][:15]])
          + '</div>'
          + '<h4 style="font-size:13px;margin:14px 0 6px">带货视频 TOP15（按销售额档 × 销量档排序）</h4>'
          + '<div class="scrollx"><table><tr><th>#</th><th>视频文案/标题</th><th>时长</th><th>发布</th>'
            '<th>销售额档</th><th>销量档</th><th>播放</th><th>点赞</th><th>GPM</th><th>原视频</th></tr>'
          + vrows + '</table></div>'
          + '<div class="insight"><ul><li>共 %d 条真实带货视频（TOP6 商品各取 30 条）</li>'
            '<li><b>≤30 秒</b>视频单位产出最高，2 分钟以上最低 —— 短平快完胜长测评</li></ul></div>' % A["n_videos"])
    panels.append(("爆款内容公式（%d 条真实视频）" % A["n_videos"], "时长带 / 钩子 / 标签 / TOP15 视频", g4,
                   "飞瓜商品详情页 → 带货视频列表（近30天，按销售额降序，每商品取 TOP30）· %s" % RANGE_D))

    # ⑤ 达人矩阵
    tt = A["top_talents"][:25]
    trows = "".join(["<tr><td class='rk'>%d</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                     "<td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                     % (i, E(t.get("name") or "—"), E(t.get("displayId") or "—"), E(t.get("fans") or "—"),
                        E(t.get("level") or "—"), E(t.get("cert") or "—"), E(t.get("gmv") or "—"),
                        E(t.get("volume") or "—"), E(t.get("awemeCnt") or "—"), E(t.get("liveCnt") or "—"))
                     for i, t in enumerate(tt, 1)])
    conc = []
    for gid, d in A["deep"].items():
        c = (d.get("concentration") or {})
        t5 = c.get("top5") or []
        if t5:
            conc.append("<tr><td style='max-width:280px'>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                        % (E((d.get("title") or "")[:40]), E(t5[0]["name"]), E(t5[0]["gmv"]), E(t5[0]["rate"])))
    g5 = ('<div class="grid2"><div><h4 style="font-size:13px;margin-bottom:6px">达人粉丝量级 × 平均销售额档</h4>'
          + bars([{"name": x["name"], "value": int(x["avg_gmv"]), "unit": ""} for x in A["fan_band"]],
                 "linear-gradient(90deg,#4f46e5,#818cf8)")
          + '<div class="mini">柱长为该层级达人带货视频的销售额档中位数均值（元）</div></div>'
          + '<div><h4 style="font-size:13px;margin-bottom:6px">单品 TOP1 达人销售额集中度</h4>'
          + '<div class="scrollx"><table><tr><th>商品</th><th>TOP1 达人</th><th>销售额档</th><th>占比</th></tr>'
          + "".join(conc) + '</table></div></div></div>'
          + '<h4 style="font-size:13px;margin:14px 0 6px">达人 TOP25（按销售额档排序，%d 位样本）</h4>' % A["n_talents"]
          + '<div class="scrollx"><table><tr><th>#</th><th>达人</th><th>抖音号</th><th>粉丝</th><th>等级</th>'
            '<th>认证</th><th>销售额档</th><th>销量档</th><th>带货视频</th><th>带货直播</th></tr>'
          + trows + '</table></div>'
          + '<div class="insight"><ul>'
            '<li>头部集中度惊人：TOP1 达人最高吃掉单品 <b>83.75%</b> 销售额（多为品牌自营店号）</li>'
            '<li>粉丝 <b>1–10 万</b> 与 <b>50 万以上</b> 两头效率最高，中间层性价比最低</li>'
            '<li>达人类型里「潜力达人」数量占比 <b>98%</b> 但产出集中在头部 —— 铺量不如押头部</li></ul></div>')
    panels.append(("达人矩阵与投放效率", "%d 位达人 / 粉丝层级效率 / 集中度" % A["n_talents"], g5,
                   "飞瓜商品详情页 → 带货达人列表 + 达人集中度 + 达人类型分析（近30天）· %s" % RANGE_D))

    # ⑥ 研发与选品建议
    wc = A["wordcloud_top"]
    eff = [x for x in wc if x["cat"] == "功效"][:12]
    part = [x for x in wc if x["cat"] == "部位"][:8]
    ing = [x for x in wc if x["cat"] == "成分"][:8]
    g6 = ('<div class="grid3">'
          '<div><h4 style="font-size:13px;margin-bottom:6px">功效词（占词云 %.1f%%）</h4><div>'
          % next((x["pct"] for x in A["wordcloud_cat"] if x["name"] == "功效"), 0)
          + "".join(['<span class="chip g">%s<b>%d</b></span>' % (E(x["kw"]), x["cnt"]) for x in eff])
          + '</div></div><div><h4 style="font-size:13px;margin-bottom:6px">部位词（%.1f%%）</h4><div>'
          % next((x["pct"] for x in A["wordcloud_cat"] if x["name"] == "部位"), 0)
          + "".join(['<span class="chip i">%s<b>%d</b></span>' % (E(x["kw"]), x["cnt"]) for x in part])
          + '</div></div><div><h4 style="font-size:13px;margin-bottom:6px">成分词（%.1f%%）</h4><div>'
          % next((x["pct"] for x in A["wordcloud_cat"] if x["name"] == "成分"), 0)
          + "".join(['<span class="chip w">%s<b>%d</b></span>' % (E(x["kw"]), x["cnt"]) for x in ing])
          + '</div></div></div>'
          + '<h4 style="font-size:13px;margin:14px 0 6px">研发方向与 SKU 矩阵（数据推导，非官方口径）</h4>'
          + '<div class="scrollx"><table><tr><th>维度</th><th>数据依据</th><th>建议动作</th></tr>'
          + "".join(["<tr><td><b>%s</b></td><td>%s</td><td>%s</td></tr>" % (E(a), E(b_), E(c))
                     for a, b_, c in suggest_rows(A, ps, cmm, cm, sm)])
          + '</table></div>'
          + '<div class="note">以上为基于本次 %d 个商品 / %d 条视频 / %d 位达人的数据推导建议，'
            '需结合实际供应链与合规口径复核后再落地。</div>' % (A["n_top"], A["n_videos"], A["n_talents"]))
    panels.append(("研发方向与选品建议", "价格锚 / 形态 / 卖点 / 佣金 / 渠道配速", g6,
                   "由本次采集的 TOP30 卡片层 + %d 条视频词云 + %d 位达人结构推导 · %s"
                   % (A["n_videos"], A["n_talents"], RANGE_D)))

    ph = ""
    for i, (t, hint, body, src) in enumerate(panels, 1):
        ph += ('<div class="panel" id="p%d"><div class="ph" onclick="togglePanel(%d)">'
               '<span class="no">%d</span>%s<span class="hint">%s</span><span class="chev">▼ 展开明细</span></div>'
               '<div class="pb">%s<div class="src">%s</div></div></div>' % (i, i, i, E(t), E(hint), body, E(src)))

    # 附：TOP10 品牌
    b10 = "".join(["<tr><td class='rk'>%d</td><td>%s</td><td>%s 款</td><td>%s</td></tr>"
                   % (i, E(x["name"]), x["n"], fmt_money(x["gmv_mid"]))
                   for i, x in enumerate(A["brand_top"][:10], 1)])

    html_out = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>产品调研模块 · 眼油品类 | AI全球选品平台</title>
<style>%s</style></head><body>
<header><div class="wrap"><div class="hd">
  <div><h1>产品调研模块</h1><div class="sub">AI全球选品平台 · 眼油/眼部护理品类（全品类视角，各品牌一视同仁）</div></div>
  <span class="badge">数据截至 %s</span>
  <div class="navlinks"><a href="deep.html">深度拆解页 ➝</a></div>
</div></div></header>
<main class="wrap">
<section class="sec" style="background:var(--pri-soft);border-color:#c7d2fe;padding:12px 20px">
  <div style="display:flex;gap:24px;flex-wrap:wrap;font-size:13px;align-items:baseline">
    <span>商品池 <b style="font-size:17px">%d</b> → 去重后定稿 <b style="font-size:17px">%d</b></span>
    <span>品牌 <b>%d</b></span><span>带货视频 <b>%d</b></span><span>带货达人 <b>%d</b></span>
    <span>统计周期 <b>%s</b>（近30天）</span>
    <span style="color:#64748b;font-size:12px">来源：飞瓜数据 · 商品销售榜（个护家清/月榜）+ 商品详情页</span>
  </div>
</section>
<section class="sec">
  <h2>⚡ 结论速览 · 六大产出</h2>
  <div class="lead">点任意一张卡 → 跳到下方对应编号的明细栏目</div>
  <div class="sgrid">%s</div>
</section>
<h2 style="font-size:16px;margin:22px 0 10px">📂 数据明细 · 与上方 6 个产出一一对应</h2>
%s
<section class="sec">
  <h2>🏷 附：TOP10 品牌玩家</h2>
  <div class="lead">按 TOP30 上榜款数排序；「销售额档中位数」为该品牌所有上榜商品档位中位数的合计</div>
  <div class="scrollx"><table><tr><th>#</th><th>品牌</th><th>上榜款数</th><th>销售额档中位数合计</th></tr>%s</table></div>
  <div class="src">飞瓜商品销售榜（个护家清 / 月榜 / 8 个眼部关键词）→ 商品详情页「品牌」字段 · %s</div>
</section>
</main>
<footer class="wrap">数据与展示分离 · 本页由 data/*.json 驱动 · 生成于 %s</footer>
<script>%s</script>
</body></html>""" % (CSS, NOW, A["n_pool"], A["n_top"], bc["n_brands"], A["n_videos"], A["n_talents"],
                     RANGE_D, sc, ph, b10, RANGE_D, NOW, JS_COMMON)

    open(os.path.join(OUT, "品类聚合视图.html"), "w", encoding="utf-8").write(html_out)
    return os.path.join(OUT, "品类聚合视图.html")


def toint(v):
    """词云/计数在 deep.json 里是字符串（如 '392'、'2.77%'），统一转 int"""
    if v is None:
        return 0
    if isinstance(v, (int, float)):
        return int(v)
    m = re.search(r"[\d.]+", str(v))
    try:
        return int(float(m.group(0))) if m else 0
    except Exception:
        return 0


def td_share(lst, name):
    if not lst:
        return "<td>—</td>"
    for x in lst:
        if x.get("name") == name:
            return "<td>%s</td>" % E(x.get("pct") or "—")
    return "<td>—</td>"


def fmt_money(v):
    try:
        v = float(v)
    except Exception:
        return "—"
    if v >= 10000:
        return "%.1fw" % (v / 10000.0)
    return "%.0f" % v


def suggest_rows(A, ps, cmm, cm, sm):
    eff = next((x["pct"] for x in A["wordcloud_cat"] if x["name"] == "功效"), 0)
    part = next((x["pct"] for x in A["wordcloud_cat"] if x["name"] == "部位"), 0)
    return [
        ("价格锚", "推算价格中位 %.0f 元，区间 %.0f–%.0f 元（n=%d）" % (ps["median"] or 0, ps["min"] or 0, ps["max"] or 0, ps["n"]),
         "主销 SKU 定在 100–200 元；用 50 元以下的引流小规格拉新客"),
        ("佣金机制", "佣金均值 %.2f%%，最高 %.0f%%" % (cmm["avg"] or 0, cmm["max"] or 0),
         "给到达人的佣金不要低于 5%，冲量期可拉到 10–20% 抢腰部达人"),
        ("品类形态", "眼膜 %d 款、眼霜 %d 款、眼部精华 %d 款、眼贴 %d 款" % tuple(
            next((x["n"] for x in A["cate_dist"] if x["name"] == k), 0) for k in ("眼膜", "眼霜", "眼部精华", "眼贴")),
         "眼膜/眼霜做走量盘，眼油（眼部精华）做差异化与高客单"),
        ("卖点表达", "功效词占词云 %.1f%%，部位词 %.1f%%，成分词仅 %.1f%%" % (eff, part,
            next((x["pct"] for x in A["wordcloud_cat"] if x["name"] == "成分"), 0)),
         "主打「功效+部位」组合（如紧致淡纹 × 眼周），成分做背书不做主卖点"),
        ("渠道配速", "直播 %.1f%% / 视频 %.1f%% / 商品卡 %.1f%%；自营 %.1f%% vs 达人 %.1f%%" % (
            cm.get("直播", 0), cm.get("视频", 0), cm.get("商品卡", 0), sm.get("品牌自营", 0), sm.get("达人推广", 0)),
         "先把自播/店播跑通吃住七成盘，再用达人分销做增量放大"),
        ("内容时长", "≤30 秒视频单位产出最高，2 分钟以上最低",
         "素材一律做 30–45 秒版本，长测评只留作详情页补充"),
        ("品质底线", "好评率均值 %.2f%%，最低 %.2f%%" % (A["praise"]["avg"] or 0, A["praise"]["min"] or 0),
         "好评率低于 90% 会明显拖累转化，批次质控与售后要前置"),
    ]


print("index:", build_index())


# ============================ 页面 2：深度拆解 ============================
def build_deep():
    # ---- 利益点 TOP5（功效+部位词，按 覆盖商品数×频次 排序）----
    wc = A["wordcloud_top"]
    KWMAP = {x["kw"]: x["cat"] for x in wc}
    cand = [x for x in wc if x["cat"] in ("功效", "部位")]
    for x in cand:
        x["score"] = x["cnt"] * (1 + 0.35 * (x["goods"] - 1))
    cand.sort(key=lambda x: -x["score"])
    benefit = cand[:5]

    # ---- 钩子示例（真实文案）----
    def sample(pat, n=3):
        out = []
        for v in A["top_videos"]:
            d = v.get("desc") or ""
            if re.search(pat, d[:60]):
                out.append(d)
            if len(out) >= n:
                break
        return out

    hook_ex = {
        "痛点直击": sample(r"松垮|眼纹|眼袋|黑眼圈|泪沟|鱼尾纹|显老|干纹|细纹|暗沉|浮肿"),
        "年龄锚定": sample(r"\d+岁|同龄人|40不|30不|年纪|年轻"),
        "效果承诺": sample(r"抚纹|淡纹|紧致|提拉|淡化|改善"),
        "权威背书": sample(r"代言|推荐|官方|专研|院线|医美|博士|专利|认证"),
    }

    # ---- 每个商品一个区块 ----
    blocks = []
    order = list(A["deep"].keys())
    for idx, gid in enumerate(order, 1):
        d = A["deep"][gid]
        c = cards.get(gid, {})
        title = d.get("title") or ""
        ch = {x["name"]: x["pct"] for x in (c.get("channel") or [])}
        st = {x["name"]: x["pct"] for x in (c.get("selltype") or [])}
        meta = ("<div class='gmeta'>品牌 <b>%s</b>　小店 <b>%s</b>　分类 <b>%s</b>　上架 <b>%s</b>　"
                "推算价格 <b>%s</b>　佣金 <b>%s</b>　好评 <b>%s</b></div>"
                % (E(c.get("brand") or "—"), E(c.get("shop") or "—"), E(c.get("cate") or "—"),
                   E(c.get("onsale_date") or "—"), ("￥%.0f" % c["price_est"]) if c.get("price_est") else "—",
                   E(c.get("commission_rate") or "—"), E(c.get("praise") or "—")))
        kv = "".join(['<span class="chip %s">%s<b>%s</b></span>' % (
            "i" if k == "销售额" else "", E(k), E(v))
            for k, v in (("销售额", c.get("销售额")), ("销量", c.get("销量")),
                         ("订单量", c.get("订单量")), ("浏览量", c.get("浏览量")),
                         ("转化率", c.get("转化率")), ("带货视频", c.get("带货视频")),
                         ("带货直播", c.get("带货直播")), ("带货达人", c.get("带货达人")))
            if v])
        kv2 = "".join(['<span class="chip w">%s<b>%s</b></span>' % (E(k), E(v))
                       for k, v in (("视频", ch.get("视频")), ("直播", ch.get("直播")), ("商品卡", ch.get("商品卡"))) if v])
        kv3 = "".join(['<span class="chip g">%s<b>%s</b></span>' % (E(k), E(v))
                       for k, v in (("品牌自营", st.get("品牌自营")), ("达人推广", st.get("达人推广"))) if v])

        # 达人表
        bl = (d.get("bloggers") or [])[:10]
        brows = "".join(["<tr><td class='rk'>%d</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                         "<td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                         % (i, E(b.get("name") or "—"), E(b.get("displayId") or "—"), E(b.get("fans") or "—"),
                            E(b.get("level") or "—"), E(b.get("cert") or "—"), E(b.get("gmv") or "—"),
                            E(b.get("volume") or "—"), E(b.get("awemeCnt") or "—"))
                         for i, b in enumerate(bl, 1)])
        bt = "".join(['<span class="chip i">%s<b>%s</b></span>' % (E(x["type"]), E(x["ratio"]))
                      for x in (d.get("blogger_types") or [])])
        # 词云（deep.json 里的词云没有 cat 字段，用总表 kw→cat 映射补齐）
        wmax = max([toint(x.get("cnt")) for x in (d.get("wordcloud") or [])] or [1])
        cw = "".join(['<span class="%s" style="font-size:%s;opacity:%s" title="%s 次">%s</span> '
                      % ("wg" if KWMAP.get(x.get("kw"), "其他") in ("功效", "部位") else "",
                         "%.1fpx" % (12 + 16 * min(1.0, toint(x.get("cnt")) / max(1, wmax))),
                         "%.2f" % (0.5 + 0.5 * min(1.0, toint(x.get("cnt")) / max(1, wmax))),
                         E(x.get("cnt")), E(x.get("kw")))
                      for x in (d.get("wordcloud") or [])[:40]])
        # 视频表
        vs = (d.get("videos") or [])[:20]
        if vs:
            vrows = "".join(["<tr><td class='rk'>%d</td><td class='desc'>%s</td><td>%s</td><td>%s</td>"
                             "<td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                             "<td><a href='%s' target='_blank'>抖音原视频</a></td></tr>"
                             % (i, E((v.get("desc") or "")[:70]), E(v.get("duration") or "—"),
                                E((v.get("pubTime") or "")[:10]), E(v.get("gmv") or "—"), E(v.get("volume") or "—"),
                                E(v.get("play") or "—"), E(v.get("like") or "—"), E(v.get("gpm") or "—"),
                                E(v.get("blogger") or "—"), E(v.get("fans") or "—"), E(v.get("shareUrl") or "#"))
                             for i, v in enumerate(vs, 1)])
            vtbl = ("<div class='scrollx'><table><tr><th>#</th><th>视频文案/标题</th><th>时长</th><th>发布</th>"
                    "<th>销售额档</th><th>销量档</th><th>播放</th><th>点赞</th><th>GPM</th><th>达人</th>"
                    "<th>粉丝</th><th>原视频</th></tr>%s</table></div>" % vrows)
            assert vrows.count("<tr>") == len(vs)
        else:
            vtbl = ('<div class="note">该商品近30天 <b>无带货视频</b>（带货视频 0 / 直播 3 / 达人 1）'
                    '—— 属于纯商品卡/自营驱动的品，短视频不是它的起量路径。</div>')

        blocks.append(
            '<div class="goods" id="g-%s"><h3><span class="rk">%d</span>%s</h3>%s'
            '<div style="margin:6px 0">%s</div><div style="margin:6px 0">%s</div><div>%s</div>'
            '<div class="grid2" style="margin-top:12px">'
            '<div><h4 style="font-size:13px;margin-bottom:6px">带货达人 TOP10（共 %s 位）</h4>'
            '<div class="scrollx"><table><tr><th>#</th><th>达人</th><th>抖音号</th><th>粉丝</th><th>等级</th>'
            '<th>认证</th><th>销售额档</th><th>销量档</th><th>带货视频</th></tr>%s</table></div>'
            '<div style="margin-top:6px">达人类型分布：%s</div></div>'
            '<div><h4 style="font-size:13px;margin-bottom:6px">视频内容词云 TOP40</h4>'
            '<div style="padding:6px 2px;line-height:1.9">%s</div></div></div>'
            '<h4 style="font-size:13px;margin:12px 0 6px">带货视频 TOP20（按销售额档降序，共 %s 条）</h4>%s'
            '</div>'
            % (gid[:12], idx, E(title[:60]), meta, kv, kv2, kv3,
               E(d.get("bloggers_total") or "—"), brows, bt or "—", cw or "—",
               E(d.get("videos_total") or 0), vtbl))

    # ---- 4 段时间轴 × 镜头五要素 A 级模板 ----
    dur = A["dur_band"]
    d15 = next((x for x in dur if x["name"] == "≤15秒"), {})
    d30 = next((x for x in dur if x["name"] == "16-30秒"), {})
    d60 = next((x for x in dur if x["name"] == "31-60秒"), {})
    d120 = next((x for x in dur if x["name"] == "1-2分钟"), {})
    dlong = next((x for x in dur if x["name"] == "2分钟以上"), {})
    segs = [
        ("0–3 秒 · 钩子", "特写 / 怼脸",
         "眼周局部特写（眼纹·眼袋·黑眼圈），或素颜前后对比分屏",
         "痛点直击 %.1f%% 为主：直接点名眼部问题；年龄锚定 %.1f%% 次之（「40 不显老」「同龄人」）" % (
             next((x["pct"] for x in A["hook_dist"] if x["name"] == "痛点直击"), 0),
             next((x["pct"] for x in A["hook_dist"] if x["name"] == "年龄锚定"), 0)),
         "大字痛点词压屏", "产品本体 / 素颜出镜 / 镜子"),
        ("3–10 秒 · 痛点放大", "中景 / 半身",
         "手指点按眼周讲解位置，配合素颜特写",
         "部位词占词云 %.1f%%：眼周·眼纹·眼袋·泪沟·鱼尾纹逐个点名" % (
             next((x["pct"] for x in A["wordcloud_cat"] if x["name"] == "部位"), 0)),
         "部位标注箭头 + 关键词字幕", "镜子 / 棉签 / 素颜"),
        ("10–25 秒 · 证据与演示", "近景 / 手法特写",
         "上脸手法演示：取量—点涂—按摩吸收，给质地特写",
         "成分词仅 %.1f%%：PDRN / 胶原 / 胜肽 / 咖啡因做背书一句带过，不要堆成分" % (
             next((x["pct"] for x in A["wordcloud_cat"] if x["name"] == "成分"), 0)),
         "成分名 + 质地词（好吸收·不油腻）", "产品 + 按摩头/滚珠"),
        ("25–40 秒 · 转化收口", "中景 / 口播",
         "效果回看 + 机制口播（拍一发二/赠品/限量）",
         "效果承诺 %.1f%% + 权威背书 %.1f%%：明星同款·官方旗舰·代言人" % (
             next((x["pct"] for x in A["hook_dist"] if x["name"] == "效果承诺"), 0),
             next((x["pct"] for x in A["hook_dist"] if x["name"] == "权威背书"), 0)),
         "机制字幕 + 下单引导箭头", "礼盒 / 赠品堆头 / 手机下单画面"),
    ]
    seg_html = "".join([
        '<div class="step"><b>%s</b>　景别：%s<div style="font-size:12.5px;margin-top:2px">'
        '画面：%s<br>口播：%s<br>字幕：%s　道具：%s</div></div>'
        % (E(a), E(b_), E(cc), E(dd), E(e), E(f)) for a, b_, cc, dd, e, f in segs])

    # ---- 话术词库 ----
    bycat = collections.defaultdict(list)
    for x in wc:
        bycat[x["cat"]].append(x)
    lex_html = ""
    for k in ("功效", "部位", "成分", "人群", "场景", "情绪"):
        v = bycat.get(k, [])
        if not v:
            continue
        lex_html += ('<div style="margin-bottom:8px"><b style="font-size:12.5px">%s</b>（%d 词，合计 %d 次）<div>'
                     % (E(k), len(v), sum(x["cnt"] for x in v))
                     + "".join(['<span class="chip %s">%s<b>%d</b></span>' % (
                         "g" if k == "功效" else ("i" if k == "部位" else ("w" if k == "成分" else "")),
                         E(x["kw"]), x["cnt"]) for x in v[:20]])
                     + '</div></div>')

    ben_html = "".join([
        '<div class="step"><b>%d. %s</b>　%s 次提及 · 覆盖 %d/%d 个深度样本商品</div>'
        % (i, E(b_["kw"]), b_["cnt"], b_["goods"], len(order)) for i, b_ in enumerate(benefit, 1)])

    ctr = [
        ("开头 3 秒必须出现眼部问题词", "痛点直击占 %.1f%%，是所有钩子类型里最高的" % (
            next((x["pct"] for x in A["hook_dist"] if x["name"] == "痛点直击"), 0))),
        ("总时长压到 30–45 秒", "≤15 秒均值 %s、16–30 秒 %s，都高于 31–60 秒（%s）与 2 分钟以上（%s）" % (
            fmt_money(d15.get("avg_gmv", 0)), fmt_money(d30.get("avg_gmv", 0)),
            fmt_money(d60.get("avg_gmv", 0)), fmt_money(dlong.get("avg_gmv", 0)))),
        ("给结论不给过程", "效果承诺类开头占 %.1f%%，长测评（2 分钟以上）单位产出最低" % (
            next((x["pct"] for x in A["hook_dist"] if x["name"] == "效果承诺"), 0))),
        ("挂话题标签要带品类词", "高频标签 TOP：%s" % "、".join(
            ["#" + x["name"] for x in A["tags_top"][:6]])),
        ("用素颜/前后对比做视觉锤", "部位词占词云 %.1f%%，视觉化部位问题最能拉停留" % (
            next((x["pct"] for x in A["wordcloud_cat"] if x["name"] == "部位"), 0))),
    ]
    ctr_html = "".join(['<div class="step"><b>%s</b>　%s</div>' % (E(a), E(b_)) for a, b_ in ctr])

    hx = "".join(['<div style="margin-bottom:6px"><b style="font-size:12.5px">%s</b>（%.1f%%）<div class="mini">%s</div></div>'
                  % (E(k), next((x["pct"] for x in A["hook_dist"] if x["name"] == k), 0),
                     "<br>".join(E(x[:70]) for x in v) or "—")
                  for k, v in hook_ex.items()])

    body = """
<section class="sec">
  <h2>🎬 爆款视频结构模板（4 段 × 镜头五要素）</h2>
  <div class="lead">基于 %d 条真实带货视频的时长分布、开头钩子分布与内容词云推导，非逐帧观看所得</div>
  %s
  <div class="insight"><ul>
    <li>推荐总时长 <b>30–45 秒</b>：≤30 秒视频单位产出最高（均值 %s / %s），2 分钟以上最低（%s）</li>
    <li>镜头五要素按「景别 / 画面 / 口播 / 字幕 / 道具」五列落地，拍摄时逐项对表</li>
  </ul></div>
  <div class="src">飞瓜商品详情页 → 带货视频列表（近30天，按销售额降序，TOP6 商品各 30 条）+ 视频内容词云 · %s</div>
</section>
<section class="sec">
  <h2>🗣 话术词库（按语义分类）</h2>
  <div class="lead">直接取自 %d 条视频的内容词云，按功效/部位/成分/人群/场景/情绪归类，可直接喂给脚本撰写</div>
  %s
  <div class="src">飞瓜商品详情页 → 视频内容词云（GetAwemeMarketingKeyWordList）· %s</div>
</section>
<section class="sec">
  <h2>🎯 利益点 TOP5 与 CTR 要素</h2>
  <div class="grid2">
    <div><h4 style="font-size:13px;margin-bottom:6px">利益点 TOP5（频次 × 覆盖商品数加权）</h4>%s</div>
    <div><h4 style="font-size:13px;margin-bottom:6px">提升 CTR 的 5 个要素</h4>%s</div>
  </div>
  <h4 style="font-size:13px;margin:14px 0 6px">开头钩子真实文案示例</h4>%s
  <div class="src">飞瓜带货视频文案（desc 字段）· %s</div>
</section>
<h2 style="font-size:16px;margin:22px 0 10px">📦 深度样本商品拆解（%d 个）</h2>
%s
""" % (A["n_videos"], seg_html,
       fmt_money(d15.get("avg_gmv", 0)), fmt_money(d30.get("avg_gmv", 0)), fmt_money(dlong.get("avg_gmv", 0)),
       RANGE_D,
       A["n_videos"], lex_html, RANGE_D,
       ben_html, ctr_html, hx, RANGE_D,
       len(order), "".join(blocks))

    html_out = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>深度拆解 · 产品调研模块 | AI全球选品平台</title>
<style>%s</style></head><body>
<header><div class="wrap"><div class="hd">
  <div><h1>深度拆解 · 产品调研模块</h1><div class="sub">眼油/眼部护理品类 · TOP6 样本商品的视频 / 达人 / 词云拆解（各品牌一视同仁）</div></div>
  <span class="badge">数据截至 %s</span>
  <div class="navlinks"><a href="index.html">⬅ 返回商品卡墙</a><a href="品类聚合视图.html">附件：品类聚合视图</a></div>
</div></div></header>
<main class="wrap">
<section class="sec" style="background:var(--pri-soft);border-color:#c7d2fe;padding:12px 20px">
  <div style="display:flex;gap:24px;flex-wrap:wrap;font-size:13px;align-items:baseline">
    <span>深度样本 <b style="font-size:17px">%d</b> 个商品</span>
    <span>带货视频 <b>%d</b> 条</span><span>带货达人 <b>%d</b> 位</span>
    <span>统计周期 <b>%s</b>（近30天）</span>
    <span style="color:#64748b;font-size:12px">来源：飞瓜数据 · 商品详情页（带货视频/带货达人/内容词云）</span>
  </div>
</section>
%s
</main>
<footer class="wrap">数据与展示分离 · 本页由 data/*.json 驱动 · 生成于 %s</footer>
<script>%s</script>
</body></html>""" % (CSS, NOW, len(order), A["n_videos"], A["n_talents"], RANGE_D, body, NOW, JS_COMMON)

    p = os.path.join(OUT, "deep.html")
    open(p, "w", encoding="utf-8").write(html_out)
    return p


print("deep:", build_deep())
