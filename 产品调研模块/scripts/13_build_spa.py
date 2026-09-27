# -*- coding: utf-8 -*-
"""13 · 单文件版页面生成器（2026-09-26 第二版）
★ 单个 index.html 用 hash 路由承载「商品卡墙 + 单品详情 + 爆款拆解」，彻底解决跨文件跳转失效。

数据需求对齐三个飞书文件：
  《产品AI工作流》二、产品调研 → 2.1 产品核心要素 / 2.3 货架策略 / 2.4 产品视觉包装
  《产品AI工作流》三、3.2 爆品视频拆解 → TOP10 视频 5 段式拆解（排除明星/大V>100万粉/品牌广告/福利款）
  《全球选品策略》四、产品调研 → 形态/香型/功效/成分/一句话卖点/价格 + 视觉调研
  《竞品分析2》 → 品名/图片/销量/价格规格/每克均价/上架/渠道/配赠/消费人群/用户痛点/
                 功能/一句话卖点/主打技术/主打成分/香味/背书/备案成分/好评/差评/差评率/工厂
产出: index.html（自包含，assets/ 用相对路径）
"""
import os, sys, json, re, html, datetime, collections

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
import pcommon as P

DATA = os.path.join(BASE, "data")
E = lambda s: html.escape("" if s is None else str(s))

load = lambda n: json.load(open(os.path.join(DATA, n), encoding="utf-8")) if os.path.exists(
    os.path.join(DATA, n)) else {}
cards = load("cards.json")
deep = load("deep.json")
prof = load("profile.json")
# ---- 面部护理（2026-09-27 新增）：同一套采集逻辑、独立命名空间 ----
cards2 = load("cards_face.json")
deep2 = load("deep_face.json")
prof2 = load("profile_face.json")
top2 = load("top30_face.json") or []
try:
    A = load("analysis.json")
except Exception:
    A = {}

NOW = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
try:
    RANGE_D = "%s ~ %s" % (datetime.datetime.strptime(P._dcode(29), "%Y%m%d").strftime("%m-%d"),
                           datetime.datetime.strptime(P._dcode(0), "%Y%m%d").strftime("%m-%d"))
except Exception:
    RANGE_D = "近 30 天"

L1_NAME = "个护家清"
EYE_L3 = ["眼部精华", "眼霜", "眼膜", "眼贴", "眼部按摩仪"]
FACE_L3 = ["面部精华", "面霜", "面膜", "洁面", "爽肤水", "防晒"]
FACE_POOL_L3 = {p["gid"]: ((p.get("catePath") or {}).get("L3"))
                for p in top2 if p.get("gid")}


def _title_l3(t, table):
    """按标题关键词定三级类目（table 顺序即优先级）"""
    for kw, name in table:
        if kw in t:
            return name
    return ""


def eye_l3(title, fgcate):
    """眼部护理三级类目：飞瓜商品分类优先，标题规则纠偏（如「眼霜套装」被飞瓜归到面部护理套装）"""
    t = title or ""
    if fgcate in EYE_L3 and "套装" not in t:
        return fgcate
    return (_title_l3(t, [("眼膜", "眼膜"), ("眼贴", "眼贴"), ("眼霜", "眼霜"),
                          ("眼部精华", "眼部精华"), ("眼油", "眼部精华"), ("眼精华", "眼部精华")])
            or (fgcate if fgcate in EYE_L3 else "眼部精华"))


def face_l3(gid, title, fgcate):
    """面部护理三级类目：以池子阶段「按三级类目关键词检索」的归属为准，标题规则兜底"""
    v = FACE_POOL_L3.get(gid)
    if v in FACE_L3:
        return v
    if fgcate in FACE_L3:
        return fgcate
    return (_title_l3(title or "", [("面膜", "面膜"), ("防晒", "防晒"), ("洁面", "洁面"),
                                    ("洗面奶", "洁面"), ("爽肤水", "爽肤水"), ("化妆水", "爽肤水"),
                                    ("精华水", "爽肤水"), ("面霜", "面霜"), ("精华", "面部精华")])
            or ("面霜" if "霜" in (title or "") else "面部精华"))


items = []
for gid, c in (cards or {}).items():
    c = dict(c); c["gid"] = gid; c["_ns"] = "eye"
    c["_cp"] = {"L1": L1_NAME, "L2": "眼部护理", "L3": eye_l3(c.get("title"), c.get("cate"))}
    items.append(c)
for gid, c in (cards2 or {}).items():
    c = dict(c); c["gid"] = gid; c["_ns"] = "face"
    c["_cp"] = {"L1": L1_NAME, "L2": "面部护理", "L3": face_l3(gid, c.get("title"), c.get("cate"))}
    items.append(c)
# 眼部在前、同一类目内按榜内序
items.sort(key=lambda x: (0 if x["_ns"] == "eye" else 1, x.get("榜_rank") or 999))

# 三级类目「组内排名」（同 L3 内按 销售额档中位 → 销量档 → 浏览量 降序）
_l3group = collections.defaultdict(list)
for c in items:
    _l3group[(c["_cp"]["L2"], c["_cp"]["L3"])].append(c)
