# -*- coding: utf-8 -*-
"""
c06_merge.py — 洁面语料归并统计：需求 TOP / 痛点红线 / 词库 / 决策权重
沿用眼油模块 06 的统计口径（否定识别 + 引文截取 + 一语料一桶）

双来源：
  ① 小红书笔记/评论      data/raw_comments.json
  ② 飞瓜商品评价原文      raw/feigua_profile_洁面_*.json（c23 采集：29 个商品的商品评价原话）
     —— 与小红书共用同一套需求桶/痛点桶，命中数按来源拆分（fgCount / xhsCount）

输出: data/needs_top5.json, data/redline.json, data/lexicon.json, data/overview.json
"""
import json, os, re, glob
from collections import Counter, defaultdict
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
RAW = os.path.join(BASE, "raw")
TODAY = datetime.now().strftime("%Y-%m-%d")

# 飞瓜采集产物（取最新一份）
try:
    import c20_feigua_rank as C          # 复用 is_noise / guess_brand（与 c24 同一口径）
except Exception:
    C = None


def _fix_brand(b, t):
    """详情页品牌偶被截断（THE WHOO/后 → The），按标题回正"""
    bb = (b or "").strip()
    if bb.upper() in ("THE", "") and "后" in (t or ""):
        return "THE WHOO/后"
    return bb or "—"


def _disp_brand(b):
    """'CHANDO/自然堂' → '自然堂'；'BUV' → 'BUV'"""
    b = (b or "").strip()
    if "/" in b:
        zh = b.split("/", 1)[1].strip()
        if zh:
            return zh
    return b or "—"

# ===== 洁面需求桶 =====
NEED_BUCKETS = [
    ("清洁力（洗得干净/控油/去黑头）",
     r"清洁力|洗得干净|洗干净|洗得掉|洗掉|去油|控油|黑头|白头|毛孔|油脂|脏东西|深层清洁|卸得掉|洗完很干净"),
    ("洗后肤感（不紧绷/不假滑/不拔干）",
     r"紧绷|拔干|干涩|假滑|洗后|洗完|保湿|水润|舒服|清爽|不干|不涩|滋润|肤感|滑"),
    ("成分安全（氨基酸/无皂基/无香精）",
     r"氨基酸|皂基|成分|无香精|香精|酒精|sls|表活|弱酸|ph值|ph|防腐剂|无添加|安全|温和配方|刺激"),
    ("肤质匹配（油皮/干皮/敏感肌/痘肌）",
     r"油皮|干皮|混油|混干|混合皮|敏感肌|痘肌|痘痘肌|大油田|沙漠皮|肤质|中性皮"),
    ("祛痘 / 去闭口功效",
     r"祛痘|去痘|消痘|闭口|粉刺|痘痘|痘印|抗炎|消炎|红肿|痘"),
    ("价格性价比（平价/学生党）",
     r"平价|便宜|性价比|学生|穷鬼|大碗|百元|实惠|划算|预算|不贵|价位|多少钱|一支能用|几十块"),
    ("泡沫与使用愉悦感",
     r"泡沫|泡泡|绵密|丰富|起泡|打泡|冲洗|好冲|香味|味道|好闻|难闻|气味|香精味|留香|仪式感"),
    ("选品求助（求推荐/哪个好）",
     r"用哪个|推荐吗|求推荐|求安利|哪个好|可以吗|适合吗|怎么选|怎么办|用哪种|哪款|怎么样|有用过的吗|求分享"),
    ("用法/搭配困惑（频率/干手干脸/二次清洁）",
     r"一天洗几次|早晚|频率|干手|干脸|打湿|二次清洁|先用|顺序|要不要|还要用|搭配|卸妆后|敷"),
]
# ===== 洁面痛点桶（全部走否定识别）=====
PAIN_BUCKETS = [
    # 「很干/脸干」加了 (?!净) —— 否则 "洗完很干净 / 洗完脸干净" 会被跨词误判成痛点
    ("洗后紧绷 / 拔干", r"紧绷|拔干|干涩|很干(?!净)|脸干(?!净)|干燥|起皮|脱皮|绷得|绷"),
    ("假滑 / 残留冲不净", r"假滑|滑腻|冲不干净|洗不干净|残留|膜感|没洗干净|洗不掉|洗完还是油|油膜"),
    ("过敏 / 刺痛 / 泛红 / 烂脸",
     r"过敏|泛红|发红|刺痛|灼热|辣眼睛|辣脸|瘙痒|很痒|又痒|肿|红疹|起疹|烂脸|烧灼|烫|不适"),
    ("致痘 / 闷痘 / 爆闭口", r"闷痘|致痘|长痘|爆痘|闭口|粉刺|起痘|冒痘|越长越多"),
    ("清洁力不足 / 洗不干净",
     r"清洁力不够|清洁力不行|洗不干净|洗不掉|清洁力弱|卸不干净|没洗干净|卸不掉|清洁力差"),
    ("过度清洁 / 伤屏障", r"过度清洁|清洁力太强|清洁力太猛|伤屏障|屏障受损|越洗越油|越洗越干|洗太干净"),
    ("气味难闻 / 香精味重", r"难闻|异味|刺鼻|呛|味儿|味道怪|香精味|味道太冲|化工味"),
    ("无效 / 智商税",
     r"(?<!有)没效果|(?<!有)没有效果|没啥效果|一点效果没有|不见效|没见效|无效|智商税|交智商税|后悔|骗子|骗人|踩雷|不值|白买|吹上天|(?<!有)(?<!还)没用(?!完|之前|以前|过)|没啥用|浪费钱|交税"),
    ("包装 / 膏体问题", r"挤不出来|挤不动|太硬|硬得|不好挤|难起泡|起不了泡|漏|盖不严|盖子松|开口太|膏体"),
]
NON_FIXABLE = ["物流", "快递", "发货", "客服态度", "服务态度", "退货", "退款", "退不了", "降价"]

