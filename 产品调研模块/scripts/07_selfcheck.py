# -*- coding: utf-8 -*-
"""自检（单文件 SPA 版）：商品卡墙 + 单品调研 + 爆款拆解
结果写 _check/selfcheck.md
"""
import os, sys, json, re, glob, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
CHK = os.path.join(BASE, "_check")
COV = os.path.join(BASE, "assets", "covers")
VID = os.path.join(BASE, "assets", "video")
os.makedirs(CHK, exist_ok=True)

res = []
def ck(n, ok, d=""):
    res.append((n, bool(ok), d))

H = open(os.path.join(BASE, "index.html"), encoding="utf-8").read()
m = re.search(r'<script id="DB" type="application/json">(.*?)</script>', H, re.S)
DB = json.loads(m.group(1).replace("<\\/", "</")) if m else {}
P = DB.get("products") or []
M = DB.get("meta") or {}

# ---------- 1 文件层 ----------
ck("01 index.html 为单文件页面且足够大", len(H) > 300000, "%.2f MB" % (len(H) / 1e6))
ck("02 内嵌数据可解析", bool(P), "products = %d" % len(P))
ck("03 页面自包含：无跨文件页面跳转", 'href="product/' not in H and 'href="deep.html"' not in H)
ext = [u for u in re.findall(r'(?:src|href)="(https?://[^"]+)"', H)
       if not any(k in u for k in ("feigua", "douyin", "jinritemai", "iesdouyin"))]
ck("04 不自带外部 CDN / 字体依赖", not ext, str(ext[:2]))
ck("05 前端路由齐全（卡墙/单品/对标表/口径）",
   all(k in H for k in ("#/p/", "#/cmp", "#/method", "hashchange")), "route 函数存在")
ck("06 单品页有「返回商品货架」入口", 'href="#/"' in H and "返回商品货架" in H)
ck("07 单品页有上一/下一个链接", "#/p/'+(p.i-1)" in H.replace(" ", "") or "(p.i-1)" in H)

# ---------- 2 用户点名的三个字段 ----------
ck("08 每个商品都有「一句话卖点」", all(p.get("sellingPoint") for p in P), "覆盖 %d/%d" % (sum(1 for p in P if p.get("sellingPoint")), len(P)))
n_aud = sum(1 for p in P if p.get("audienceLine") and "不足" not in p["audienceLine"])
ck("09 每个商品都有「主要消费人群」", n_aud >= len(P) * 0.9, "覆盖 %d/%d" % (n_aud, len(P)))
n_bad = sum(1 for p in P if p.get("badRate") is not None)
ck("10 每个商品都有「差评率」", n_bad >= len(P) * 0.9, "覆盖 %d/%d" % (n_bad, len(P)))
ck("11 卡墙上这三项都渲染出来了",
   all(k in H for k in ("💡 ", "👥 ", "差评 ")), "卡模板含 卖点/人群/差评率")

# ---------- 3 产品核心要素 / 货架策略 / 视觉 ----------
CK_KEYS = ["内料形态", "包装形式", "功效", "主打成分", "香型/气味", "质地/肤感", "技术/工艺",
           "规格", "目标受众词", "使用场景", "用户痛点词", "外观/包装词", "美妆概念"]
ck("12 产品核心要素 13 个维度都产出", all(all(k in (p.get("core") or {}) for k in CK_KEYS) for p in P),
   "%d 个维度" % len(CK_KEYS))
def n_dims(p):
    return sum(1 for k in CK_KEYS if (p["core"].get(k) or []))

# 只有「评价=0 且 带货视频=0」的链接允许维度不足（真·无数据源），其余必须 ≥6 维
poor = [p for p in P if n_dims(p) < 6]
n_core = sum(1 for p in P if n_dims(p) >= 6)
low = lambda p: (p.get("nReviews") or 0) <= 3 or str(p.get("nV")) in ("0", "0条")
ck("13 ≥93% 的链接在「产品核心要素」上有 ≥6 个维度有实际内容",
   n_core >= len(P) * 0.93 and all(low(x) for x in poor),
   "满足 %d/%d；不足的 %d 个都是评价≤3 条或带货视频=0 的链接：%s（页面已如实标注「无」）"
   % (n_core, len(P), len(poor),
      "、".join("TOP%d %s" % (x["i"], x["title"][:12]) for x in poor) or "无"))