for _arr in _l3group.values():
    _arr.sort(key=lambda x: (P.tier_mid(x.get("榜_sales_tier")),
                             P.tier_mid(x.get("榜_volume_tier")),
                             P.num(x.get("榜_views")) or 0), reverse=True)
    for _i, _c in enumerate(_arr, 1):
        _c["_l3rank"] = _i


def cover(gid):
    """卡面图：优先 800×800 真·商品主图（assets/products），退回视频封面（assets/covers）"""
    import glob as _g
    hit = _g.glob(os.path.join(BASE, "assets", "products", gid + ".*"))
    hit = [h for h in hit if not h.endswith(".part")]
    if hit:
        return "assets/products/" + os.path.basename(sorted(hit)[0])
    if os.path.exists(os.path.join(BASE, "assets", "covers", gid + ".jpg")):
        return "assets/covers/%s.jpg" % gid
    return ""


def vimg(aw):
    return "assets/video/%s.jpg" % aw if aw and os.path.exists(
        os.path.join(BASE, "assets", "video", "%s.jpg" % aw)) else ""


def numw(s):
    if s is None:
        return 0.0
    m = re.search(r"([\d.]+)\s*([w万]?)", str(s).replace(",", ""))
    if not m:
        return 0.0
    return float(m.group(1)) * (10000 if m.group(2) else 1)


def numrate(s):
    if not s:
        return 0.0
    m = re.search(r"([\d.]+)\s*%", str(s))
    if not m:
        return 0.0
    lo = float(m.group(1))
    m2 = re.search(r"[-~]\s*([\d.]+)\s*%", str(s))
    return (lo + float(m2.group(1)) if m2 else lo * 2) / 2 if m2 else lo


def pct(s):
    try:
        return float(str(s).replace("%", ""))
    except Exception:
        return 0.0


# ---------------- 词表（用于「文案里真的出现了什么」的判定） ----------------
PAIN = ["眼袋", "黑眼圈", "细纹", "干纹", "皱纹", "鱼尾纹", "川字纹", "泪沟", "松弛", "松垮",
        "浮肿", "眼周", "暗沉", "下垂", "脂肪粒", "敏感", "干燥", "缺水", "显老", "熬夜",
        "垮", "纹", "老", "松", "肿", "累", "疲", "无神", "没精神", "卡粉", "起皮", "粗糙",
        "凹陷", "眼纹", "眼皮松", "三角眼", "泡泡眼", "熊猫眼", "初老", "衰老", "干瘪"]
GOOD = ["紧致", "抗皱", "淡纹", "滋润", "保湿", "淡化", "提亮", "吸收", "舒缓", "清爽", "不油腻",
        "水润", "修复", "修护", "淡化细纹", "淡黑眼圈", "抗老", "抗初老", "嫩", "弹", "饱满",
        "平滑", "亮", "透", "细腻", "抚平", "改善", "拯救", "逆袭", "回春", "显小", "显年轻",
        "变小", "紧实", "提升", "淡掉", "不见", "消失", "抚纹", "去纹"]
PROOF = ["明星", "代言", "工厂", "国货", "专利", "成分", "实测", "对比", "回购", "林心如", "陈紫函",
         "宋威龙", "于震", "蔡徐坤", "魏哲鸣", "王楚钦", "李若彤", "临床", "检测", "认证",
         "同源", "大牌", "院线", "医美", "实验室", "报告", "数据", "三年", "十年", "老字号"]
ACT = ["活动", "大促", "降价", "福利", "补贴", "特惠", "限时", "限量", "仅限", "买一送", "拍一发",
       "送", "满减", "券", "双节", "中秋", "母亲节", "劳动节", "会员节", "涨前"]
CTA = ["小黄车", "评论区", "下单", "点击", "链接", "库存", "错过", "赶紧", "倒计时", "抢"]

# ---- 场景 / 人群 / 成分 / 钩子话术 / 转化话术（2026-09-26 按反馈新增） ----
SCENE = ["熬夜", "睡前", "晚上", "夜里", "早上", "早起", "起床", "化妆前", "上妆前", "妆前",
         "办公室", "上班", "通勤", "出差", "旅行", "游玩", "日常", "素颜", "卸妆后", "洗脸后",
         "洗完脸", "护肤", "带娃", "加班", "追剧", "手机", "屏幕", "电脑", "久坐", "party",
         "约会", "拍照", "镜头", "婚礼", "过年", "回家", "夏天", "冬天", "换季", "空调房"]
CROWD = ["25+", "30+", "35+", "40+", "45+", "50+", "55+", "60+", "25岁", "30岁", "35岁", "40岁",
         "45岁", "50岁", "60岁", "68岁", "姐妹", "姐姐", "姐姐们", "阿姨", "妈妈", "宝妈",
         "上班族", "打工人", "熬夜党", "学生", "党", "初老", "抗初老", "熟龄", "中年", "年轻",
         "女人", "女生", "女孩", "男士", "男生", "敏感肌", "干皮", "油皮", "混合皮", "准妈妈",
         "孕妈", "同龄人", "闺蜜", "同事", "老婆", "老公"]
INGRE = ["肽", "胶原", "玻尿酸", "烟酰胺", "视黄醇", "A醇", "咖啡因", "积雪草", "鱼子酱", "胜肽",
         "依克多因", "神经酰胺", "角鲨烷", "维E", "维生素", "PDRN", "肝素钠", "叶黄素", "决明子",
         "草本", "植萃", "多肽", "琥珀", "玻色因", "精油", "玫瑰", "人参", "灵芝", "蜂胶",
         "氨基酸", "虾青素", "麦角硫因", "重组胶原", "三型胶原"]