# 非洁面品类：飞瓜「面部护理套装」类商品（水乳霜/面霜同链接）的评价会混进来，逐条剔除
# 另含「吸收/涂抹/涂完/抹完」——洁面不会用这类涂抹动作词，出现即说明讲的是同链接搭售的乳液面霜
NON_CLEANSER_RE = re.compile(
    r"水乳|面霜|精华|面膜|眼霜|防晒|身体乳|洗发|沐浴|乳液|乳霜|爽肤水|护肤水|爽肤|"
    r"吸收|涂抹|涂完|抹完")
CLEANSER_RE = re.compile(r"洗面奶|洁面|洗脸|洗卸|泡沫|洗完脸|清洁|洗面")
# 雷区核心词：好评词云里若出现这些词说明是否定语境误抓（"不会紧绷"），一律只保留在差评侧
BADWORD_CORE_RE = re.compile(
    r"紧绷|拔干|干涩|干燥|起皮|脱皮|过敏|刺痛|泛红|发红|烂脸|痒|长痘|爆痘|闷痘|致痘|闭口|粉刺|"
    r"假滑|残留|冲不净|难闻|刺鼻|异味|没用|无效|智商税|后悔|踩雷|不值|白买|屏障|辣")
# 治愈性表述前缀：「去闭口 / 改善闭口」是需求不是已发生痛点
CURE_RE = re.compile(
    r"(?:去|祛|消|抗|淡化|减少|改善|缓解|修复|修护|针对|治|拯救|治好|舒缓|镇静|解决|搞定|"
    r"远离|不再|不长|没长|少了)$")
# 治愈性表述后置：「黑头闭口都有改善」「过敏肌都可以使用」「对闭口很有效果」—— 说的是解决/适用，不是痛点
CURE_POST_RE = re.compile(
    r"^[^，。！？；;,.!?\s]{0,5}(?:改善|减少|少了|没了|消失|淡化|好转|变少|下去|好了|掉了|"
    r"清掉|去掉|祛掉|消掉|缓解|干净|有效|有效果|有帮助|管用|可以使用|可以用|可用|能用|"
    r"适用|适合|友好|放心|必备|不怕)")

NEG_RE = re.compile(r"(?:不|没|无|未|别|不会|不太|没有|绝不|毫无|并不|也不|都不|不算|谈不上|不会|避免)[^，。！？；;.!?\s]{0,8}$")
HYP_RE = re.compile(r"(?:担心|害怕|怕|会不会|会不|可能|容易|据说|听说|万一|想着|就算|如果|假如|希望|期待)[^，。！？、；\s]{0,3}$")
DEG_RE = re.compile(r"[很太超挺特别非常有点比]{1,3}$")
CLAUSE_RE = re.compile(r"[，,。！？；;.!?\n]")

