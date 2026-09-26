# -*- coding: utf-8 -*-
"""B9' · 单品两级页面（用户 2026-09-26 新要求）
  第 1 屏 = 购物软件式「商品卡墙」——一个具体商品链接一张卡
  第 2 屏 = 点开某张卡后的「该链接单品详情页」——速览卡 + 具体数据来源 + 该链接挖到的数据
产出: index.html  +  product/p01..pNN.html
"""
import os, sys, json, re, html, shutil, datetime, collections

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
import pcommon as P

DATA = os.path.join(BASE, "data")
PROD = os.path.join(BASE, "product")
os.makedirs(PROD, exist_ok=True)

cards = json.load(open(os.path.join(DATA, "cards.json"), encoding="utf-8"))
deep = json.load(open(os.path.join(DATA, "deep.json"), encoding="utf-8")) if os.path.exists(
    os.path.join(DATA, "deep.json")) else {}
try:
    A = json.load(open(os.path.join(DATA, "analysis.json"), encoding="utf-8"))
except Exception:
    A = {}

NOW = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
RANGE_D = None
try:
    RANGE_D = "%s ~ %s" % (datetime.datetime.strptime(P._dcode(29), "%Y%m%d").strftime("%Y-%m-%d"),
                           datetime.datetime.strptime(P._dcode(0), "%Y%m%d").strftime("%Y-%m-%d"))
except Exception:
    pass

E = lambda s: html.escape("" if s is None else str(s))


# ---------------- 数值工具 ----------------
def numw(s):
    """'344.0w' / '1.2w' / '2632' / '50w-100w' → float"""
    if s is None:
        return 0.0
    s = str(s).strip().replace(",", "")
    if not s or s in ("--", "-"):
        return 0.0
    m = re.search(r"([\d.]+)\s*([w万]?)", s)
    if not m:
        return 0.0
    v = float(m.group(1))
    if m.group(2):
        v *= 10000
    return v


def numrate(s):
    """'15%-20%' → 17.5 ; '30%+' → 30 ; '0-5%' → 2.5"""
    if not s:
        return 0.0
    s = str(s)
    m = re.search(r"([\d.]+)\s*%", s)
    if not m:
        return 0.0
    lo = float(m.group(1))
    m2 = re.search(r"[-~]\s*([\d.]+)\s*%", s)
    hi = float(m2.group(1)) if m2 else lo
    return (lo + hi) / 2


def tier(s):
    try:
        return P.tier_mid(str(s))
    except Exception:
        return 0.0


def pct(s):
    try:
        return float(str(s).replace("%", ""))
    except Exception:
        return 0.0


def sortkey(c):
    return (c.get("榜_rank") or 999,)


items = []
for gid, c in cards.items():
    c = dict(c)
    c["gid"] = gid
    items.append(c)
items.sort(key=sortkey)


def has_deep(gid):
    d = deep.get(gid) or {}
    return bool(d.get("videos") or d.get("bloggers") or d.get("wordcloud") or d.get("attr_text"))


def cover_of(gid):
    """卡面图：用该链接 TOP1 带货视频封面（已本地化，见 scripts/09_fetch_images.py）"""
    p = os.path.join(BASE, "assets", "covers", gid + ".jpg")
    return "assets/covers/%s.jpg" % gid if os.path.exists(p) else ""


def vimg(v, pre="../"):
    """视频缩略图：优先本地化文件，否则回落到远程 URL"""
    aw = v.get("awemeId")
    p = os.path.join(BASE, "assets", "video", "%s.jpg" % aw) if aw else None
    if p and os.path.exists(p):
        return pre + "assets/video/%s.jpg" % aw
    return v.get("cover") or ""


NDEEP = sum(1 for c in items if has_deep(c["gid"]))
NCOV = sum(1 for c in items if cover_of(c["gid"]))

# 每个商品的页面文件名（按排名序）
pagename = {}
for i, c in enumerate(items, 1):
    pagename[c["gid"]] = "p%02d.html" % i
rank_no = {}
for i, c in enumerate(items, 1):
    rank_no[c["gid"]] = i

# ---------------- 公共 CSS / JS ----------------
CSS = """
:root{--bg:#f4f5f9;--card:#fff;--ink:#16202f;--ink2:#6b7a90;--ink3:#9aa7b8;--line:#e6eaf1;
--pri:#4f46e5;--pri-soft:#eef2ff;--price:#e0245e;--good:#0d9488;--warn:#d97706;--gold:#f59e0b;}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font:14px/1.6 "Microsoft YaHei","PingFang SC",system-ui,sans-serif;padding-bottom:60px}
.wrap{max-width:1280px;margin:0 auto;padding:0 22px}
header{background:var(--card);border-bottom:1px solid var(--line);padding:12px 0;position:sticky;top:0;z-index:30;box-shadow:0 1px 6px rgba(20,30,50,.04)}
.hd{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.logo{font-size:19px;font-weight:700;letter-spacing:.5px}
.logo em{color:var(--pri);font-style:normal}
.hd .sub{font-size:12px;color:var(--ink2)}
.pill{font-size:11px;padding:3px 9px;border-radius:11px;background:var(--pri-soft);color:var(--pri);border:1px solid #dbe0fb}
.pill.g{background:#ecfdf5;color:#047857;border-color:#a7f3d0}
.pill.o{background:#fff7ed;color:#c2410c;border-color:#fed7aa}
.navlinks{margin-left:auto;display:flex;gap:8px;flex-wrap:wrap}
.navlinks a{font-size:12.5px;color:var(--pri);text-decoration:none;border:1px solid #c7d2fe;background:var(--pri-soft);border-radius:7px;padding:5px 11px}
.navlinks a:hover{background:#e0e7ff}
main{padding:18px 0}
.notice{background:#fffbeb;border:1px solid #fde68a;color:#92400e;border-radius:10px;padding:10px 14px;font-size:12.5px;margin-bottom:14px}
a{color:var(--pri)}
::-webkit-scrollbar{height:8px;width:8px}::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:4px}
"""