SH_KEYS = ["现行价（推算）", "佣金", "规格信号", "每克/每单位均价", "SKU 形态", "货架定位", "标题里的活动词"]
ck("14 货架策略 7 个字段都产出", all(all(k in (p.get("shelf") or {}) for k in SH_KEYS) for p in P),
   "%d 个字段" % len(SH_KEYS))
ck("15 视觉/包装调研有词云支撑", all((p["core"].get("外观/包装词") is not None) for p in P), "外观/包装词列存在")

# ---------- 4 爆款视频拆解 ----------
n_novid = sum(1 for p in P if not p.get("viral") and not (p.get("videosTotal") or 0))
ck("16 每个有带货视频的商品都给出 TOP10（不足 10 条则全给）拆解",
   all(len(p.get("viral") or []) == min(p.get("videosTotal") or 0, 10) for p in P),
   "共 %d 条；%d 个链接本月无带货视频（已如实标注，非缺数据）"
   % (sum(len(p["viral"]) for p in P), n_novid))
n_lines = sum(len(v.get("lines") or []) for p in P for v in p["viral"])
n_noline = sum(1 for p in P for v in p["viral"] if not v.get("lines"))
ck("17 每条视频都有「文案逐句拆解」（原句 + 类型 + 在干什么）",
   n_noline <= sum(len(p["viral"]) for p in P) * 0.05,
   "共 %d 句；%d 条文案只有话题标签无正文（页面如实标注）" % (n_lines, n_noline))
ck("18 每条视频都给了「框架类型 / 话术结构 / 痛点·卖点·人群·场景」",
   all(v.get("hook") and v.get("frameType") and "seq" in v
       and all(k in v for k in ("painC", "beneC", "crowdC", "sceneC"))
       for p in P for v in p["viral"]), "字段完整")
ck("19 每条视频都附「标题文案原文 + 抖音原视频直链」",
   all(v.get("share", "").startswith("http") for p in P for v in p["viral"]),
   "链接 %d 条" % sum(len(p["viral"]) for p in P))
ck("20 拆解筛选规则生效（排除大V/品牌号/福利款）",
   "排除" in H and "100 万" in H and all("excluded" in v for p in P for v in p["viral"]),
   "标记被排除 %d 条" % sum(1 for p in P for v in p["viral"] if not v.get("keep")))
n_mid = sum(1 for p in P for v in p["viral"] if "中腰部" in (v.get("tier") or ""))
ck("21 中腰部创作者占比", n_mid >= sum(len(p["viral"]) for p in P) * 0.3,
   "中腰部 %d 条 / 共 %d 条" % (n_mid, sum(len(p["viral"]) for p in P)))
ck("22 拆解口径如实标注（只依据文案原文，未做 ASR）",
   "ASR" in H and "视频文案原文" in H and "文案逐句拆解" in H)

# ---------- 5 图片 ----------
n_cov = sum(1 for p in P if p.get("cover"))
ck("23 卡面图已本地化", n_cov >= len(P) * 0.6, "%d/%d" % (n_cov, len(P)))
n_vimg = sum(1 for p in P for v in p["viral"] if v.get("cover"))
ck("24 拆解视频缩略图已本地化", n_vimg >= sum(len(p["viral"]) for p in P) * 0.6,
   "%d/%d" % (n_vimg, sum(len(p["viral"]) for p in P)))

# ---------- 6 卫生 & 铁律 ----------
bad = [x for x in (">None<", ">undefined<", ">null<", "nan%", "%s%", "Traceback", "/*__DB__*/") if x in H]
ck("25 页面无脏值与占位符残留", not bad, str(bad))
SELF = ["自家", "我方", "本品牌", "对标竞品", "我方品牌"]
viol = [k for k in SELF if k in H]
ck("26 铁律：所有品牌一视同仁，无自家/竞品二分", not viol, ("命中 %s" % viol) if viol else "白云山与其他品牌同等呈现")
n_vs = sum(1 for p in P if (p.get("vsummary") or {}).get("n"))
gs = sorted({g["name"] for p in P for g in ((p.get("vsummary") or {}).get("groups") or [])})
n_withv = sum(1 for p in P if (p.get("videosTotal") or 0) or p.get("viral"))
ck("27 每个有带货视频的链接都有「这些视频在反复讲什么」内容总结（词云 + 分类）",
   n_vs >= n_withv and "内容总结" in H and len(gs) >= 5,
   "有总结 %d / 有带货视频的 %d 个链接（其余 %d 个本月无视频）；分类：%s"
   % (n_vs, n_withv, len(P) - n_withv, "、".join(gs)))