HOOKW = ["严重怀疑", "我严重", "千万别", "不要再", "别再", "还在", "你知道", "为什么", "是不是",
         "有没有", "谁说", "你还", "一定要", "必须", "后悔", "早知道", "居然", "竟然", "原来",
         "秘密", "真相", "黑科技", "绝了", "救命", "真的", "狠狠", "直接", "一整个", "破防",
         "离谱", "逆天", "震惊", "劝你", "听我", "说真的", "说实话", "不信你", "试过才", "后悔没",
         "才几十", "不要太", "我真的", "谁懂", "懂的", "姐妹们", "赶紧", "悄悄", "偷偷"]
SELLW = ["小黄车", "购物车", "左下角", "链接", "下单", "拍", "抢", "囤", "赶紧", "快", "别错过",
         "错过", "最后", "限时", "限量", "库存", "不多", "福利", "活动", "优惠", "便宜", "划算",
         "赠", "送", "倒计时", "今天", "现在", "直播间", "到手", "一支", "一瓶", "入手", "带回家"]
PROD = ["眼油", "眼霜", "眼膜", "眼贴", "眼部", "精华油", "眼精华", "眼部精华", "精油", "眼周",
        "小金瓶", "按摩", "滚珠", "眼膜贴", "眼周油", "眼部油", "眼霜油"]


HOOK_Q = ["你知道", "还在", "为什么", "是不是", "有没有", "别再用", "别再", "谁说", "你还"]


def clean_desc(t):
    """文案正文：去掉 #话题标签，压缩空白"""
    t = re.sub(r"#[^\s#]+", " ", t or "")
    return re.sub(r"\s+", " ", t).strip()


def split_clauses(t):
    """把视频文案切成子句（去掉 #话题 后按标点切），保留原文措辞"""
    body = clean_desc(t)
    if not body:
        return []
    parts = re.split(r"[！!？?。；;，,、~\-—…\.…\s]+", body)
    out = []
    for p in parts:
        p = p.strip()
        if len(p) >= 2 and p not in out:
            out.append(p)
    return out


def clauses_hit(t, wordlist, maxn=3):
    """从文案里抽出「真的说了」的子句原文，而不是返回孤立的词表词"""
    out = []
    for c in split_clauses(t):
        if any(w in c for w in wordlist):
            out.append(c)
        if len(out) >= maxn:
            break
    if not out:
        body = clean_desc(t)
        if body and any(w in body for w in wordlist):
            out = [body[:34]]
    return out


def clause_type(c, idx):
    """给文案的每一句判类型（只依据文案本身，不做画面推测）"""
    if idx == 0 and (any(w in c for w in HOOKW) or any(w in c for w in PAIN)):
        return ("黄金3秒钩子", "第一句就抓注意力 / 抛问题，负责留人")
    if any(w in c for w in ACT) or any(w in c for w in CTA) or any(w in c for w in SELLW):
        return ("转化/逼单", "给行动指令或活动信号，负责收口")
    if any(w in c for w in PAIN):
        return ("痛点", "戳用户已经有的问题，让对号入座")
    if any(w in c for w in GOOD):
        return ("功效/卖点", "给出结果承诺，回答「用了会怎样」")
    if any(w in c for w in INGRE):
        return ("成分/技术", "用成分或技术把功效讲得可信")
    if any(w in c for w in CROWD):
        return ("人群定位", "点名是谁的问题，圈定目标人群")
    if any(w in c for w in SCENE):
        return ("使用场景", "给出什么时候用，降低想象成本")
    if any(w in c for w in PROOF):
        return ("信任背书", "用背书降低决策风险")
    if any(w in c for w in HOOKW):
        return ("钩子话术", "用强语气/悬念拉住继续看")
    return ("补充描述", "补充产品信息或情绪表达")


def copy_lines(t):
    """把整条文案拆成逐句结构：子句 + 类型 + 作用（完全基于文案，不涉及画面）"""
    cs = split_clauses(t)
    return [{"c": c, "type": clause_type(c, i)[0], "why": clause_type(c, i)[1]}
            for i, c in enumerate(cs[:8])]


# ---- 商品级「视频内容总结」：同一商品多条视频文案 → 反复提及词 → 分类 ----
VS_GROUPS = [("痛点", PAIN), ("功效/卖点", GOOD), ("成分/技术", INGRE), ("目标人群", CROWD),
             ("使用场景", SCENE), ("钩子话术", HOOKW), ("转化话术", SELLW), ("信任背书", PROOF),
             ("品类/产品词", PROD)]


