# -*- coding: utf-8 -*-
"""
06_merge_xhs.py（v2）— 统一桶体系，把飞瓜评价 + 小红书语料合并统计需求/痛点
输入: raw/feigua_details_all.json（飞瓜评价）、data/raw_comments.json（小红书，已过滤）
输出: 重写 data/needs_top5.json、data/redline.json（每个桶标注两个来源各自命中数）
"""
import json, os, re, glob
from collections import Counter, defaultdict
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 自动定位：.../用户调研模块
WORKSPACE = os.path.dirname(BASE)
DATA = os.path.join(BASE, "data")
RAW = os.path.join(BASE, "raw")
TODAY = datetime.now().strftime("%Y-%m-%d")


def guess_brand_from_title(title, shop=""):
    """详情页「品牌」字段缺失时从标题兜底提品牌。
    只在**已知是真眼部商品**时使用（调用方已按类目过滤）。
    标题惯例「【营销词】品牌+产品名」：先剥营销括号，再匹配开头的英文名或 2-4 字中文名。
    匹配到「眼油霜人参胶」这类明显是产品描述的开头时返回空串，宁缺毋滥，
    绝不返回 "—" 之类的占位符。"""
    t = re.sub(r"^[【\[].*?[】\]]", "", (title or "").strip())
    t = re.sub(r"^[（(].*?[)）]", "", t).strip()
    # 英文品牌
    me = re.match(r"^([A-Za-z][A-Za-z0-9'\-\.]{1,18})(?![a-z])", t)
    if me:
        return me.group(1).strip()
    # 中文品牌：2-4 字，且不能是「产品词」开头
    mc = re.match(r"^([\u4e00-\u9fa5]{2,4})", t)
    if not mc:
        return ""
    cand = mc.group(1)
    if re.search(r"眼|霜|油|精华|面部|抗皱|补水|紧致|润养|淡纹|男女|肌肤|官方|正品|全新|升级|补贴|代言", cand):
        return ""
    return cand


