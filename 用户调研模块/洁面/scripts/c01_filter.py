# -*- coding: utf-8 -*-
"""
c01_filter.py — 洁面语料去水军过滤（沿用眼油模块 R1-R12，词表换成洁面口径）
输入: raw/xhs_output/*.json
输出: data/raw_comments.json   保留语料（已脱敏）
      data/filtered_log.json  被过滤语料 + 剔除原因（可审计）
"""
import json, re, glob, os, sys, hashlib
from collections import Counter, defaultdict
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE, "raw", "xhs_output")
DATA_DIR = os.path.join(BASE, "data")
os.makedirs(DATA_DIR, exist_ok=True)
TODAY = datetime.now().strftime("%Y-%m-%d")

# ---------- 洁面 / 洗面奶 品类词 ----------
CATEGORY_WORDS = [
    "洗面奶", "洁面", "洗颜", "洗脸", "洗面", "氨基酸", "皂基", "泡沫", "泡泡", "慕斯",
    "洁面乳", "洗面乳", "洁面膏", "洁面奶", "清洁力", "洗得干净", "洗不干净", "洗不掉",
    "紧绷", "假滑", "干涩", "拔干", "控油", "出油", "油皮", "干皮", "混油", "混干",
    "敏感肌", "痘肌", "痘痘", "闭口", "黑头", "毛孔", "泛红", "刺痛", "过敏", "烂脸",
    "温和", "不刺激", "刺激", "保湿", "香精", "味道", "起泡", "打泡", "冲洗", "洗完",
    "洗后", "表活", "弱酸", "sls", "皂", "膏体", "洗感", "肤感", "回购", "空瓶",
    "搓", "清爽", "滋润", "干干净净", "洗干净",
]
BRAND_WORDS = [
    "芙丽芳丝", "freeplus", "elta", "珂润", "curel", "薇诺娜", "至本", "逐本", "hfp",
    "半亩花田", "谷雨", "优时颜", "珀莱雅", "薇姿", "理肤泉", "雅漾", "丝塔芙",
    "cerave", "适乐肤", "大宝", "旁氏", "妮维雅", "曼秀雷敦", "资生堂", "洗颜专科",
    "珊珂", "senka", "悦诗风吟", "innisfree", "fancl", "芳珂", "dhc", "城野医生",
    "石泽研究所", "suisai", "嘉娜宝", "kanebo", "诗留美屋", "牛乳石碱", "花印",
    "玉泽", "瑷尔博士", "可复美", "敷尔佳", "欧莱雅", "olay", "露得清", "neutrogena",
    "可伶可俐", "相宜本草", "百雀羚", "自然堂", "韩束", "御泥坊", "一叶子", "膜法世家",
    "阿芙", "林清轩", "兰蔻", "sk-ii", "黛珂", "雪肌精", "高丝", "kose", "溪木源",
    "肌肤未来", "rnw", "unny", "柳丝木", "摇滚动物园", "优斐斯", "博乐达",
]

R1_PATTERNS = re.compile(
    r"加V|加薇|加微|私信|点我头像|点击主页|主页联系|淘口令|淘宝|天猫|京东|拼多多|"
    r"http[s]?://|www\.|优惠券|领券|链接在|低价出|代购|代拍|返现|返利|刷单|接广告|"
    r"互关|互赞|涨粉|引流|货源|一手价|批发", re.I)
R7_PATTERNS = re.compile(r"好物|优选|严选|福利|返利|优惠券|折扣|代购|旗舰店|官方旗舰|客服|"
                         r"批发|厂家|工厂|清仓|特卖|团购|带货|甄选", re.I)
R9_PATTERNS = re.compile(r"太贵|价格.*贵|物流|快递|发货|包装|瓶口|按压.*难|盖.*松")
R12_PATTERNS = re.compile(r"(?<![a-zA-Z])tao(?![a-zA-Z])|去某宝|某宝|置顶评论|戳我|私我|主页有|点击主页", re.I)


def anon_id(uid):
    return hashlib.md5(str(uid).encode("utf-8")).hexdigest()[:12]


def hits_any(text, words):
    t = text.lower()
    return [w for w in words if w.lower() in t]


def norm_time(t):
    if t is None:
        return None, None
    if isinstance(t, (int, float)):
        ts = t if t < 1e12 else t / 1000
        from datetime import datetime as _dt
        dt = _dt.fromtimestamp(ts)
    else:
        from datetime import datetime as _dt
        s = str(t)
        dt = None
        try:
            dt = _dt.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
        except Exception:
            try:
                dt = _dt.strptime(s[:10], "%Y-%m-%d")
            except Exception:
                pass
    if not dt:
        return str(t), None
    return dt.strftime("%Y-%m-%d %H:%M:%S"), dt.strftime("%Y-%m-%d")