def build_vsummary(vids):
    """输入该商品的视频列表，输出按类分组的高频词 + 代表原句"""
    descs = [v.get("desc") or "" for v in vids]
    descs = [d for d in descs if d.strip()]
    out = []
    for name, wl in VS_GROUPS:
        cnt, eg, nvid = {}, {}, 0
        for d in descs:
            hw = hits_of(d, wl)
            if hw:
                nvid += 1
            for w in hw:
                cnt[w] = cnt.get(w, 0) + 1
            for c in clauses_hit(d, wl, 2):
                eg[c] = eg.get(c, 0) + 1
        if not cnt:
            continue
        # 单字（老/纹/松…）只用于命中判定，不进词云展示
        words = [(k, c) for k, c in sorted(cnt.items(), key=lambda x: (-x[1], -len(x[0])))
                 if len(k) >= 2][:12]
        if not words:
            continue
        egs = sorted(eg.items(), key=lambda x: -x[1])[:3]
        out.append({"name": name,
                    "words": [{"k": k, "c": c} for k, c in words],
                    "egs": [e for e, _ in egs],
                    "nVid": nvid})
    # 总词云：把各类的高频词合并去重（每个词都带得上分类，不做滑窗猜测）
    merged, belong = {}, {}
    for g in out:
        for w in g["words"]:
            k = w["k"]
            if k not in merged or w["c"] > merged[k]:
                merged[k] = w["c"]
                belong[k] = g["name"]
    cloud = [{"k": k, "c": c, "g": belong[k]} for k, c in
             sorted(merged.items(), key=lambda x: -x[1])[:20]]
    return {"groups": out, "cloud": cloud, "n": len(descs)}


def one_line_sp(title, brand, goods):
    """一句话卖点：从标题里剔除品牌/促销/官方词，保留 形态+功效 描述"""
    t = re.sub(r"【[^】]*】", "", title or "")
    for w in ["官方正品", "官方旗舰", "官方", "正品", "旗舰店", "专卖", "包邮", "同款", "明星",
              "推荐", "达人专属", "全新升级", "升级", "版", "款", "抖音独家", "国货", "男女通用",
              "女", "男", "通用", "护肤", "正品保障"]:
        t = t.replace(w, "")
    t = re.sub(r"[（(][^)）]*[)）]", "", t)
    t = re.sub(r"[A-Za-z0-9\-&'’·×#@\s]+", " ", t).strip()
    t = re.sub(r"\s+", "", t)
    if brand:
        for part in re.split(r"[/／|｜、]", brand):
            part = part.strip()
            if len(part) >= 2:
                t = t.replace(part, "")
    t = t.strip("·-()（） ")
    if len(t) > 26:
        t = t[:26]
    return t or (title or "")[:20]


def hook_type(desc, dur, btype):
    d = desc or ""
    if any(k in d for k in ACT):
        return "活动/促销开头"
    if any(k in d for k in HOOK_Q):
        return "提问式开头"
    if any(k in d for k in PROOF):
        return "明星/信任背书开头"
    if re.search(r"(我今年|岁|妈妈|姐妹|姐姐|阿姨|四十|50|60|68)", d):
        return "人设/年龄共鸣开头"
    if any(k in d for k in PAIN):
        return "痛点直击开头"
    if re.search(r"(vlog|日常|办公室|睡前|早上|洗完脸|化妆前)", d, re.I):
        return "场景代入开头"
    return "种草直给开头"


def parse_dur(s):
    m = re.match(r"(?:(\d+)分)?(\d+)秒", str(s or ""))
    if not m:
        return 0
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)


def frame_seq(hook, dur, hits):
    """段落序列：按实测时长切"""
    segs = [hook]
    if hits.get("pain"):
        segs.append("痛点放大（%s）" % "／".join(hits["pain"][:2]))
    if hits.get("benefit"):
        segs.append("利益点输出（%s）" % "／".join(hits["benefit"][:2]))
    if hits.get("proof"):
        segs.append("信任背书（%s）" % "／".join(hits["proof"][:2]))
    if hits.get("act") or hits.get("cta"):
        segs.append("活动逼单/转化引导")
    if dur >= 60:
        segs.append("重复强化 + 二次逼单")
    return segs


def hits_of(text, wordlist):
    return [w for w in wordlist if w in (text or "")]


# ---- 框架类型（对齐《爆款拆解框架》表的「框架类型」列取值） ----
F_STAR = ["于震", "林心如", "陈紫函", "宋威龙", "蔡徐坤", "魏哲鸣", "王楚钦", "李若彤", "明星", "代言"]
F_AI = ["ai", "AI", "Ai", "数字人", "换脸", "生成"]
F_PLOT = ["剧情", "日常", "vlog", "Vlog", "独居", "老公", "老婆", "室友", "同事", "对话", "吵架"]
F_GIFTW = ["拍一发", "买一送", "买1送", "送同款", "加赠", "赠品", "送小样", "第二件", "2件", "礼盒", "套装"]


def frame_type(desc, bt, dur, hits, hook):
    d = desc or ""
    if any(k in d for k in F_AI):
        return "AI"
    if any(k in d for k in F_STAR):
        return "明星"
    if hits.get("act"):
        return "活动"
    if any(k in d for k in F_PLOT) or re.search(r"(短剧|剧情|情景)", d):
        return "剧情"
    if re.search(r"(我今年|岁|妈妈|姐妹|姐姐|阿姨|四十|50|60|68|亲身|用了|我自己)", d):
        return "人设"
    if any(k in bt for k in ("达人", "个人", "企业")) or "达人" in d:
        return "达人"
    if hits.get("pain"):
        return "痛点"
    if hook == "场景代入开头":
        return "场景"
    return "种草"