# ===== 统一需求桶（飞瓜 + 小红书共用一套）=====
NEED_BUCKETS = [
    ("功效诉求（淡纹/抗老/黑眼圈）",
     r"细纹|干纹|抗老|抗皱|淡纹|皱纹|紧致|松弛|泪沟|眼袋|黑眼圈|浮肿|暗沉|眼下|改善"),
    ("质地体验（好吸收/不油腻）",
     r"好吸收|易吸收|不油|清爽|不腻|不黏|轻薄|吸收快|肤感|滋润|不滋润|水润|润滑"),
    ("温和安全（不过敏/不长脂肪粒）",
     r"温和|不辣|不刺激|敏感肌|孕妇|无酒精|不熏|过敏|脂肪粒|安全"),
    ("设计便捷（滚珠/手法/便携）",
     r"手法|怎么涂|怎么用|滚珠|便携|方便|按摩头|好上手|简单|充电|权杖|按摩棒|外观设计|瓶身|出口|用量|一次用多少|带出门"),
    ("价格性价比",
     r"平价|便宜|性价比|学生|穷鬼|大碗|百元|实惠|划算|预算|元左右|不贵|价廉"),
    ("香味与使用愉悦感",
     r"味道|香味|好闻|香气|留香|仪式感|难闻|冰冰凉凉|清凉|气味|香精"),
    ("用法/搭配困惑（二选一、叠涂、频率）",
     r"二选一|叠涂|怎么用|先用|顺序|每天|隔几天|要不要|还要用|流程|要每天都用"),
    ("选品求助（按年龄/症状求推荐）",
     r"用哪个|推荐吗|求推荐|哪个好|可以吗|适合|选择|怎么办|用哪种|哪款|怎么样"),
    ("成分/达人驱动（PDRN、主播推荐）",
     r"pdrn|玻色因|胜肽|视黄醇|咖啡因|成分|浓度|肽|主播|推荐买|视频推荐"),
]
# ===== 统一痛点桶（全部走否定识别，避免"不油腻/不糊眼/不刺鼻"被算成痛点）=====
PAIN_BUCKETS = [
    ("糊眼 / 进眼睛", r"糊眼|糊眼睛|进眼睛|模糊|砸吧|眼周很痒|辣眼睛|辣眼|睁不开"),
    ("无效 / 智商税",
     r"(?<!有)没效果|(?<!有)没有效果|没任何效果|没一点效果|没啥效果|一点效果没有|不见效|没见效|无效|智商税|交智商税|后悔|骗子|骗人|踩雷|不值|白买|吹上天|(?<!有)(?<!还)没用(?!完|之前|以前|过)|(?<!有)(?<!还)没有用(?!完|之前|以前|过)|没啥用|没鸟用|没一点鸟用|浪费钱"),
    ("油腻 / 不吸收",
     r"油腻|很厚|不吸收|不好吸收|闷|假滑|厚重|油乎乎|黏腻|粘腻|浮在表面|搓泥"),
    ("过敏 / 脂肪粒",
     r"过敏|红点|红疹|脂肪粒|起粒|起小疙瘩|发痒|很痒|瘙痒|肿痛|红肿|刺痛|灼热|不适|刺激|辣眼睛|辣眼|烧灼|长闭口|闷痘"),
    ("气味难闻", r"难闻|异味|刺鼻|呛|🤮|味儿|味道怪|香精味"),
    ("卫生/包装设计差",
     r"漏|不卫生|卫生隐患|二次污染|难打开|打不开|包装差|包装简陋|包装不好|包装太|瓶口太|盖不严|盖子松|滴管不好|取量不|控制不了用量|一次挤太多|洒了"),
]
# 不可改良项（物流/客服/价格），统计红线时剔除
NON_FIXABLE = ["物流", "快递", "发货", "客服态度", "服务态度", "退货", "退款", "退不了", "降价"]
# 否定词：出现在命中词前 5 字内即判为"否定表述"，痛点桶不计入、也不作引文
NEG_RE = re.compile(r"(?:不|没|无|未|别|不会|不太|没有|绝不|毫无|并不|也不|都不|不算|谈不上)[^，。！？；;.!?\s]{0,8}$")
# 假设/担忧语境：'担心会长脂肪粒'、'想着就算没效果' 属于需求信号，不是已发生的痛点
HYP_RE = re.compile(r"(?:担心|害怕|怕|会不会|会不|可能|容易|据说|听说|万一|想着|就算|如果|假如|希望|期待)[^，。！？、；\s]{0,3}$")
DEG_RE = re.compile(r"[很太超挺特别非常有点比]{1,3}$")
# 子句切分（、不算断句，因为 "没有闷脂肪粒、泛红刺痛" 是一个否定作用域）
CLAUSE_RE = re.compile(r"[，,。！？；;.!?\n]")


def norm(t): return re.sub(r"\s+", " ", (t or "")).strip()


def find_positive(text, pat):
    """返回第一个『非否定语境』的匹配。命中词前 5 字内出现"不/没/无..."则视为否定表述，跳过。

    例：'也不糊眼睛' 命中 '糊眼睛' → 前缀 '很滋润，也不' → 否定，不算痛点
        '不油腻'     命中 '油腻'   → 前缀 '不'        → 否定，不算痛点
    """
    bounds = [0] + [c.end() for c in CLAUSE_RE.finditer(text)]
    for m in re.finditer(pat, text):
        cs = max([b for b in bounds if b <= m.start()] or [0])   # 命中词所在子句起点
        pre = text[max(cs, m.start() - 10):m.start()]
        pre2 = DEG_RE.sub("", DEG_RE.sub("", pre))   # 先剥掉句尾程度副词
        if NEG_RE.search(pre2): continue             # "不油腻" / "不闷脂肪粒" / "没有闷脂肪粒、泛红刺痛"
        if HYP_RE.search(pre2): continue             # "担心会长脂肪粒" / "想着就算没效果"
        if re.match(r"[^？?。！]{0,4}[吗呢][？?]?", text[m.end():m.end() + 6]): continue  # 疑问句式
        return m
    return None


def excerpt(text, m, win=72):
    """以命中词为中心截取引文，保证『证据』一定出现在展示出来的那句话里"""
    start = max(0, m.start() - 18)
    end = min(len(text), start + win)
    return ("…" if start > 0 else "") + text[start:end] + ("…" if end < len(text) else "")


