# -*- coding: utf-8 -*-
"""
01_filter_comments.py — 小红书评论去水军过滤（R1-R9）
输入: raw/xhs_output/*.json  (xhs-note-scraper 输出格式)
输出: data/raw_comments.json   — 保留的评论（已脱敏）
      data/filtered_log.json  — 被过滤评论 + 剔除原因（可审计）
运行: python 01_filter_comments.py
"""
import json, re, glob, os, sys, hashlib
from collections import Counter, defaultdict
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 用户调研模块/
RAW_DIR = os.path.join(BASE, "raw", "xhs_output")
DATA_DIR = os.path.join(BASE, "data")
os.makedirs(DATA_DIR, exist_ok=True)
TODAY = datetime.now().strftime("%Y-%m-%d")

# ---------- 词表 ----------
# R3 品类相关性词表（眼部护理核心词，30+）
CATEGORY_WORDS = [
    "眼油", "眼霜", "眼部精华", "眼部", "眼周", "眼纹", "细纹", "干纹", "泪沟", "黑眼圈",
    "眼袋", "脂肪粒", "脂肪球", "辣眼", "刺眼", "搓泥", "卡粉", "搓开", "吸收", "油腻",
    "以油养肤", "抗老", "抗皱", "紧致", "淡纹", "祛皱", "皱纹", "眼贴", "眼膜", "按摩",
    "手法", "涂眼", "抹眼", "眼周护理", "眼部护理", "去纹", "眼干",
]
# 品牌词（命中任意一个也算相关）
BRAND_WORDS = [
    "白云山", "阿芙", "melvita", "蜜葳特", "赏容", "olay", "欧莱雅", "珀莱雅", "韩束",
    "自然堂", "薇诺娜", "华熙", "润百颜", "夸迪", "林清轩", "逐本", "至本", "haba",
    "科颜氏", "兰蔻", "雅诗兰黛", "赫莲娜", "娇韵诗", "悦薇", "小棕瓶", "红腰子",
]
# R1 营销文本模式
R1_PATTERNS = re.compile(
    r"加V|加薇|加微|私信|点我头像|点击主页|主页联系|淘口令|淘宝|天猫|京东|拼多多|"
    r"http[s]?://|www\.|优惠券|领券|链接在|低价出|代购|代拍|返现|返利|刷单|接广告|"
    r"互关|互赞|涨粉|引流|货源|一手价|批发", re.I)
# R7 营销号昵称特征
R7_PATTERNS = re.compile(r"好物|优选|严选|福利|返利|优惠券|折扣|代购|旗舰店|官方旗舰|客服|"
                         r"批发|厂家|工厂|清仓|特卖|团购|带货|甄选", re.I)
# R9 不可改良差评（保留但不进痛点榜）
R9_PATTERNS = re.compile(r"太贵|价格.*贵|物流|快递|发货|包装|瓶口|滴管.*难|按压.*难")
# R12 作者营销 / 购买引导（作者置顶推广、引流到站外购买）—— 2026-09-24 新增
R12_PATTERNS = re.compile(r"(?<![a-zA-Z])tao(?![a-zA-Z])|去某宝|某宝|置顶评论|戳我|私我|主页有|点击主页", re.I)
# R2 例外：超短但含品类词的保留
def norm_time(t):
    """createTime 兼容：数字时间戳(秒/毫秒) / 日期字符串"""
    if t is None:
        return None, None
    if isinstance(t, (int, float)):
        ts = t if t < 1e12 else t / 1000
        dt = datetime.fromtimestamp(ts)
    else:
        s = str(t)
        try:
            dt = datetime.fromtimestamp(int(s[:10]) if len(s) >= 10 and s.isdigit() else int(s) / 1000) if s.isdigit() else datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
        except Exception:
            dt = None
            try:
                dt = datetime.strptime(str(s)[:10], "%Y-%m-%d")
            except Exception:
                pass
    if not dt:
        return str(t), None
    return dt.strftime("%Y-%m-%d %H:%M:%S"), dt.strftime("%Y-%m-%d")

def anon_id(uid):
    """脱敏：不可逆 hash，审计可对簇但不暴露账号"""
    return hashlib.md5(str(uid).encode("utf-8")).hexdigest()[:12]

def hits_any(text, words):
    t = text.lower()
    return [w for w in words if w.lower() in t]