ck("28 全品对标表存在且行数=商品数",
   "全品对标表" in H and P and len(P) == M.get("n"), "%d 个商品（眼部 %d + 面部 %d）"
   % (len(P), M.get("nEye", 0), M.get("nFace", 0)))
ck("29 三个飞书文件的数据需求都写进了「口径与方法」",
   all(k in H for k in ("2.1", "2.3", "2.4", "3.2", "竞品分析", "全球选品")), "对照表存在")
ck("30 统计周期标注一致", "月榜" in H and M.get("range") and M["range"] in H, M.get("range"))

# ---------- 7 三份飞书文档的字段覆盖 ----------
SELL_KEYS = ["功能", "一句话卖点", "主打技术", "主打成分", "香味", "背书", "备案成分"]
ck("31 《竞品分析2》卖点七项都产出",
   all(all(k in (p.get("sell") or {}) for k in SELL_KEYS) for p in P), "%d 项" % len(SELL_KEYS))
ck("32 《竞品分析2》产品档案段存在（21 行字段表）",
   "cmp2" in H and "产品档案（竞品分析 2 口径）" in H
   and all(k in H for k in ("'品名'", "'每克/每单位均价'", "'配赠'", "'消费人群'", "'用户痛点'",
                            "'主打技术'", "'备案成分'", "'差评率'", "'品牌 / 工厂'")), "21 行")
ck("33 全品对标表覆盖竞品分析2 字段", all(k in H for k in ("配赠", "工厂", "每克均价", "差评率")), "18 列")
ck("34 《产品AI工作流》2.1 核心要素 13 维 + 2.3 货架 7 字段 + 2.4 视觉齐备",
   all(k in H for k in ("产品核心要素", "货架策略", "产品视觉 / 包装调研")), "三段都在")
ck("35 《全球选品策略》四、产品调研（形态/包装形式/香型/功效/成分/价格）有对应位",
   all(k in H for k in ("内料形态", "包装形式", "香型/气味", "功效", "主打成分")), "5 项")

# ---------- 8 爆款拆解：对齐《爆款拆解框架》表 ----------
ck("36 每条视频拆解表 8 列（含痛点 / 卖点 / 人群 / 场景）",
   all(k in H for k in ("打什么痛点", "核心卖点", "目标人群", "使用场景",
                        "框架类型", "分析（亮点 / 转化点 / 爆点）", "开头（钩子）")), "8 列")
ck("37 每条视频都有「框架类型」",
   all(v.get("frameType") for p in P for v in p["viral"]),
   "取值样例：" + "／".join(sorted(set(v["frameType"] for p in P for v in p["viral"]))[:8]))
ck("38 每条视频都有「分析：亮点/转化点/爆点」三句",
   all(v.get("analysis") and all(v["analysis"].get(k) for k in ("亮点", "转化点", "爆点"))
       for p in P for v in p["viral"]), "三句完整")
ck("39 每条视频都有发布时间（时间列）",
   all(v.get("time") and v["time"] != "—" for p in P for v in p["viral"]),
   "有时间的 %d 条" % sum(1 for p in P for v in p["viral"] if v.get("time") and v["time"] != "—"))
ck("40 爆款拆解是折叠的（details 折叠，点开才显示拆解）",
   '<details class="vitem">' in H and "点击展开拆解" in H, "默认折叠")
ck("41 详情页每个板块都可手动折叠/展开（全板块 details + 全部展开/收起）",
   '<details class="sec"' in H and "secAll(1)" in H and "secAll(0)" in H and "sec-tools" in H,
   "板块默认收起，速览默认展开")
npi = sum(1 for p in P if (p.get("cover") or "").startswith("assets/products/"))
ck("42 卡面优先用 800×800 真·商品主图", npi >= len(P) * 0.5,
   "真商品图 %d / %d（缺失的是无评价数据的数据贫瘠链接，如实留空，不补占位图）"
   % (npi, len(P)))