def pick_quotes(quotes, limit=4):
    """引文排序：优先长句（信息量高），且同一句话不重复"""
    seen, out = set(), []
    # 排序权重：亲历口吻（我/用了/买了/上脸）优先，其次信息量长的优先
    def score(q):
        t = q["text"]
        first = 2 if re.search(r"我(用|买|入手|涂|抹|上脸|最近|之前)|用了|买了|入手|上眼|回购", t) else 0
        return (-first, -len(t))
    for q in sorted(quotes, key=score):
        if "#" in q["text"]: continue          # 话题标签串不算有效引文
        key = q["text"][:24]
        if key in seen: continue
        seen.add(key); out.append(q)
        if len(out) >= limit: break
    return out


def load_gid_brand_map():
    """从 top10.json 建 gid → 品牌 的权威映射。
    详情页「品牌」字段缺失时优先用它兜底（top10 的品牌名是榜单口径的正名，
    比从标题正则猜准得多：实测标题猜会得到「优时颜第」「雏菊的天」这类截断名）。"""
    mp = {}
    fp = os.path.join(DATA, "top10.json")
    if os.path.exists(fp):
        try:
            for it in json.load(open(fp, encoding="utf-8")).get("items", []):
                b = (it.get("brand") or "").strip()
                for sp in it.get("spus", []):
                    g = sp.get("gid")
                    if g and b:
                        mp[g] = b
        except Exception:
            pass
    return mp


def load_corpus():
    """返回 [(text, source_tag, brand)]"""
    items = []
    gid_brand = load_gid_brand_map()
    dp = os.path.join(RAW, "feigua_details_all.json")
    if os.path.exists(dp):
        det = json.load(open(dp, encoding="utf-8"))["details"]
        for gid, d in det.items():
            info = d.get("info", {}) or {}
            cate3 = (info.get("category3") or "").strip()
            # ★ 先按类目剔除噪音：实测混入「眼油霜人参胶原玻色因以油入眼霜」（润林个护严选，
            #   类目「身体乳/霜/贴/膏/油」），评价讲的是身体乳，整条必须剔除。
            if cate3 and ("眼" not in cate3):
                continue
            # ★ 详情页「品牌」字段会缺失（实测 11 个商品里 2 个为空）。
            #   以前直接 `or "—"` 会把字符串 "—" 当成真品牌名传下去，
            #   导致语料来源显示成「飞瓜·—」、痛点品牌列表里多出一个「—」。
            #   兜底顺序：详情页 brand → top10 的 gid→品牌 → 标题正则 → 留空（按无品牌处理）
            brand = ((info.get("brand") or "").strip()
                     or gid_brand.get(gid, "")
                     or guess_brand_from_title(info.get("title", "")))
            for key in ("reviews", "negativeReviews"):
                lst = d.get(key) or []
                if isinstance(lst, dict): lst = lst.get("reviews", [])
                for r in lst:
                    txt = r if isinstance(r, str) else norm(r.get("content", ""))
                    items.append((norm(txt), "飞瓜", brand))
    rc = os.path.join(DATA, "raw_comments.json")
    if os.path.exists(rc):
        for c in json.load(open(rc, encoding="utf-8")).get("comments", []):
            items.append((norm(c.get("content", "")), "小红书", ""))
    # 去重
    seen, out = set(), []
    for t, s, b in items:
        if len(t) < 4 or t in seen: continue
        seen.add(t); out.append((t, s, b))
    return out


def tally(corpus, buckets, skip_nonfixable=False, neg_guard=False):
    """neg_guard=True → 痛点桶，必须命中非否定语境才算数（防"不油腻"被算成油腻痛点）"""
    cnt = Counter(); by_src = defaultdict(Counter); quotes = defaultdict(list); brands = defaultdict(set)
    for t, s, b in corpus:
        if skip_nonfixable and any(n in t for n in NON_FIXABLE): continue
        for name, pat in buckets:
            m = find_positive(t, pat) if neg_guard else re.search(pat, t)
            if m:
                cnt[name] += 1; by_src[name][s] += 1
                if b and b != "—": brands[name].add(b)   # 空品牌不塞进品牌列表
                quotes[name].append({"text": excerpt(t, m),
                                     "source": s + (f"·{b}" if (b and b != "—") else "")})
                break
    for k in quotes: quotes[k] = pick_quotes(quotes[k])
    return cnt, by_src, quotes, brands