def analysis_of(v):
    """对齐《爆款拆解框架》表「分析」列：亮点 / 转化点 / 爆点 三句"""
    d = v.get("desc") or ""
    hook_s = "开头用「%s」留人" % v.get("hook", "")
    star = [k for k in F_STAR if k in d]
    hl = []
    if star:
        hl.append("明星/IP（%s）做信任背书" % "／".join(star[:2]))
    if v.get("frameType") == "AI":
        hl.append("AI 生成内容开场，靠视觉新奇压低划走率")
    if v.get("painC"):
        hl.append("文案直接点名痛点「%s」，人群精准" % "／".join([x[:20] for x in v["painC"][:2]]))
    elif v.get("pain"):
        hl.append("文案命中痛点词「%s」" % "／".join(v["pain"][:2]))
    if not hl:
        hl.append("以「%s」切入，靠文案角度留人" % (v.get("hook") or "直给种草"))
    cp = []
    if v.get("beneC"):
        cp.append("卖点说成「%s」，和痛点对得上" % "／".join([x[:20] for x in v["beneC"][:2]]))
    elif v.get("benefit"):
        cp.append("核心利益点落在「%s」，和痛点一一对应" % "／".join(v["benefit"][:2]))
    if v.get("crowdC"):
        cp.append("点名人群「%s」" % "／".join([x[:16] for x in v["crowdC"][:2]]))
    if v.get("sceneC"):
        cp.append("落在场景「%s」" % "／".join([x[:16] for x in v["sceneC"][:2]]))
    if v.get("act"):
        cp.append("活动/福利信号（%s）做价格锚点" % "／".join(v["act"][:2]))
    if v.get("cta"):
        cp.append("结尾用「%s」类话术收口逼单" % "／".join(v["cta"][:2]))
    if not cp:
        cp.append("无明显逼单词，靠挂车自然转化")
    bp = []
    if v.get("proof"):
        bp.append("信任背书靠「%s」" % "／".join(v["proof"][:2]))
    if v.get("durs", 0) >= 60:
        bp.append("时长 %s 秒，中段有二次强化（适合长转化链路）" % v["durs"])
    else:
        bp.append("时长 %s 秒，短平快，纯前 15 秒完成钩子→利益点→转化" % v.get("durs"))
    bp.append("达人层级 %s（%s 粉），%s" % (v.get("tier"), v.get("fans"), "可复制" if v.get("keep") else "不可复制"))
    return {"亮点": hook_s + "；" + "；".join(hl), "转化点": "；".join(cp), "爆点": "；".join(bp)}