def main():
    files = sorted(glob.glob(os.path.join(RAW_DIR, "*.json")))
    if not files:
        print(f"[warn] {RAW_DIR} 下没有笔记 JSON，先跑 xhs-note-scraper 批量采集")
        sys.exit(0)
    kept, filtered = [], []
    kept_texts = set()   # R10 去重：已保留的语料原文
    seen_text = defaultdict(list)   # content -> [(userId, noteId)]  R4
    per_note_ip = defaultdict(Counter)  # noteId -> ipCounter  R5
    all_rows = []

    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                doc = json.load(fh)
        except Exception as e:
            print(f"[skip] 解析失败 {os.path.basename(f)}: {e}")
            continue
        # 兼容两种格式：① xhs-note-scraper（note/comments）② Kimi 采集（title/desc/comments）
        if isinstance(doc.get("note"), dict):
            note = doc["note"]
            note_id = note.get("noteId") or os.path.basename(f).replace(".json", "")
            note_title = note.get("title", "")
        else:
            note_id = doc.get("nid") or os.path.basename(f).replace(".json", "")
            note_title = doc.get("title", "")
            # 笔记正文也作为一条语料计入（无评论时正文兜底）
            if doc.get("desc"):
                doc.setdefault("comments", []).insert(0, {
                    "id": note_id + "_desc", "nickname": doc.get("author", ""),
                    "userId": note_id, "content": doc["desc"][:300],
                    "likeCount": 0, "ipLocation": None, "createTime": doc.get("fetchDate")})
        comments = doc.get("comments", []) or []
        for c in comments:
            for cc in (c.get("subComments") or []):
                cc["_parent"] = c.get("id")
            flat = [c] + (c.get("subComments") or [])
            for c2 in flat:
                c2["_noteId"] = note_id
                all_rows.append(c2)

    # 预扫描：R4 相同文案簇、R5 per-note IP 分布、R6 时间簇
    text_sig = defaultdict(list)
    note_sets = defaultdict(set)   # content -> 出现的笔记集合（跨笔记复刷才是真水军）
    for r in all_rows:
        content = (r.get("content") or "").strip()
        if content:
            text_sig[content].append((r.get("userId"), r["_noteId"]))
            note_sets[content].add(r["_noteId"])
    # 同文案出现在 >=3 个不同笔记 → 判定为模板复刷
    dup_texts = {t for t, notes in note_sets.items() if len(notes) >= 3}
    for r in all_rows:
        ip = r.get("ipLocation") or "未知"
        per_note_ip[r["_noteId"]][ip] += 1

    def filter_one(r):
        """返回 (保留?, 规则码, 原因)"""
        content = (r.get("content") or "").strip()
        nickname = r.get("nickname") or ""
        note_id = r["_noteId"]
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
        # R8 官方/作者自评（xhs-note-scraper 无显式标记，按昵称与作者一致判断）
        # R11 纯话题标签串：剥掉 #标签 后没有实质表述 —— 2026-09-24 新增
        if "#" in content and len(re.sub(r"#[^\s#]+", "", content).strip()) < 10:
            return False, "R11", "纯话题标签串，无实质表述"
        # R12 作者营销 / 购买引导 —— 2026-09-24 新增
        if R12_PATTERNS.search(content):
            return False, "R12", "作者营销/购买引导"
        # R10 重复语料：同一句话只计一条（此前重复计数导致频次虚高）—— 2026-09-24 新增
        if content in kept_texts:
            return False, "R10", "重复语料（同内容只计一条）"
        return True, None, None

    for r in all_rows:
        note_id = r["_noteId"]
        content = (r.get("content") or "").strip()
        norm, day = norm_time(r.get("createTime"))
        ok, rule, reason = filter_one(r)
        rec = {
            "id": r.get("id"), "noteId": note_id, "isSub": bool(r.get("_parent")),
            "content": content, "likeCount": r.get("likeCount", 0),
            "createTime": norm, "date": day, "fetchDate": TODAY,
            "ipLocation": r.get("ipLocation"), "userHash": anon_id(r.get("userId")),
            "r9NonFixable": bool(R9_PATTERNS.search(content)),
            "categoryHits": hits_any(content, CATEGORY_WORDS),
            "brandHits": hits_any(content, BRAND_WORDS),
        }
        if ok:
            kept_texts.add(content)
            kept.append(rec)
        else:
            rec["filterRule"], rec["filterReason"] = rule, reason
            filtered.append(rec)

    # R5 / R6 需要 kept 之后按 note 聚合二次过滤
    keep2 = []
    for r in kept:
        ip = r.get("ipLocation") or ""
        # 无 IP 属地数据时不启用 R5（否则会误杀整篇）
        if not ip or ip == "未知":
            keep2.append(r); continue
        cnt = per_note_ip[r["noteId"]][ip]
        total = sum(per_note_ip[r["noteId"]].values()) or 1
        if cnt / total > 0.4 and cnt >= 5:
            r2 = dict(r); r2.update({"filterRule": "R5", "filterReason": f"同IP属地占比>{cnt*100//total}%（疑似水军聚集）"})
            filtered.append(r2); continue
        keep2.append(r)
    # R6：同笔记内 createTime 集中同一小时且 likeCount=0 ≥8 条 → 整簇剔除
    hour_key = defaultdict(list)
    for r in keep2:
        if r["createTime"]:
            hour_key[(r["noteId"], r["createTime"][:13])].append(r)
    drop6 = set()
    for k, rows in hour_key.items():
        if len(rows) >= 8 and all((x.get("likeCount") or 0) == 0 for x in rows):
            drop6.update(x["id"] for x in rows)
    if drop6:
        final, d6 = [], []
        for r in keep2:
            if r["id"] in drop6:
                r2 = dict(r); r2.update({"filterRule": "R6", "filterReason": "零赞同小时集中爆发"}); d6.append(r2)
            else:
                final.append(r)
        keep2, d6 = final, d6
        filtered.extend(d6)

    with open(os.path.join(DATA_DIR, "raw_comments.json"), "w", encoding="utf-8") as f:
        json.dump({"fetchedAt": TODAY, "count": len(keep2), "comments": keep2}, f, ensure_ascii=False, indent=1)
    rule_counter = Counter(x.get("filterRule") for x in filtered)
    with open(os.path.join(DATA_DIR, "filtered_log.json"), "w", encoding="utf-8") as f:
        json.dump({"fetchedAt": TODAY, "count": len(filtered),
                   "ruleSummary": dict(rule_counter), "filtered": filtered},
                  f, ensure_ascii=False, indent=1)

    print(f"[done] 输入评论 {len(all_rows)} 条 → 保留 {len(keep2)} 条，过滤 {len(filtered)} 条")
    for k, v in sorted(rule_counter.items()):
        print(f"   {k}: {v} 条")
    print("[next] python 02_cluster_keywords.py 生成 TOP5")

if __name__ == "__main__":
    main()