def main():
    corpus = load_corpus()
    nc, nsrc, nq, nb = tally(corpus, NEED_BUCKETS)
    pc, psrc, pq, pb = tally(corpus, PAIN_BUCKETS, skip_nonfixable=True, neg_guard=True)

    def mk(cnt, by_src, quotes, brands, topn):
        return [{"name": k, "count": v,
                 "fgCount": by_src[k].get("飞瓜", 0), "xhsCount": by_src[k].get("小红书", 0),
                 "brandCount": len(brands.get(k, set())), "brands": sorted(brands.get(k, set()))[:6],
                 "quotes": quotes[k]} for k, v in cnt.most_common(topn)]

    needs = {"generatedAt": TODAY, "items": mk(nc, nsrc, nq, nb, 5),
             "corpus": {"total": len(corpus),
                        "feigua": sum(1 for x in corpus if x[1] == "飞瓜"),
                        "xhs": sum(1 for x in corpus if x[1] == "小红书")},
             "sources": [
                 {"name": "飞瓜商品评价", "detail": "商品详情页→商品评价，全部/好评/差评原文 + 舆情词云"},
                 {"name": "小红书", "detail": "10 个关键词搜索结果 → 笔记正文 + 评论，已过 R1-R9 水军过滤"}]}
    redline = {"generatedAt": TODAY, "items": mk(pc, psrc, pq, pb, 6),
               "source": "飞瓜商品评价（差评筛选）+ 小红书笔记与评论；已剔除物流/客服/价格等不可改良项"}
    json.dump(needs, open(os.path.join(DATA, "needs_top5.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(redline, open(os.path.join(DATA, "redline.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # 把小红书语料的高频词并入「用户话语体系」词云（好评词=需求桶命中，差评词=痛点桶命中）
    lx_p = os.path.join(DATA, "lexicon.json")
    if os.path.exists(lx_p):
        lx = json.load(open(lx_p, encoding="utf-8"))
        gw, bw = Counter(), Counter()
        for t, s, b in corpus:
            if s != "小红书": continue
            for name, pat in NEED_BUCKETS:
                m = re.search(pat, t)
                if m: gw[m.group(0)] += 1; break
            for name, pat in PAIN_BUCKETS:
                m = find_positive(t, pat)
                if m: bw[m.group(0)] += 1; break
        have = {x["word"] for x in lx.get("cloud", [])}
        for w, n in gw.most_common(14):
            if w not in have: lx.setdefault("cloud", []).append({"word": w, "count": n, "polarity": "good"})
        for w, n in bw.most_common(14):
            if w not in have: lx.setdefault("cloud", []).append({"word": w, "count": n, "polarity": "bad"})
        lx["cloud"] = sorted(lx["cloud"], key=lambda x: -x["count"])[:56]
        lx["source"] = "飞瓜商品评价（情感分布+舆情词云）+ 小红书笔记与评论高频词"
        json.dump(lx, open(lx_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"[done] lexicon.json 词云并入小红书高频词（好评{len(gw)} 差评{len(bw)}）")

    ov_p = os.path.join(DATA, "overview.json")
    ov = json.load(open(ov_p, encoding="utf-8")) if os.path.exists(ov_p) else {}
    ov["corpusTotal"] = len(corpus)
    ov["corpusFeigua"] = sum(1 for x in corpus if x[1] == "飞瓜")
    ov["corpusXhs"] = sum(1 for x in corpus if x[1] == "小红书")
    ov["sources"] = needs["sources"]
    json.dump(ov, open(ov_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"语料总量 {len(corpus)}（飞瓜 {ov['corpusFeigua']} / 小红书 {ov['corpusXhs']}）\n")
    print("=== 高频需求 TOP5 ===")
    for i, x in enumerate(needs["items"], 1):
        print(f"{i}. 合计{x['count']:>3}（飞瓜{x['fgCount']} / 小红书{x['xhsCount']}）  {x['name']}")
    print("\n=== 产品红线 ===")
    for i, x in enumerate(redline["items"], 1):
        print(f"{i}. 合计{x['count']:>3}（飞瓜{x['fgCount']} / 小红书{x['xhsCount']}）  {x['name']}")


if __name__ == "__main__":
    main()