def build_product(i, c):
    gid = c["gid"]
    _is_face = c.get("_ns") == "face"
    d = (deep2 if _is_face else deep).get(gid) or {}
    p = (prof2 if _is_face else prof).get(gid) or {}
    cp = c.get("_cp") or {}
    title = c.get("title") or ""
    brand = c.get("brand") or ""
    cats = p.get("cats") or {}

    def cat(k, n=10):
        return [x["k"] for x in (cats.get(k) or [])[:n] if x.get("k")]

    # ---- 主要消费人群 ----
    au = p.get("audience") or {}
    g = (au.get("Gender") or [{}])
    fem = next((x for x in (au.get("Gender") or []) if x.get("n") == "女性"), None)
    age_top = sorted((au.get("Age") or []), key=lambda x: -pct(x.get("r")))[:2]
    geos = [x.get("n") for x in (au.get("Region") or au.get("Province") or [])[:3] if x.get("n")]
    ints = [x.get("n") for x in (au.get("Interest") or [])[:3] if x.get("n")]
    audience_line = "、".join([x for x in [
        ("女性 %s" % fem["r"]) if fem else "",
        ("主力 %s 岁（%s）" % (age_top[0]["n"], age_top[0]["r"])) if age_top else "",
        ("地域 " + "/".join(geos)) if geos else "",
    ] if x]) or "该链接受众画像数据不足"
    audience_detail = []
    for k, lab in (("Gender", "性别"), ("Age", "年龄"), ("Region", "地域"),
                   ("Province", "省份"), ("Interest", "兴趣偏好"), ("ConsumeLevel", "消费层级"),
                   ("PriceLevel", "价格偏好"), ("FansLevel", "粉丝层级"), ("Device", "设备")):
        if au.get(k):
            audience_detail.append({"label": lab,
                                    "items": [{"n": x.get("n"), "r": x.get("r"), "tgi": x.get("tgi")}
                                              for x in au[k][:8]]})

    # ---- 评价 ----
    good_words = cat("感受体验", 12) + cat("功效", 12)
    bad_words = cat("痛点问题", 12)
    reviews_sample = []
    for kw, lst in (p.get("comments") or {}).items():
        if lst:
            reviews_sample.append({"kw": kw, "items": [{"t": x.get("t"), "d": x.get("d")} for x in lst[:6]]})

    # ---- 兜底语料：该链接自己的视频文案 + 内容词云 + 属性原文 ----
    # 评价极少的链接（如 0~3 条评价）评价词云会空，用视频侧语料补，且如实标注来源
    corpus = " ".join([(v.get("desc") or "") for v in (d.get("videos") or [])])
    corpus += " " + " ".join([x.get("kw") or "" for x in (d.get("wordcloud") or [])])
    corpus += " " + (d.get("attr_text") or "")
    SEED = {
        "功效": GOOD, "成分": ["肽", "胶原", "玻尿酸", "烟酰胺", "视黄醇", "A醇", "咖啡因", "积雪草",
                              "鱼子酱", "胜肽", "依克多因", "神经酰胺", "角鲨烷", "维E", "维生素", "PDRN",
                              "肝素钠", "叶黄素", "决明子", "草本", "植萃", "多肽", "琥珀", "玻色因"],
        "气味": ["香", "味", "清新", "草本", "薄荷", "无香", "淡香"],
        "质地": ["清爽", "滋润", "不油腻", "吸收", "轻薄", "水润", "油感", "黏", "顺滑", "细腻", "服帖"],
        "技术": ["技术", "工艺", "专利", "冻干", "微电流", "超导", "发酵", "包裹", "微囊", "纳米", "靶向"],
        "规格": ["片", "支", "g", "ml", "克", "毫升", "装", "盒", "瓶"],
        "场景": ["熬夜", "睡前", "早上", "上班", "化妆前", "出差", "办公室", "通勤", "学生", "晚睡"],
        "受众": ["女性", "男士", "学生", "上班族", "妈妈", "阿姨", "40岁", "50岁", "25岁", "30岁", "初老"],
        "外观": ["瓶", "盒", "管", "罐", "礼盒", "金色", "银", "透明", "玻璃", "磨砂"],
        "痛点": PAIN,
    }

    def fallback(k):
        """按品类词表从视频文案/内容词云/属性原文里捞词；捞不到返回 []"""
        seeds = SEED.get(k) or []
        return [w for w in seeds if w in corpus][:8]

    # ---- 产品核心要素（2.1 / 全球选品 1.1） ----
    form = "油类（精华油）" if "眼油" in title or "油" in title else (
        "膜/贴类" if any(k in title for k in ("膜", "贴")) else (
            "霜/膏类" if "霜" in title else "精华/液类"))
    if "眼油" in title:
        form = "纯油（眼部精华油）"
    core_from = {}

    def dim(val, key):
        """val 取自评价词云；为空则用视频侧语料兜底，并记录来源"""
        if val:
            core_from[key] = "评价词云"
            return val
        fb = fallback(key)
        core_from[key] = "视频文案/内容词云兜底" if fb else "无（该链接评价与视频均未出现）"
        return fb

    core = {
        "内料形态": form,
        "包装形式": ("瓶装" if any(k in title for k in ("瓶", "油")) else "盒装/袋装")
                    + "（详情页未直接标注，需以实拍为准）",
        "功效": dim(cat("功效", 12) or hits_of(title, GOOD), "功效"),
        "主打成分": dim(cat("成分", 12), "成分"),
        "香型/气味": dim(cat("气味", 10), "气味"),
        "质地/肤感": dim(cat("质地", 10), "质地"),
        "规格": dim(cat("规格", 8), "规格"),
        "目标受众词": dim(cat("目标受众", 8), "受众"),
        "使用场景": dim(cat("使用场景", 8), "场景"),
        "用户痛点词": dim(cat("痛点问题", 10), "痛点"),
        "技术/工艺": dim(cat("技术工艺", 8), "技术"),
        "外观/包装词": dim(cat("外观", 8) + cat("包装", 8), "外观"),
        "美妆概念": dim(cat("美妆概念", 8), "美妆概念"),
    }

    # ---- 货架策略（2.3） ----
    price = c.get("price_est")
    spec_txt = " ".join(core["规格"]) + " " + (d.get("attr_text") or "")[:300]
    gram = None
    m = re.search(r"(\d+(?:\.\d+)?)\s*(g|g装|克|ml|毫升|片|支)", spec_txt)
    if m and price:
        v = float(m.group(1))
        if v > 0:
            gram = round(float(price) / v, 2)
    act_words = [w for w in ACT if w in title]
    sku_type = "套装/多件装" if any(k in title for k in ("拍一发", "套装", "2件", "两件", "组合", "礼盒", "×2")) else "单品"
    pos = "引流款（低价高佣金）" if (price and price <= 60) else (
        "利润款（中高价位）" if (price and price >= 150) else "主推款/复购款")
    shelf = {
        "现行价（推算）": ("¥%s" % price) if price else "无佣金标注，无法反推",
        "佣金": "%s / %s" % (c.get("commission_rate") or "—", c.get("commission_fee") or "—"),
        "规格信号": "、".join(core["规格"][:5]) or (d.get("attr_text") or "")[:60] or "详情页未给规格文本",
        "每克/每单位均价": ("¥%s" % gram) if gram else "缺规格或价格，无法计算",
        "SKU 形态": sku_type,
        "货架定位": pos,
        "标题里的活动词": "、".join(act_words) if act_words else "无（日常价挂车）",
        "上架时间": c.get("onsale_date") or "—",
        "累计评价": c.get("reviews") or "—",
        "好评率": c.get("praise") or "—",
    }

    # ---- 爆款视频拆解 ----
    viral = []
    for v in (d.get("videos") or []):
        fans = v.get("fansNum") or numw(v.get("fans"))
        bt = v.get("bloggerType") or ""
        desc = v.get("desc") or ""
        dur = parse_dur(v.get("duration"))
        excluded = []
        if fans and fans > 1000000:
            excluded.append("粉丝>100万（大V，不可复制）")
        if any(k in bt for k in ("旗舰店", "品牌", "自营", "官方")):
            excluded.append("品牌自营账号（品牌广告）")
        if re.search(r"(9\.9|免单|抽奖|免费送)", desc):
            excluded.append("福利款")
        tier = ("中腰部(1万-50万)" if 10000 <= fans <= 500000 else
                ("腰部以上(50万+)") if fans > 500000 else "尾部(<1万)")
        hits = {"pain": hits_of(desc, PAIN), "benefit": hits_of(desc, GOOD),
                "proof": hits_of(desc, PROOF), "act": hits_of(desc, ACT), "cta": hits_of(desc, CTA),
                "scene": hits_of(desc, SCENE), "crowd": hits_of(desc, CROWD),
                "ingre": hits_of(desc, INGRE)}
        hook = hook_type(desc, dur, bt)
        ft = frame_type(desc, bt, dur, hits, hook)
        lines = copy_lines(desc)
        # 话术结构 = 文案逐句的类型序列（只依据文案，不做画面推测）
        seq = []
        for l in lines:
            if l["type"] not in seq:
                seq.append(l["type"])
        viral.append({
            "awemeId": v.get("awemeId"), "share": v.get("shareUrl"), "cover": vimg(v.get("awemeId")),
            "rawCover": v.get("cover"), "desc": desc, "dur": v.get("duration"), "durs": dur,
            "blogger": v.get("blogger"), "displayId": v.get("displayId"), "fans": v.get("fans"),
            "fansNum": fans, "bt": bt, "tag": v.get("tag"), "prov": v.get("province"),
            "home": v.get("douyinHome"), "pub": v.get("pubTime"), "gmv": v.get("gmv"),
            "volume": v.get("volume"), "gpm": v.get("gpm"),
            "tier": tier, "excluded": excluded, "keep": not excluded,
            "hook": hook, "seq": seq, "frameType": ft, "lines": lines,
            "time": v.get("pubTime") or v.get("pub") or "—",
            "pain": hits["pain"], "benefit": hits["benefit"][:3], "proof": hits["proof"][:3],
            "act": hits["act"][:3], "cta": hits["cta"][:3],
            "scene": hits["scene"][:3], "crowd": hits["crowd"][:3], "ingre": hits["ingre"][:3],
            # 真实引用：从文案里抽出的原句，而不是孤立的词表词
            "painC": clauses_hit(desc, PAIN, 3),
            "beneC": clauses_hit(desc, GOOD, 3),
            "sceneC": clauses_hit(desc, SCENE, 2),
            "crowdC": clauses_hit(desc, CROWD, 2),
        })
    for v in viral:
        v["analysis"] = analysis_of(v)

    # ---- 该链接全部带货视频的「内容总结」：反复提及词 + 分类 ----
    vsummary = build_vsummary(viral)

    # ---- 竞品分析2 口径的产品卖点 / 痛点 / 配赠 / 工厂 ----
    tech = cat("技术工艺", 10)
    ingre = cat("成分", 12)
    smell = cat("气味", 8)
    endorse = [w for w in (hits_of(title, PROOF) + cat("美妆概念", 6)) if w]
    beian = ""
    m = re.search(r"(备案[^，。；\n]{0,40}|[组国]妆[GW][字准][^，。；\n]{0,20})", (d.get("attr_text") or ""))
    if m:
        beian = m.group(1)
    sell = {
        "功能": "／".join((cat("功效", 6) or hits_of(title, GOOD))[:5]) or "—",
        "一句话卖点": one_line_sp(title, brand, ""),
        "主打技术": "／".join(tech[:4]) or "评价词云未出现技术/工艺词（多为常规涂抹型）",
        "主打成分": "／".join(ingre[:8]) or "—",
        "香味": "／".join(smell[:5]) or "评价词云未出现气味词（多为无香/淡香）",
        "背书": "／".join(endorse[:5]) or "标题与词云未见显性背书",
        "备案成分": beian or "未给备案 / 成分表，需以抖店详情页为准",
    }
    pain_pts = (cat("痛点问题", 10) or hits_of(title, PAIN))[:6]
    gift = "／".join(hits_of(title, F_GIFTW)) or "标题未标赠品（默认无配赠）"
    factory = "／".join([x for x in [brand, c.get("shop")] if x]) or "—"

    # 排序：可复制的（中腰部、非品牌、非福利）优先，再按 GMV
    viral.sort(key=lambda x: (0 if x["keep"] else 1, -numw(x["gmv"])))
    keep10 = [v for v in viral if v["keep"]][:10]
    if len(keep10) < 10:
        keep10 += [v for v in viral if not v["keep"]][:10 - len(keep10)]

    return {
        "i": i, "gid": gid, "title": title, "brand": brand or "（飞瓜未标品牌）",
        "shop": c.get("shop") or "—", "shopScore": c.get("shop_score") or "—",
        "cate": cp.get("L3") or c.get("cate") or "未分类",
        "cateRaw": c.get("cate") or "", "l1": cp.get("L1") or L1_NAME,
        "l2": cp.get("L2") or "", "l3": cp.get("L3") or "",
        "rank": c.get("_l3rank") or 1, "rankAll": c.get("榜_rank") or i,
        "rankNo": c.get("rank_no"), "rankPeriod": c.get("rank_period") or "月榜",
        "price": price, "cover": cover(gid),
        "link": (c.get("douyin_links") or [None])[0],
        "fg": "https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=%s&tab=overview&ts=%s&sign=%s"
              % (gid, c.get("ts"), c.get("sign")),
        "sales": c.get("销售额") or "—", "volume": c.get("销量") or "—",
        "orders": c.get("订单量") or "—", "views": c.get("浏览量") or "—",
        "conv": c.get("转化率") or "—", "nV": c.get("带货视频") or "0",
        "nL": c.get("带货直播") or "0", "nT": c.get("带货达人") or "0",
        "onSale": c.get("onsale_date") or "—", "reviews": c.get("reviews") or "—",
        "praise": c.get("praise") or "—", "upd": c.get("update_time") or "—",
        "channel": c.get("channel") or [], "selltype": c.get("selltype") or [],
        "sellingPoint": one_line_sp(title, brand, ""),
        "audienceLine": audience_line, "audienceDetail": audience_detail,
        "nReviews": p.get("n_reviews"), "badRate": p.get("rate_bad"),
        "midRate": p.get("rate_mid"), "goodRate": p.get("rate_good"),
        "goodWords": good_words, "badWords": bad_words,
        "words": p.get("words") or [],
        "cats": {k: [{"k": x["k"], "c": x["c"], "r": x["r"]} for x in (v or [])[:14]] for k, v in cats.items()},
        "core": core, "coreFrom": core_from, "shelf": shelf,
        "sell": sell, "painPoints": pain_pts, "gift": gift, "factory": factory,
        "goodCmt": [x.get("t") for g in reviews_sample for x in g["items"]][:10],
        "badCmt": cat("痛点问题", 10),
        "attr": (d.get("attr_text") or "").strip()[:900],
        "reviewsSample": reviews_sample,
        "viral": keep10, "viralAll": len(viral), "viralExcluded": sum(1 for v in viral if not v["keep"]),
        "vsummary": vsummary,
        "videosTotal": d.get("videos_total") or len(d.get("videos") or []),
        "bloggersTotal": d.get("bloggers_total"),
        "bloggers": [{"n": b.get("name"), "lvl": b.get("level"), "fans": b.get("fans"),
                      "cert": b.get("cert") or b.get("tag"), "gmv": b.get("gmv"), "vol": b.get("volume"),
                      "aw": b.get("awemeCnt"), "lv": b.get("liveCnt"), "lgmv": b.get("liveGmv"),
                      "home": b.get("home")} for b in (d.get("bloggers") or [])[:20]],
        "conc": ((d.get("concentration") or {}).get("top5") or []),
        "btypes": d.get("blogger_types") or [],
        "wordcloud": [{"k": x.get("kw"), "c": x.get("cnt"), "r": x.get("ratio")}
                      for x in (d.get("wordcloud") or [])[:40]],
        "sortkey": {"sv": numw(c.get("销售额")), "vol": numw(c.get("销量")),
                    "vw": numw(c.get("浏览量")), "cv": numrate(c.get("转化率")),
                    "vid": numw(c.get("带货视频")), "tal": numw(c.get("带货达人")),
                    "pr": price or 0, "cm": pct(c.get("commission_rate")),
                    "bad": p.get("rate_bad") if p.get("rate_bad") is not None else 99},
    }