CSS_SHOP = """
.bar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;background:var(--card);border:1px solid var(--line);
  border-radius:12px;padding:12px 14px;margin-bottom:14px}
.bar input[type=search]{flex:1;min-width:200px;border:1px solid var(--line);border-radius:8px;padding:7px 11px;font-size:13px;outline:none}
.bar input[type=search]:focus{border-color:#a5b4fc}
select,.chip{border:1px solid var(--line);background:#fff;border-radius:8px;padding:6px 10px;font-size:12.5px;color:var(--ink);cursor:pointer}
.chip.on{background:var(--pri);color:#fff;border-color:var(--pri)}
.bar .cnt{font-size:12.5px;color:var(--ink2)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(212px,1fr));gap:14px}
.gcard{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;text-decoration:none;color:inherit;
  display:flex;flex-direction:column;transition:transform .14s,box-shadow .14s;position:relative}
.gcard:hover{transform:translateY(-3px);box-shadow:0 8px 22px rgba(30,41,59,.12);border-color:#c7d2fe}
.gcard .pic{position:relative;width:100%;padding-top:100%;background:#f1f3f7;overflow:hidden}
.gcard .pic img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.gcard .nopic{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:var(--ink3);font-size:13px;background:linear-gradient(135deg,#f8fafc,#eef2f7)}
.rk{position:absolute;left:8px;top:8px;background:rgba(20,25,40,.72);color:#fff;font-size:11px;padding:2px 8px;border-radius:20px;z-index:2}
.dg{position:absolute;right:8px;top:8px;background:#0d9488;color:#fff;font-size:10.5px;padding:2px 8px;border-radius:20px;z-index:2}
.cvtag{position:absolute;left:8px;bottom:8px;background:rgba(20,25,40,.62);color:#fff;font-size:10px;padding:1.5px 7px;border-radius:5px;z-index:2}
.gbody{padding:10px 11px 12px;display:flex;flex-direction:column;gap:5px;flex:1}
.ttl{font-size:12.8px;line-height:1.45;height:37px;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.pri{display:flex;align-items:baseline;gap:6px}
.pri b{color:var(--price);font-size:18px;font-weight:700}
.pri .cm{font-size:11px;color:var(--warn);background:#fff7ed;border:1px solid #fed7aa;border-radius:5px;padding:1px 5px}
.pri .np{font-size:12px;color:var(--ink3)}
.who{font-size:11.5px;color:var(--ink2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.kv{display:grid;grid-template-columns:1fr 1fr;gap:2px 8px;font-size:11.5px;color:var(--ink2);margin-top:2px}
.kv i{font-style:normal;color:var(--ink);font-weight:600}
.sell{font-size:11px;color:var(--ink3);margin-top:-1px}
.tags{display:flex;gap:5px;flex-wrap:wrap;margin-top:4px}
.tag{font-size:10.5px;background:#f1f5f9;color:#475569;border-radius:5px;padding:1.5px 6px}
.tag.hot{background:#fef2f2;color:#b91c1c}
.footnote{font-size:12px;color:var(--ink2);background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin-top:16px}
.empty{padding:40px;text-align:center;color:var(--ink3)}
"""