def main():
    files = sorted(glob.glob(os.path.join(RAW_DIR, "*.json")))
    if not files:
        print("[warn] 没有笔记 JSON，先跑 c07", flush=True)
        sys.exit(0)
    kept, filtered = [], []
    kept_texts = set()
    note_sets = defaultdict(set)
    per_note_ip = defaultdict(Counter)
    all_rows = []
    note_meta = {}

    for f in files:
        try:
            doc = json.load(open(f, encoding="utf-8"))
        except Exception as e:
            print(f"[skip] {os.path.basename(f)}: {e}", flush=True)
            continue
        note_id = doc.get("nid") or os.path.basename(f).replace(".json", "")
        note_title = doc.get("title", "")
        note_meta[note_id] = {"title": note_title, "url": doc.get("url", ""),
                              "author": doc.get("author", ""), "keyword": doc.get("keyword", ""),
                              "tag": doc.get("tag", ""), "likes": doc.get("likes", ""),
                              "desc": doc.get("desc", "")}
        if doc.get("desc"):
            all_rows.append({"id": note_id + "_desc", "nickname": doc.get("author", ""),
                             "userId": note_id, "content": doc["desc"][:400],
                             "likeCount": 0, "ipLocation": None,
                             "createTime": doc.get("fetchDate"), "_noteId": note_id, "_isDesc": True})
        for c in (doc.get("comments") or []):
            for cc in (c.get("subComments") or []):
                cc["_parent"] = c.get("id")
            for c2 in [c] + (c.get("subComments") or []):
                c2["_noteId"] = note_id
                all_rows.append(c2)

    for r in all_rows:
        content = (r.get("content") or "").strip()
        if content:
            note_sets[content].add(r["_noteId"])
    dup_texts = {t for t, notes in note_sets.items() if len(notes) >= 3}
    for r in all_rows:
        per_note_ip[r["_noteId"]][r.get("ipLocation") or "未知"] += 1

    def filter_one(r):
        content = (r.get("content") or "").strip()
        nickname = r.get("nickname") or ""
        if not content:
            return False, "R2", "空内容"
        if R1_PATTERNS.search(content):
            return False, "R1", "营销文本模式"
        cat_hit = hits_any(content, CATEGORY_WORDS)
        brand_hit = hits_any(content, BRAND_WORDS)
        if len(content) < 6 and not cat_hit and not brand_hit:
            return False, "R2", "超短且无信息"
        if not cat_hit and not brand_hit:
            return False, "R3", "与品类/品牌均无关（低相关）"
        if content in dup_texts:
            return False, "R4", "同文案复刷簇"
        if R7_PATTERNS.search(nickname):
            return False, "R7", "营销号昵称特征"
        if "#" in content and len(re.sub(r"#[^\s#]+", "", content).strip()) < 10:
            return False, "R11", "纯话题标签串，无实质表述"
        if R12_PATTERNS.search(content):
            return False, "R12", "作者营销/购买引导"
        if content in kept_texts:
            return False, "R10", "重复语料（同内容只计一条）"
        return True, None, None

    for r in all_rows:
        content = (r.get("content") or "").strip()
        norm, day = norm_time(r.get("createTime"))
        ok, rule, reason = filter_one(r)
        rec = {"id": r.get("id"), "noteId": r["_noteId"], "isSub": bool(r.get("_parent")),
               "isNoteDesc": bool(r.get("_isDesc")),
               "content": content, "likeCount": r.get("likeCount", 0),
               "createTime": norm, "date": day, "fetchDate": TODAY,
               "ipLocation": r.get("ipLocation"), "userHash": anon_id(r.get("userId")),
               "r9NonFixable": bool(R9_PATTERNS.search(content)),
               "categoryHits": hits_any(content, CATEGORY_WORDS),
               "brandHits": hits_any(content, BRAND_WORDS)}
        if ok:
            kept_texts.add(content)
            kept.append(rec)
        else:
            rec["filterRule"], rec["filterReason"] = rule, reason
            filtered.append(rec)

    json.dump({"fetchedAt": TODAY, "count": len(kept), "noteMeta": note_meta, "comments": kept},
              open(os.path.join(DATA_DIR, "raw_comments.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    rule_counter = Counter(x.get("filterRule") for x in filtered)
    json.dump({"fetchedAt": TODAY, "count": len(filtered),
               "ruleSummary": dict(rule_counter), "filtered": filtered},
              open(os.path.join(DATA_DIR, "filtered_log.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"[done] 输入 {len(all_rows)} 条 → 保留 {len(kept)} 条，过滤 {len(filtered)} 条", flush=True)
    for k, v in sorted(rule_counter.items()):
        print(f"   {k}: {v} 条", flush=True)


if __name__ == "__main__":
    main()