PRODUCTS = [build_product(i + 1, c) for i, c in enumerate(items)]

DB = {
    "meta": {
        "n": len(PRODUCTS), "now": NOW, "range": RANGE_D,
        "nDeep": sum(1 for p in PRODUCTS if p["viral"]),
        "nCov": sum(1 for p in PRODUCTS if p["cover"]),
        "nAud": sum(1 for p in PRODUCTS if p["badRate"] is not None),
        "nViral": sum(len(p["viral"]) for p in PRODUCTS),
        "nEye": sum(1 for p in PRODUCTS if p["l2"] == "眼部护理"),
        "nFace": sum(1 for p in PRODUCTS if p["l2"] == "面部护理"),
        "src": "飞瓜数据·抖音版（商品销售榜 → 一级类目「个护家清」→ 月榜）",
        "kw": "眼部护理 8 词（眼油/眼部精华/眼精华/眼霜/眼膜/眼贴/眼周/眼部护理）"
              "＋面部护理 6 类（面膜/防晒/洁面/爽肤水/面霜/面部精华，各 3 词）",
    },
    "products": PRODUCTS,
}
OUTFILE = os.path.join(BASE, "index.html")
TEMPLATE = open(os.path.join(BASE, "tmp", "_spa_tpl.html"), encoding="utf-8").read()
html_out = TEMPLATE.replace("/*__DB__*/",
                            json.dumps(DB, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
open(OUTFILE, "w", encoding="utf-8").write(html_out)
print("已生成 index.html  %.2f MB（%d 个商品 / %d 张卡有图 / %d 个有画像 / %d 条拆解视频）"
      % (len(html_out) / 1e6, len(PRODUCTS), DB["meta"]["nCov"], DB["meta"]["nAud"], DB["meta"]["nViral"]))