DECISION_MAP = {
    "清洁力（洗得干净/控油/去黑头）": "清洁力",
    "洗后肤感（不紧绷/不假滑/不拔干）": "温和度（不紧绷）",
    "成分安全（氨基酸/无皂基/无香精）": "成分安全",
    "肤质匹配（油皮/干皮/敏感肌/痘肌）": "肤质匹配",
    "祛痘 / 去闭口功效": "功效（祛痘/去黑头）",
    "价格性价比（平价/学生党）": "价格",
    "泡沫与使用愉悦感": "使用感（泡沫/香味）",
}


def norm(t):
    return re.sub(r"\s+", " ", (t or "")).strip()


def find_positive(text, pat, cure_guard=False):
    bounds = [0] + [c.end() for c in CLAUSE_RE.finditer(text)]
    for m in re.finditer(pat, text):
        cs = max([b for b in bounds if b <= m.start()] or [0])
        pre = text[max(cs, m.start() - 10):m.start()]
        pre2 = DEG_RE.sub("", DEG_RE.sub("", pre))
        if NEG_RE.search(pre2):
            continue
        if HYP_RE.search(pre2):
            continue
        if cure_guard and CURE_RE.search(pre2):
            continue
        if cure_guard and CURE_POST_RE.search(text[m.end():m.end() + 8]):
            continue
        if re.match(r"[^？?。！]{0,4}[吗呢][？?]?", text[m.end():m.end() + 6]):
            continue
        return m
    return None


def excerpt(text, m, win=72):
    start = max(0, m.start() - 18)
    end = min(len(text), start + win)
    return ("…" if start > 0 else "") + text[start:end] + ("…" if end < len(text) else "")