CSS_DETAIL = """
.crumb{display:flex;align-items:center;gap:10px;font-size:12.5px;color:var(--ink2);margin-bottom:12px;flex-wrap:wrap}
.crumb a{text-decoration:none}
.hero{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;display:grid;grid-template-columns:230px 1fr;gap:20px}
.shot{width:230px;height:230px;border-radius:12px;overflow:hidden;background:#f1f3f7;border:1px solid var(--line)}
.shot img{width:100%;height:100%;object-fit:cover}
.shot .nopic{width:100%;height:100%;display:flex;align-items:center;justify-content:center;color:var(--ink3)}
.hinfo h1{font-size:19px;line-height:1.4;margin-bottom:8px}
.hrow{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:10px}
.pricebox{background:#fff1f4;border:1px solid #fecdd6;border-radius:10px;padding:10px 14px;display:inline-flex;align-items:baseline;gap:10px}
.pricebox b{color:var(--price);font-size:26px}
.pricebox span{font-size:12.5px;color:var(--ink2)}
.metas{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px 16px;font-size:12.5px;color:var(--ink2);margin-top:10px}
.metas b{color:var(--ink);font-weight:600}
.btnrow{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}
.btn{display:inline-block;font-size:12.5px;padding:7px 13px;border-radius:8px;text-decoration:none;border:1px solid var(--pri);
  color:var(--pri);background:var(--pri-soft)}
.btn:hover{background:#e0e7ff}
.btn.solid{background:var(--pri);color:#fff}
.btn.gray{border-color:var(--line);color:var(--ink2);background:#f8fafc}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(132px,1fr));gap:12px;margin:14px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:13px 14px}
.kpi .lb{font-size:11.5px;color:var(--ink2)}
.kpi .vl{font-size:21px;font-weight:700;margin:2px 0}
.kpi .sr{font-size:10.5px;color:var(--ink3);border-top:1px dashed var(--line);padding-top:5px;margin-top:4px}
.sec{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin-bottom:14px}
.sec h2{font-size:15.5px;margin-bottom:2px;display:flex;align-items:center;gap:8px}
.sec .lead{font-size:12px;color:var(--ink2);margin-bottom:12px}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th,td{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top}
th{background:#f8fafc;font-weight:600;font-size:11.5px}
tr:nth-child(even) td{background:#fcfdfe}
td.num{text-align:right;white-space:nowrap}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.pie{display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.pie .ring{width:120px;height:120px;border-radius:50%;flex:0 0 auto}
.pie ul{list-style:none;font-size:12.5px}
.pie li{margin:3px 0;display:flex;align-items:center;gap:7px}
.pie .dot{width:10px;height:10px;border-radius:3px;display:inline-block}
.vgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
.vcard{border:1px solid var(--line);border-radius:10px;overflow:hidden;background:#fff;display:flex;flex-direction:column}
.vcard .cover{position:relative;width:100%;padding-top:56%;background:#eef1f6}
.vcard .cover img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.vcard .dur{position:absolute;right:6px;bottom:6px;background:rgba(0,0,0,.6);color:#fff;font-size:10.5px;padding:1px 6px;border-radius:4px}
.vcard .b{padding:8px 10px;display:flex;flex-direction:column;gap:4px;font-size:12px}
.vcard .d{font-size:12px;line-height:1.45;max-height:52px;overflow:hidden}
.vcard .m{display:flex;gap:8px;flex-wrap:wrap;color:var(--ink2);font-size:11.5px}
.vcard .gmv{color:var(--price);font-weight:700}
.cloud{display:flex;flex-wrap:wrap;gap:8px}
.kw{background:var(--pri-soft);border:1px solid #dbe0fb;color:#3730a3;border-radius:8px;padding:4px 10px;font-size:12.5px}
.kw small{color:#6366f1;margin-left:5px}
.cloud .kw.big{background:#e0e7ff;font-weight:700}
.srcline{font-size:11.5px;color:var(--ink3);margin-top:8px}
@media(max-width:820px){.hero{grid-template-columns:1fr}.shot{width:100%;height:260px}.grid2{grid-template-columns:1fr}}
"""

JS_SHOP = """
function tog(el){el.classList.toggle('on')}
(function(){
  var q=document.getElementById('q'), sel=document.getElementById('sort'), cnt=document.getElementById('cnt');
  var cards=[].slice.call(document.querySelectorAll('.gcard'));
  var filters={cate:null,deep:null};
  function apply(){
    var kw=(q.value||'').trim().toLowerCase(), n=0;
    var arr=cards.slice();
    var mode=sel.value;
    arr.sort(function(a,b){
      if(mode==='rank') return (+a.dataset.rank)-(+b.dataset.rank);
      var x=+a.dataset[mode], y=+b.dataset[mode]; return y-x;
    });
    var box=document.getElementById('grid');
    arr.forEach(function(c){
      var s=c.dataset.search.toLowerCase();
      var ok=(!kw||s.indexOf(kw)>=0)&&(!filters.cate||c.dataset.cate===filters.cate)&&(!filters.deep||c.dataset.deep==='1');
      c.style.display=ok?'':'none';
      if(ok){box.appendChild(c);n++}
    });
    cnt.textContent='共 '+n+' 个商品 · 其中 '+document.getElementById('grid').dataset.nv+' 个已深挖带货视频/达人明细';
  }
  q.addEventListener('input',apply); sel.addEventListener('change',apply);
  document.querySelectorAll('.chip[data-f]').forEach(function(ch){
    ch.addEventListener('click',function(){
      var f=ch.dataset.f, v=ch.dataset.v;
      document.querySelectorAll('.chip[data-f="'+f+'"]').forEach(function(x){x.classList.remove('on')});
      if(filters[f]===v){filters[f]=null;ch.classList.remove('on')}else{filters[f]=v;ch.classList.add('on')}
      apply();
    });
  });
  apply();
})();
"""


def ring(name, lst, colors):
    """简单环形图 + 图例（纯 CSS conic-gradient，自包含）"""
    tot, parts, legend = 0.0, [], []
    for x in lst:
        try:
            v = pct(x.get("pct"))
        except Exception:
            v = 0.0
        tot += v
    if tot <= 0:
        tot = 1.0
    acc = 0.0
    for i, x in enumerate(lst):
        v = pct(x.get("pct"))
        c = colors[i % len(colors)]
        a, b = acc, acc + v / tot * 100
        parts.append("%s %s%% %s%%" % (c, round(a, 2), round(b, 2)))
        acc = b
        legend.append('<li><span class="dot" style="background:%s"></span>%s · %s <b>%s</b></li>'
                      % (c, E(x.get("name")), E(x.get("gmv")), E(x.get("pct"))))
    return ('<div class="pie"><div class="ring" style="background:conic-gradient(%s)"></div>'
            '<ul>%s</ul></div>' % (",".join(parts), "".join(legend)))


PIE_C = ["#4f46e5", "#0d9488", "#f59e0b", "#e0245e", "#0284c7", "#7c3aed"]