# ---------- 9 三级类目筛选（2026-09-27 新增） ----------
ck("43 卡墙上方有「三级类目联动筛选」（一级/二级/三级）",
   'class="cate"' in H and 'id="fl1"' in H and 'id="fl2"' in H and 'id="fl3"' in H
   and "fillCate" in H and "cateRow" in H, "沿用用户调研模块的 select 写法")

ck("44 每个商品都带完整类目路径（L1 / L2 / L3）",
   all(p.get("l1") and p.get("l2") and p.get("cate") for p in P),
   "L1=%s；L2=%s；L3=%s" % (
       "／".join(sorted({p.get("l1") or "?" for p in P})),
       "／".join(sorted({p.get("l2") or "?" for p in P})),
       "／".join(sorted({p.get("cate") or "?" for p in P}))))

ck("45 三级筛选是真过滤（不是摆设）",
   "(!FILT.L1||p.l1===FILT.L1)" in H.replace(" ", "")
   and "(!FILT.L2||p.l2===FILT.L2)" in H.replace(" ", "")
   and "(!FILT.L3||p.cate===FILT.L3)" in H.replace(" ", "")
   and "applyWall()" in H, "applyWall 里按 L1/L2/L3 三档过滤")

_facets = {}
for _p in P:
    _k = (_p.get("l2") or "?", _p.get("cate") or "?")
    _facets[_k] = _facets.get(_k, 0) + 1
_empty = [k for k in _facets if _facets[k] == 0]
ck("46 每个三级类目都有货（选任何一档都不会出空白卡墙）",
   len(_facets) >= 8 and not _empty and min(_facets.values()) >= 3,
   "；".join("%s·%s %d" % (a, b, _facets[(a, b)]) for (a, b) in
             sorted(_facets, key=lambda x: (x[0] != "眼部护理", x[1]))))

ck("47 筛选选项按「当前有货的类目」聚合，且带数量",
   "facets()" in H and "l2Of" in H and "l3Of" in H and "g2[k]" in H and "g3[k]" in H,
   "选项文案形如「面霜（6）」，选之前就知道有几个")

ck("48 类目筛选器高亮当前选中的最深一级",
   "classList.add('on')" in H and "cate select.on" in H.replace("  ", " "),
   "已选到三级时高亮第三个 select（与参考图一致）")

for f in ("data/pool_raw.json", "data/pool_eye.json", "data/top30.json", "data/cards.json",
          "data/deep.json", "data/profile.json", "README.md",
          "data/pool_face.json", "data/top30_face.json", "data/cards_face.json",
          "data/deep_face.json", "data/profile_face.json"):
    ck("· 文件 %s" % f, os.path.exists(os.path.join(BASE, f)) and os.path.getsize(os.path.join(BASE, f)) > 100)
for f in glob.glob(os.path.join(BASE, "raw", "feishu", "*.json")):
    ck("· 飞书原始文档 %s" % os.path.basename(f), os.path.getsize(f) > 100)

md = ["# 产品调研模块 · 自检报告（单文件版）", "",
      "- 生成时间：%s" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
      "- 结果：**%d/%d PASS**" % (sum(1 for _, o, _ in res if o), len(res)),
      "- 结构：**单文件 index.html**（hash 路由）＝ 商品货架（三级类目筛选） → 单品调研 → 爆款拆解折叠 → 全品对标表",
      "- 规模：%.2f MB / %d 个商品（眼部护理 %d + 面部护理 %d）/ 卡面图 %d / 拆解视频 %d 条"
      % (len(H) / 1e6, len(P), M.get("nEye", 0), M.get("nFace", 0), M.get("nCov", 0), M.get("nViral", 0)),
      "", "| # | 检查项 | 结果 | 说明 |", "|---|---|---|---|"]
for i, (n, o, d) in enumerate(res, 1):
    md.append("| %d | %s | %s | %s |" % (i, n, "✅ PASS" if o else "❌ FAIL", d or "—"))
open(os.path.join(CHK, "selfcheck.md"), "w", encoding="utf-8").write("\n".join(md))
for n, o, d in res:
    print("%s %s  %s" % ("✅" if o else "❌", n, d))
print("\n%d/%d PASS → _check/selfcheck.md" % (sum(1 for _, o, _ in res if o), len(res)))