def pick_quotes(quotes, limit=4):
    seen, out = set(), []

    def score(q):
        t = q["text"]
        first = 2 if re.search(r"我(用|买|入手|洗|最近|之前)|用了|买了|入手|回购|空瓶", t) else 0
        return (-first, -len(t))
    for q in sorted(quotes, key=score):
        if "#" in q["text"]:
            continue
        # 飞瓜引文：展示出来的那 72 字必须真的在讲洁面（同链接搭售品的美白/乳液内容不拿来当证据）
        if q["source"].startswith("飞瓜") and not CLEANSER_RE.search(q["text"]):
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
    rc = os.path.join(DATA, "raw_comments.json")
    if not os.path.exists(rc):
        print("[err] 缺 data/raw_comments.json，先跑 c01", flush=True)
        return
    rawc = json.load(open(rc, encoding="utf-8"))
    note_meta = rawc.get("noteMeta", {})
    seen, corpus = set(), []
    for c in rawc.get("comments", []):
        t = norm(c.get("content", ""))
        if len(t) < 4 or t in seen:
            continue
        seen.add(t)
        corpus.append((t, "小红书", c))
    n_xhs = len(corpus)
    print(f"小红书语料 {n_xhs} 条（去重后）", flush=True)

    # ===== 飞瓜商品评价原文（c23 采集）=====
    fg_files = sorted(glob.glob(os.path.join(RAW, "feigua_profile_洁面_*.json")))
    fg_prod, fg_txt_seen = [], set()
    fg_polarity = Counter()          # 飞瓜官方情感分布（真实条数，非推算）
    fg_spus, fg_excluded = 0, []
    if fg_files:
        fgp = json.load(open(fg_files[-1], encoding="utf-8"))
        for gid, x in (fgp.items() if isinstance(fgp, dict) else []):
            if x.get("noData"):
                continue
            title = x.get("title") or ""
            ov0 = x.get("ov") or {}
            # 类目硬校验：飞瓜详情页「所属类目」必须就是「洁面」。
            # 实测混入了「面部护理套装」（水乳霜/面霜同链接），其评价是面霜内容，必须整商品剔除。
            cate0 = (ov0.get("cate") or "").strip()
            if cate0 and cate0 != "洁面":
                fg_excluded.append(f"[类目{cate0}] {title[:26]}")
                continue
            if C is not None and C.is_noise(title):
                fg_excluded.append(title[:30])
                continue
            brand = _disp_brand(_fix_brand((x.get("ov") or {}).get("brand") or x.get("brand"), title))
            for p in (x.get("polarity") or []):
                if p.get("p") == "全部":
                    fg_polarity["全部"] += p.get("c", 0)
                elif p.get("p") == "好":
                    fg_polarity["好"] += p.get("c", 0)
                elif p.get("p") == "中":
                    fg_polarity["中"] += p.get("c", 0)
                elif p.get("p") == "差":
                    fg_polarity["差"] += p.get("c", 0)
            got = 0
            for kw, lst in (x.get("comments") or {}).items():
                for it in lst:
                    t = norm(it.get("t") or "")
                    if len(t) < 8 or t in fg_txt_seen:
                        continue
                    fg_txt_seen.add(t)
                    got += 1
            if got:
                fg_spus += 1
            fg_prod.append({"gid": gid, "title": title, "brand": brand})
        # 逐商品重新遍历，写入语料（与小红书交叉去重：已出现过的文本不再计）
        n_offcate = 0
        for x in ([v for v in fgp.values() if isinstance(v, dict)] if isinstance(fgp, dict) else []):
            if x.get("noData"):
                continue
            title = x.get("title") or ""
            ov0 = x.get("ov") or {}
            cate0 = (ov0.get("cate") or "").strip()
            if cate0 and cate0 != "洁面":
                continue
            if C is not None and C.is_noise(title):
                continue
            brand = _disp_brand(_fix_brand(ov0.get("brand") or x.get("brand"), title))
            for kw, lst in (x.get("comments") or {}).items():
                for it in lst:
                    t = norm(it.get("t") or "")
                    if len(t) < 8 or t in seen:
                        continue
                    # 同链接搭售的水乳霜/面霜评价：有非洁面品类词且全句无洁面词 → 剔除
                    if NON_CLEANSER_RE.search(t) and not CLEANSER_RE.search(t):
                        n_offcate += 1
                        continue
                    seen.add(t)
                    corpus.append((t, "飞瓜·" + brand,
                                   {"brand": brand, "gid": x.get("gid", ""),
                                    "title": title, "date": it.get("d", "")}))
        if n_offcate:
            print(f"  剔除搭售品类（水乳霜/面霜等）评价 {n_offcate} 条", flush=True)
    n_fg = len(corpus) - n_xhs
    print(f"飞瓜语料 {n_fg} 条（{fg_spus} 个商品，剔除噪声商品 {len(fg_excluded)} 个）", flush=True)
    print(f"合计语料 {len(corpus)} 条", flush=True)

    def tally(buckets, neg_guard=False):
        cnt = Counter()
        fg_cnt = Counter()
        xhs_cnt = Counter()
        quotes = defaultdict(list)
        notes = defaultdict(set)
        brands = defaultdict(set)
        for t, s, rec in corpus:
            if any(n in t for n in NON_FIXABLE):
                continue
            for name, pat in buckets:
                m = find_positive(t, pat, cure_guard=neg_guard) if neg_guard else re.search(pat, t)
                if m:
                    cnt[name] += 1
                    if s.startswith("飞瓜"):
                        fg_cnt[name] += 1
                        b = rec.get("brand") or ""
                        if b and b != "—":
                            brands[name].add(b)
                    else:
                        xhs_cnt[name] += 1
                        notes[name].add(rec.get("noteId", ""))
                    # 需求桶引文：差评语境的语料计数照算，但不拿来做"购买原因"的证据
                    if not neg_guard and find_positive(t, BADWORD_CORE_RE.pattern, cure_guard=True):
                        break
                    quotes[name].append({"text": excerpt(t, m), "source": s,
                                         "noteId": rec.get("noteId", "")})
                    break
        for k in quotes:
            quotes[k] = pick_quotes(quotes[k])
        return cnt, quotes, notes, fg_cnt, xhs_cnt, brands

    nc, nq, nn, nfg, nxhs, nbr = tally(NEED_BUCKETS)
    pc, pq, pn, pfg, pxhs, pbr = tally(PAIN_BUCKETS, neg_guard=True)

    def mk(cnt, quotes, notes, topn, fg_cnt, xhs_cnt, brands):
        out = []
        for k, v in cnt.most_common(topn):
            bl = sorted(brands.get(k, set()))
            out.append({"name": k, "count": v,
                        "fgCount": fg_cnt.get(k, 0), "xhsCount": xhs_cnt.get(k, 0),
                        "brandCount": len(bl), "brands": bl[:8],
                        "noteCount": len(notes.get(k, set())),
                        "quotes": quotes[k]})
        return out

    needs = {"generatedAt": TODAY, "items": mk(nc, nq, nn, 5, nfg, nxhs, nbr),
             "corpus": {"total": len(corpus), "feigua": n_fg, "xhs": n_xhs},
             "sources": [
                 {"name": "飞瓜", "detail": f"洁面/洗面奶商品榜 TOP30 → 商品详情页「商品评价」原话（{fg_spus} 个商品，逐商品按舆情词云高频词定向抽取）"},
                 {"name": "小红书", "detail": "洁面/洗面奶 20 组关键词搜索 → 笔记正文 + 评论，已过 R1-R12 水军过滤"}]}
    redline = {"generatedAt": TODAY, "items": mk(pc, pq, pn, 8, pfg, pxhs, pbr),
               "source": f"飞瓜商品评价原文（{n_fg} 条）+ 小红书笔记正文与评论（{n_xhs} 条）；已剔除物流/客服/价格等不可改良项"}

    # ---- 词库 ----
    gw, bw = Counter(), Counter()
    pain_ids = set()          # 命中痛点桶的语料（按文本去重，飞瓜/小红书同口径）
    for t, s, rec in corpus:
        for name, pat in PAIN_BUCKETS:
            m = find_positive(t, pat, cure_guard=True)
            if m:
                bw[m.group(0)] += 1
                pain_ids.add(t)
                break
    for t, s, rec in corpus:
        if any(find_positive(t, pat, cure_guard=True) for _, pat in PAIN_BUCKETS):
            continue
        for name, pat in NEED_BUCKETS:
            m = find_positive(t, pat)
            if m:
                w = m.group(0)
                if BADWORD_CORE_RE.search(w):   # 雷区词只留在差评侧
                    continue
                gw[w] += 1
                break
    total = len(corpus) or 1
    good = total - len(pain_ids)
    cloud = ([{"word": w, "count": n, "polarity": "good"} for w, n in gw.most_common(30)] +
             [{"word": w, "count": n, "polarity": "bad"} for w, n in bw.most_common(30)])
    cloud = sorted(cloud, key=lambda x: -x["count"])[:56]

    # ---- 决策权重 ----
    dw = Counter()
    for name, crit in DECISION_MAP.items():
        dw[crit] += nc.get(name, 0)
    dsum = sum(dw.values()) or 1
    decision = [{"criterion": k, "weight": v, "pct": round(v / dsum * 100, 1)}
                for k, v in dw.most_common()]
    # 飞瓜官方情感分布（真实条数：好评/中评/差评，非推算）
    fg_total = fg_polarity.get("全部", 0)
    fg_sent = []
    if fg_total:
        for nm, key in (("好评", "好"), ("中评", "中"), ("差评", "差")):
            v = fg_polarity.get(key, 0)
            fg_sent.append({"name": nm, "value": v,
                            "pct": round(v / fg_total * 100, 2)})
    lexicon = {"generatedAt": TODAY,
               "sentimentDist": [{"name": "好评", "value": good},
                                 {"name": "差评", "value": len(pain_ids)}],
               "cloud": cloud,
               "goodWords": [{"word": w, "count": n} for w, n in gw.most_common(15)],
               "badWords": [{"word": w, "count": n} for w, n in bw.most_common(15)],
               "decision": decision,
               "sentimentDistFeigua": fg_sent,
               "corpus": {"total": len(corpus), "feigua": n_fg, "xhs": n_xhs},
               "source": (f"飞瓜商品评价原文（{n_fg} 条，{fg_spus} 个商品）+ 小红书洁面/洗面奶笔记与评论"
                          f"（{n_xhs} 条）合并统计（好评=未命中痛点桶；差评=命中痛点桶且非否定语境）"),
               "quick": {}}
    good_rate = round(good / total * 100, 1)
    lexicon["quick"] = {
        "goodTop": [x["word"] for x in sorted(cloud, key=lambda x: -x["count"]) if x["polarity"] == "good"][:5],
        "badTop": [x["word"] for x in sorted(cloud, key=lambda x: -x["count"]) if x["polarity"] == "bad"][:5],
        "goodRate": good_rate, "decision": decision}

    # ===== overview：概览条要用的字段必须与眼油口径**逐字段对齐** =====
    # 眼油是 productCount / brandCount / detailCount / reviewCount / negCount / filteredCount / dataRange。
    # 洁面这里以前只写了 corpus*，顶部概览条就渲染成「0 个品牌 ｜ 0 个商品SPU ｜ 数据区间 — ~ —」。
    o10 = {}
    _t10p = os.path.join(DATA, "top10.json")
    if os.path.exists(_t10p):
        try:
            o10 = json.load(open(_t10p, encoding="utf-8"))
        except Exception:
            o10 = {}
    st = o10.get("stats", {}) or {}
    fg_brands = set()
    for gid, x in (fgp.items() if fg_files and isinstance(fgp, dict) else []):
        if x.get("noData"):
            continue
        cate0 = ((x.get("ov") or {}).get("cate") or "").strip()
        if cate0 and cate0 != "洁面":
            continue
        raw_b = (x.get("ov") or {}).get("brand") or x.get("brand")
        b = _disp_brand(_fix_brand(raw_b, x.get("title") or ""))
        if b and b != "—":
            fg_brands.add(b)

    # 数据区间：取本次语料的真实日期范围（飞瓜评价日期 + 小红书评论日期），不写死。
    # 注意：飞瓜商品评价是「全部历史评价」按词云高频词定向抽的，跨度天然比小红书长
    #      （实测 1247/1435 条集中在最近一个月，最早只有零星几条 2024 年）。
    #      所以展示口径写成「近30天快照 + 历史评价」，不要笼统说成「近30天」，免得路演被追问。
    _dates = []
    for gid, x in (fgp.items() if fg_files and isinstance(fgp, dict) else []):
        for _kw, _lst in (x.get("comments") or {}).items():
            for _it in _lst:
                _d = (_it.get("d") or "")[:10].replace("/", "-")
                if re.match(r"^\d{4}-\d{2}-\d{2}$", _d):
                    _dates.append(_d)
    for _c in rawc.get("comments", []):
        _d = (_c.get("date") or _c.get("fetchDate") or "")[:10].replace("/", "-")
        if re.match(r"^\d{4}-\d{2}-\d{2}$", _d):
            _dates.append(_d)
    data_range = {"start": min(_dates), "end": max(_dates)} if _dates else None
    # 主力区间：从最新日期往前累计到覆盖 80% 语料的那条线（反映这批数据实际讲的是哪段时间）
    core_range = None
    if _dates:
        _cnt = Counter(_dates)
        _tot = sum(_cnt.values())
        _run = 0
        _line = None
        for _d in sorted(_cnt, reverse=True):
            _run += _cnt[_d]
            if _run >= _tot * 0.8:
                _line = _d
                break
        core_range = {"start": _line or min(_dates), "end": max(_dates)}

    overview = {"corpusTotal": len(corpus), "corpusFeigua": n_fg, "corpusXhs": n_xhs,
                "noteCount": len(note_meta),
                "fgSpuCount": fg_spus,
                # 与眼油逐一对应的概览字段
                "productCount": fg_spus or st.get("detailSpus", 0),
                "brandCount": len(fg_brands),
                "detailCount": st.get("detailSpus", fg_spus),
                "reviewCount": n_fg,
                "negCount": len(pain_ids),
                "filteredCount": len(fg_excluded),
                "dataRange": data_range,
                "coreRange": core_range,
                "dataRangeNote": "飞瓜商品评价取全部历史评价中命中舆情词云高频词的原话；小红书为本次搜索结果（笔记+评论）",
                "sources": needs["sources"]}

    json.dump(needs, open(os.path.join(DATA, "needs_top5.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(redline, open(os.path.join(DATA, "redline.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(lexicon, open(os.path.join(DATA, "lexicon.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(overview, open(os.path.join(DATA, "overview.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("\n=== 高频需求 TOP5 ===", flush=True)
    for i, x in enumerate(needs["items"], 1):
        print(f"{i}. {x['count']:>3}  {x['name']}   [飞瓜{x['fgCount']} / 小红书{x['xhsCount']}]"
              f"{'  品牌' + str(x['brandCount']) + ':' + '、'.join(x['brands'][:4]) if x['brandCount'] else ''}", flush=True)
    print("\n=== 痛点红线 ===", flush=True)
    for i, x in enumerate(redline["items"], 1):
        print(f"{i}. {x['count']:>3}  {x['name']}   [飞瓜{x['fgCount']} / 小红书{x['xhsCount']}]"
              f"{'  品牌' + str(x['brandCount']) + ':' + '、'.join(x['brands'][:4]) if x['brandCount'] else ''}", flush=True)
    if fg_sent:
        print("\n=== 飞瓜官方情感分布（真实条数）===", flush=True)
        for x in fg_sent:
            print(f"  {x['name']}  {x['value']} 条  {x['pct']}%", flush=True)
    print("\n=== 决策权重 ===", flush=True)
    for x in decision:
        print(f"  {x['criterion']}  {x['pct']}%", flush=True)
    print(f"\n好评率 {good_rate}%（好评 {good} / 差评 {len(pain_ids)}）", flush=True)


if __name__ == "__main__":
    main()