# =========================================================
# 第 1 屏 · 商品卡墙
# =========================================================

def build_index():
    cates = collections.Counter(c.get("cate") or "未分类" for c in items)
    chip = ['<span class="cnt" id="cnt"></span>']
    chips = ['<select id="sort">'
             '<option value="rank">排序：榜单排名</option>'
             '<option value="sv">排序：销售额（档位中值）</option>'
             '<option value="vol">排序：销量（档位中值）</option>'
             '<option value="vw">排序：浏览量</option>'
             '<option value="cv">排序：转化率</option>'
             '<option value="vid">排序：带货视频数</option>'
             '<option value="tal">排序：带货达人数</option>'
             '<option value="pr">排序：推算价格</option>'
             '<option value="cm">排序：佣金率</option>'
             '</select>']
    for cat, n in cates.most_common():
        chips.append('<button class="chip" data-f="cate" data-v="%s">%s %d</button>' % (E(cat), E(cat), n))
    chips.append('<button class="chip" data-f="deep" data-v="1">仅已深挖</button>')

    cards_html = []
    for i, c in enumerate(items, 1):
        gid = c["gid"]
        cv = cover_of(gid)
        pic = ('<img src="../%s" alt="" loading="lazy"><span class="cvtag">带货视频封面</span>' % E(cv)) \
            if cv else '<div class="nopic">该链接本月无带货视频<br>无卡面图</div>'
        dg = '<span class="dg">已深挖</span>' if has_deep(gid) else ''
        price = c.get("price_est")
        pr = ('<div class="pri"><b>¥%s</b>' % E(price)) if price else '<div class="pri"><span class="np">价格未标注</span>'
        if c.get("commission_rate"):
            pr += '<span class="cm">佣 %s / %s</span>' % (E(c.get("commission_rate")), E(c.get("commission_fee") or ""))
        pr += '</div>'
        who = " / ".join([x for x in [c.get("brand"), c.get("shop")] if x]) or "未标注品牌/店铺"
        tags = []
        if c.get("cate"):
            tags.append('<span class="tag">%s</span>' % E(c["cate"]))
        if c.get("rank_no"):
            tags.append('<span class="tag hot">飞瓜%s 第%s名</span>'
                        % (E(c.get("rank_period") or "月榜"), E(c.get("rank_no"))))
        if c.get("onsale_date"):
            tags.append('<span class="tag">上架 %s</span>' % E(c["onsale_date"]))
        if c.get("shop_score"):
            tags.append('<span class="tag">店铺分 %s</span>' % E(c["shop_score"]))
        if c.get("praise"):
            tags.append('<span class="tag">好评 %s</span>' % E(c["praise"]))
        if (c.get("带货视频") or "0") not in ("0", "", None):
            tags.append('<span class="tag hot">视频 %s</span>' % E(c.get("带货视频")))
        cards_html.append(
            '<a class="gcard" href="product/%s" data-rank="%d" data-cate="%s" data-deep="%d"'
            ' data-sv="%s" data-vol="%s" data-vw="%s" data-cv="%s" data-vid="%s" data-tal="%s"'
            ' data-pr="%s" data-cm="%s" data-search="%s">'
            '<div class="pic">%s<span class="rk">TOP30 #%s</span>%s</div>'
            '<div class="gbody">'
            '<div class="ttl">%s</div>%s'
            '<div class="who">%s</div>'
            '<div class="kv"><span>销售额 <i>%s</i></span><span>销量 <i>%s</i></span>'
            '<span>浏览 <i>%s</i></span><span>转化 <i>%s</i></span></div>'
            '<div class="sell"> 🎬 视频 %s　📺 直播 %s　👤 达人 %s</div>'
            '<div class="tags">%s</div>'
            '</div></a>'
            % (E(pagename[gid]), i, E(c.get("cate") or "未分类"), 1 if has_deep(gid) else 0,
               tier(c.get("销售额")), tier(c.get("销量")), numw(c.get("浏览量")), numrate(c.get("转化率")),
               numw(c.get("带货视频")), numw(c.get("带货达人")), price or 0, pct(c.get("commission_rate")),
               E(((c.get("title") or "") + " " + who + " " + (c.get("cate") or "")).lower()),
               pic, E(c.get("榜_rank") or i), dg,
               E(c.get("title")), pr, E(who),
               E(c.get("销售额") or "—"), E(c.get("销量") or "—"),
               E(c.get("浏览量") or "—"), E(c.get("转化率") or "—"),
               E(c.get("带货视频") or "0"), E(c.get("带货直播") or "0"), E(c.get("带货达人") or "0"),
               "".join(tags)))

    body = """
<main><div class="wrap">
  <div class="notice"><b>看这一页的口径：</b>每一张卡 = 飞瓜里<strong>一个具体的商品购买链接</strong>（不是品牌、不是品类）。
  点的这一步，进去看的就是<strong>这个链接自己</strong>的销售额/销量/浏览转化、它的带货视频、它的带货达人、它的话术词云。
  全部来自飞瓜月榜（近 30 天），所有品牌一视同仁，不做区分。<br>
  <b>卡面图说明：</b>飞瓜的商品图 CDN 在本机环境取不到（详情页/榜单里的商品图都是 140×140 占位图），
  所以卡面统一使用<strong>该链接预估销售额 TOP1 带货视频的封面</strong>（已本地化到 <code>assets/</code>，离线可看）。
  没有带货视频的链接不显示图，用占位块代替。</div>
  <div class="bar">
    <input type="search" id="q" placeholder="搜商品名 / 品牌 / 店铺…">
    %s
    <span class="cnt" id="cnt"></span>
  </div>
  <div class="grid" id="grid" data-nv="%d">%s<div class="empty" id="none" style="display:none">没有匹配的商品</div></div>
  <div class="footnote">
    <b>数据来源</b>：飞瓜数据 · 抖音版 <code>#/product-rank/index?tab=product</code>（商品销售榜 → 类目「个护家清」→ 月榜）
    ，关键词 眼油 / 眼部精华 / 眼精华 / 眼霜 / 眼膜 / 眼贴 / 眼周 / 眼部护理。
    候选 41 条 → 眼部校验 → 同品归一化去重 → <b>TOP30</b>（榜上已是按销量/销售额排序的单链接）。<br>
    <b>已知口径限制</b>：①飞瓜只给档位（如 100w+ / 2500-5000），排序取档位中值；②价格为「佣金金额 ÷ 佣金率」推算，无佣金标注的不显示；
    ③%d 个链接有卡面图（= 该链接 TOP1 带货视频封面），其余 %d 个该链接没有带货视频；④更新于 %s。
  </div>
</div></main>
""" % ("".join(chips), NDEEP, "".join(cards_html), NCOV, len(items) - NCOV, E(NOW))

    head = """
<header><div class="wrap"><div class="hd">
  <div class="logo">眼油品类 · <em>商品货架</em></div>
  <div class="sub">%d 个具体商品链接 · 全部品牌一视同仁</div>
  <span class="pill g">月榜 · 近 30 天</span>
  <span class="pill">数据源 飞瓜</span>
  <span class="pill o">冻结 2026-09-26 12:00</span>
  <div class="navlinks">
    <a href="README.md">交付说明</a>
    <a href="品类聚合视图.html">附：品类聚合视图</a>
    <a href="_check/selfcheck.md">自检报告</a>
  </div>
</div></div></header>
""" % len(items)

    return ("<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>眼油品类 · 商品货架（%d 个单品链接）</title><style>%s%s</style></head><body>%s%s"
            "<script>%s</script></body></html>"
            % (len(items), CSS, CSS_SHOP, head, body, JS_SHOP))


# =========================================================
# 第 2 屏 · 单个商品链接的详情页
# =========================================================

def linked(c, field):
    """数据来源：每字段写清楚出处"""
    return {
        "销售额": "飞瓜商品详情 → 概览「商品数据 / 销售额」（近 30 天）",
        "销量": "飞瓜商品详情 → 概览「商品数据 / 销量」（近 30 天）",
        "订单量": "飞瓜商品详情 → 概览「商品数据 / 订单量」（近 30 天）",
        "浏览量": "飞瓜商品详情 → 概览「商品数据 / 浏览量」（近 30 天）",
        "转化率": "飞瓜商品详情 → 概览「商品数据 / 转化率」（近 30 天）",
        "带货视频": "飞瓜商品详情 → 概览「商品数据 / 带货视频」（近 30 天）",
        "带货直播": "飞瓜商品详情 → 概览「商品数据 / 带货直播」（近 30 天）",
        "带货达人": "飞瓜商品详情 → 概览「商品数据 / 带货达人」（近 30 天）",
    }.get(field, "飞瓜商品详情 → 概览")


def build_detail(idx):
    c = items[idx]
    gid = c["gid"]
    d = deep.get(gid) or {}
    cv = cover_of(gid)
    i = idx + 1
    prev = '<a class="btn gray" href="%s">← 上一个链接</a>' % E(pagename[items[idx - 1]["gid"]]) if idx > 0 else ""
    nxt = '<a class="btn gray" href="%s">下一个链接 →</a>' % E(pagename[items[idx + 1]["gid"]]) if idx < len(items) - 1 else ""

    shot = '<img src="../%s" alt="">' % E(cv) if cv else '<div class="nopic">暂无商品图</div>'
    price = c.get("price_est")
    pricebox = ('<div class="pricebox"><b>¥%s</b><span>推算价（佣金 %s ÷ 佣金率 %s）</span></div>'
                % (E(price), E(c.get("commission_fee")), E(c.get("commission_rate")))) if price else \
               '<div class="pricebox"><b>—</b><span>详情页未标注佣金，无法反推价格</span></div>'

    metas = [("所属类目", c.get("cate")), ("店铺评分", c.get("shop_score")),
             ("上架时间", c.get("onsale_date")), ("累计评价", c.get("reviews")),
             ("好评率", c.get("praise")),
             ("飞瓜榜排名", "%s %s 第 %s 名" % (c.get("rank_cate") or "个护家清", c.get("rank_period") or "月榜",
                                             c.get("rank_no") or "—")),
             ("模块内排序", "TOP30 第 %d 位" % i),
             ("更新时间", c.get("update_time")), ("飞瓜 GID", gid)]
    mh = "".join('<div>%s <b>%s</b></div>' % (E(k), E(v or "—")) for k, v in metas)

    link = (c.get("douyin_links") or [None])[0]
    btn = '<a class="btn solid" href="%s" target="_blank" rel="noopener">打开抖店商品链接</a>' % E(link) if link else ""

    # ---- 速览卡 ----
    kpis = [("销售额", c.get("销售额"), linked(c, "销售额")),
            ("销量", c.get("销量"), linked(c, "销量")),
            ("订单量", c.get("订单量"), linked(c, "订单量")),
            ("浏览量", c.get("浏览量"), linked(c, "浏览量")),
            ("转化率", c.get("转化率"), linked(c, "转化率")),
            ("带货达人", c.get("带货达人"), linked(c, "带货达人"))]
    kh = "".join('<div class="kpi"><div class="lb">%s</div><div class="vl">%s</div><div class="sr">%s</div></div>'
                 % (E(k), E(v or "—"), E(s)) for k, v, s in kpis)

    # ---- 具体数据来源表 ----
    rows = [("近 30 天销售额", c.get("销售额"), linked(c, "销售额")),
            ("近 30 天销量", c.get("销量"), linked(c, "销量")),
            ("近 30 天订单量", c.get("订单量"), linked(c, "订单量")),
            ("近 30 天浏览量", c.get("浏览量"), linked(c, "浏览量")),
            ("近 30 天转化率", c.get("转化率"), linked(c, "转化率")),
            ("带货视频数", c.get("带货视频"), linked(c, "带货视频")),
            ("带货直播场次", c.get("带货直播"), linked(c, "带货直播")),
            ("带货达人数", c.get("带货达人"), linked(c, "带货达人")),
            ("品牌 / 店铺", " / ".join([x for x in [c.get("brand"), c.get("shop")] if x]) or "—", "飞瓜商品详情 → 概览头部店铺信息"),
            ("店铺评分", c.get("shop_score"), "飞瓜商品详情 → 概览「店铺」区块"),
            ("上架时间", c.get("onsale_date"), "飞瓜商品详情 → 概览「商品信息」"),
            ("累积评价 / 好评率", "%s / %s" % (c.get("reviews") or "—", c.get("praise") or "—"), "飞瓜商品详情 → 概览「商品评价」"),
            ("佣金率 / 佣金", "%s / %s" % (c.get("commission_rate") or "—", c.get("commission_fee") or "—"), "飞瓜商品详情 → 概览「推广信息」"),
            ("推算价格", ("¥%s" % price) if price else "—",
             ("由佣金 %s ÷ 佣金率 %s 反推" % (c.get("commission_fee"), c.get("commission_rate"))) if price else "详情页无佣金标注，不推算"),
            ("榜单位置", "%s · %s · 第 %s 名" % (c.get("rank_cate") or "个护家清", c.get("rank_period") or "月榜", c.get("rank_no") or c.get("榜_rank")),
             "飞瓜商品销售榜（类目筛选 个护家清 · 月榜）"),
            ("数据更新时间", c.get("update_time"), "飞瓜页面标注的「更新时间」"),
            ("抖店商品地址", link or "—", "飞瓜详情页 → 复制链接（haohuo.jinritemai.com）")]
    tb = "".join("<tr><td style='width:150px'><b>%s</b></td><td>%s</td><td style='width:38%%;color:#6b7a90'>%s</td></tr>"
                 % (E(k), E(v), E(s)) for k, v, s in rows)

    parts = []
    parts.append("""
<div class="crumb">
  <a href="../index.html">← 返回商品货架</a>　%s　%s
  <span>第 %d / %d 个链接</span>
</div>
<div class="hero">
  <div class="shot">%s</div>
  <div class="hinfo">
    <h1>%s</h1>
    <div class="hrow">
      <span class="pill">%s</span><span class="pill g">%s</span><span class="pill">TOP30 #%s</span>
      %s
    </div>
    %s
    <div class="metas">%s</div>
    <div class="btnrow">%s%s</div>
  </div>
</div>
<h2 style="font-size:16px;margin:18px 0 8px">⚡ 这个链接的速览</h2>
<div class="kpis">%s</div>
""" % (prev, nxt, i, len(items), shot, E(c.get("title")),
       E(c.get("brand") or "未标品牌"), E(c.get("shop") or "未标店铺"), E(c.get("榜_rank") or i),
       ('<span class="pill o">%s</span>' % E(c.get("cate"))) if c.get("cate") else "",
       pricebox, mh, btn,
       ('<a class="btn" href="https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=%s&tab=overview&ts=%s&sign=%s" target="_blank" rel="noopener">在飞瓜打开该链接</a>'
        % (E(gid), E(c.get("ts")), E(c.get("sign")))),
       kh))

    parts.append('<div class="sec"><h2>📌 具体数据来源（逐字段可复核）</h2>'
                 '<div class="lead">每个数字都写清楚它是从哪儿来的，方便直接回到飞瓜核对。</div>'
                 '<table><tr><th>字段</th><th>数值</th><th>来源 / 口径</th></tr>%s</table></div>' % tb)

    # ---- 规格 / 属性 ----
    attr = (d.get("attr_text") or "").strip()
    if attr:
        parts.append('<div class="sec"><h2>🧾 规格 / 属性（详情页原文）</h2>'
                     '<div class="lead">飞瓜详情页「属性」区块抓到的原文文本。</div>'
                     '<div style="font-size:12.5px;white-space:pre-wrap;line-height:1.8">%s</div>'
                     '<div class="srcline">来源：飞瓜商品详情 → 「属性」标签</div></div>' % E(attr[:800]))

    # ---- 渠道 & 带货方式 ----
    if c.get("channel") or c.get("selltype"):
        a1 = ring("x", c.get("channel") or [], PIE_C) if c.get("channel") else '<div class="srcline">无数据</div>'
        a2 = ring("x", c.get("selltype") or [], PIE_C[1:] + PIE_C[:1]) if c.get("selltype") else '<div class="srcline">无数据</div>'
        parts.append('<div class="grid2">'
                     '<div class="sec"><h2>📺 这个链接的成交渠道结构</h2><div class="lead">视频 / 直播 / 商品卡，谁在真正出货</div>%s'
                     '<div class="srcline">来源：飞瓜商品详情 → 概览「渠道占比」</div></div>'
                     '<div class="sec"><h2>🤝 带货方式结构</h2><div class="lead">品牌自营 / 达人推广 / 商品卡</div>%s'
                     '<div class="srcline">来源：飞瓜商品详情 → 概览「带货方式占比」</div></div>'
                     '</div>' % (a1, a2))

    videos = d.get("videos") or []
    if videos:
        vh = []
        for v in videos[:20]:
            vh.append(
                '<div class="vcard"><div class="cover"><img src="%s" alt="" loading="lazy" onerror="this.style.display=\'none\'">'
                '<span class="dur">%s</span></div><div class="b">'
                '<div class="d">%s</div>'
                '<div class="m"><span class="gmv">预估销售额 %s</span><span>销量 %s</span><span>GPM %s</span></div>'
                '<div class="m"><span>%s 发布</span><span>%s</span></div>'
                '<div class="m"><a href="%s" target="_blank" rel="noopener">抖音原视频 ↗</a>'
                '<a href="%s" target="_blank" rel="noopener">达人主页 ↗</a></div>'
                '</div></div>'
                % (E(vimg(v)), E(v.get("duration")), E(v.get("desc")),
                   E(v.get("gmv")), E(v.get("volume")), E(v.get("gpm")),
                   E(v.get("pubTime")), E(v.get("blogger")),
                   E(v.get("shareUrl")), E(v.get("douyinHome"))))
        ovv = d.get("video_overview") or {}
        parts.append('<div class="sec"><h2>🎬 这个链接的带货视频（按预估销售额 TOP%d）</h2>'
                     '<div class="lead">共抓到 %s 条带货视频，这里展示 TOP%d；点「抖音原视频」直接跳抖音网页版。</div>'
                     '<div class="vgrid">%s</div>'
                     '<div class="srcline">来源：飞瓜商品详情 → 「带货视频」标签，接口 loadAwemeAnalysis（按 AwemeSaleGmv 降序）'
                     '；本链接视频总数 %s，视频侧累计销售额 %s / 销量 %s。</div></div>'
                     % (len(vh), E(d.get("videos_total") or len(videos)), len(vh), "".join(vh),
                        E(ovv.get("AwemeCountStr") or d.get("videos_total") or "—"),
                        E(ovv.get("AwemeSaleGmvStr") or "—"), E(ovv.get("AwemeSaleCountStr") or "—")))

    wc = d.get("wordcloud") or []
    if wc:
        top = wc[:36]
        mx = max([numw(x.get("cnt")) for x in top] + [1])
        ch = "".join('<span class="kw%s">%s<small>%s (%s)</small></span>'
                     % (" big" if numw(x.get("cnt")) >= mx * 0.6 else "", E(x.get("kw")),
                        E(x.get("cnt")), E(x.get("ratio"))) for x in top)
        parts.append('<div class="sec"><h2>💬 这个链接的视频在说什么（内容词云）</h2>'
                     '<div class="lead">来自该链接关联带货视频的高频词，直接是可抄的话术素材。</div>'
                     '<div class="cloud">%s</div>'
                     '<div class="srcline">来源：飞瓜商品详情 → 「带货视频」→ GetAwemeMarketingKeyWordList</div></div>' % ch)

    bl = d.get("bloggers") or []
    if bl:
        rowsb = []
        for k, b in enumerate(bl[:20], 1):
            rowsb.append("<tr><td>%d</td><td><b>%s</b> <span style='color:#9aa7b8'>%s</span></td>"
                         "<td class='num'>%s</td><td>%s</td><td class='num'>%s</td><td class='num'>%s</td>"
                         "<td class='num'>%s</td><td class='num'>%s</td><td class='num'>%s</td>"
                         "<td><a href='%s' target='_blank' rel='noopener'>主页 ↗</a></td></tr>"
                         % (k, E(b.get("name")), E(b.get("level") or ""), E(b.get("fans") or "—"),
                            E(b.get("cert") or b.get("tag") or "—"), E(b.get("gmv") or "—"),
                            E(b.get("volume") or "—"), E(b.get("awemeCnt") or "—"),
                            E(b.get("liveCnt") or "—"), E(b.get("liveGmv") or "—"), E(b.get("home") or "")))
        parts.append('<div class="sec"><h2>👤 谁在给这个链接带货（达人 TOP%d）</h2>'
                     '<div class="lead">近 30 天该链接的带货达人，按带货销售额排序。</div>'
                     '<table><tr><th>#</th><th>达人</th><th>粉丝</th><th>认证</th><th>带货销售额</th><th>销量</th>'
                     '<th>视频</th><th>直播</th><th>直播销售额</th><th>主页</th></tr>%s</table>'
                     '<div class="srcline">来源：飞瓜商品详情 → 「带货达人」→ /api/v3/goods/blogger/list（近 30 天，sort=6）；'
                     '该链接带货达人总数 %s。</div></div>'
                     % (len(rowsb), "".join(rowsb), E(d.get("bloggers_total") or "—")))

    conc = d.get("concentration") or {}
    if conc.get("top5"):
        rows5 = "".join("<tr><td>%d</td><td>%s</td><td>%s</td><td class='num'>%s</td></tr>"
                        % (k, E(x.get("name")), E(x.get("gmv")), E(x.get("rate")))
                        for k, x in enumerate(conc["top5"], 1))
        parts.append('<div class="sec"><h2>🎯 达人集中度 TOP5</h2>'
                     '<div class="lead">看这个链接是被少数达人撑起来的，还是广撒网。</div>'
                     '<table><tr><th>#</th><th>达人</th><th>带货销售额</th><th>销售额占比</th></tr>%s</table>'
                     '<div class="srcline">来源：飞瓜 /api/v3/goods/blogger/concentration</div></div>' % rows5)

    btypes = d.get("blogger_types") or []
    if btypes:
        rowst = "".join("<tr><td>%s</td><td class='num'>%s</td><td class='num'>%s</td><td class='num'>%s</td></tr>"
                        % (E(x.get("type")), E(x.get("cnt")), E(x.get("ratio")), E(x.get("gmv")))
                        for x in btypes)
        parts.append('<div class="sec"><h2>🧩 达人层级结构</h2>'
                     '<div class="lead">给这个链接带货的都是什么量级的号。</div>'
                     '<table><tr><th>层级</th><th>达人数</th><th>占比</th><th>带货销售额</th></tr>%s</table>'
                     '<div class="srcline">来源：飞瓜 /api/v3/goods/blogger/blogger/type/analysis</div></div>' % rowst)

    if not (videos or wc or bl):
        parts.append('<div class="sec"><h2>🔍 视频 / 达人明细</h2>'
                     '<div class="lead">该链接这一批暂未取到带货视频与达人明细。</div>'
                     '<div class="notice" style="margin:0">可能原因：①该链接本身带货视频数为 0（纯直播/商品卡出货）；'
                     '②本批次深挖取样时未覆盖到。概览层的销售额 / 销量 / 浏览 / 转化 / 渠道结构仍以上方数据为准。</div></div>')

    # 同品牌其它链接
    same = [x for x in items if x["gid"] != gid and (x.get("brand") or x.get("shop")) ==
            (c.get("brand") or c.get("shop")) and (c.get("brand") or c.get("shop"))]
    if same:
        sl = "，".join('<a href="%s">%s</a>' % (E(pagename[x["gid"]]), E((x.get("title") or "")[:28]))
                      for x in same[:6])
        parts.append('<div class="sec"><h2>🔗 同品牌 / 同店铺的其它链接</h2><div style="font-size:12.5px">%s</div></div>' % sl)

    foot = ('<div class="footnote"><b>数据边界</b>：飞瓜对销售额 / 销量只给<b>档位</b>（如 100w+、2500-5000），'
            '不给精确值；价格由佣金反推；视频互动数据（点赞/评论）在列表接口不返回，显示「—」。'
            '本页所有数字均来自「%s」这一个具体链接，不做跨商品汇总。<br>'
            '统计周期 %s　|　页面数据抓取于 %s　|　冻结线 2026-09-26 12:00</div>'
            % (E(gid), E(RANGE_D or "近 30 天"), E(NOW)))

    head = """
<header><div class="wrap"><div class="hd">
  <div class="logo">单品详情 · <em>%s</em></div>
  <div class="pill">%s</div><div class="pill g">TOP30 #%s</div>
  <div class="navlinks">
    <a href="../index.html">← 商品货架</a>
    <a href="README.md">交付说明</a>
  </div>
</div></div></header>
""" % (E((c.get("brand") or "未标品牌"))[:14], E(c.get("cate") or "未分类"), E(c.get("榜_rank") or i))

    body = '<main><div class="wrap">%s%s</div></main>' % ("".join(parts), foot)

    return ("<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>%s · 单品详情</title><style>%s%s</style></head><body>%s%s</body></html>"
            % (E((c.get("title") or "")[:24]), CSS, CSS_DETAIL, head, body))


def main():
    # 旧 品类聚合页 保留为附属视图
    old = os.path.join(BASE, "index.html")
    if os.path.exists(old) and "商品货架" not in open(old, encoding="utf-8").read()[:4000]:
        shutil.copy(old, os.path.join(BASE, "品类聚合视图.html"))
    oldd = os.path.join(BASE, "deep.html")
    if os.path.exists(oldd):
        os.makedirs(os.path.join(BASE, "_check"), exist_ok=True)
        shutil.move(oldd, os.path.join(BASE, "_check", "旧版_品类聚合深度页.html"))

    open(os.path.join(BASE, "index.html"), "w", encoding="utf-8").write(build_index())
    for i in range(len(items)):
        open(os.path.join(PROD, pagename[items[i]["gid"]]), "w", encoding="utf-8").write(build_detail(i))
    print("已生成 index.html（%d 张商品卡，其中 %d 已深挖、%d 有商品图）"
          % (len(items), NDEEP, NCOV))
    print("已生成 product/p01..p%02d.html 共 %d 个单品详情页" % (len(items), len(items)))


if __name__ == "__main__":
    main()
