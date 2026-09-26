# -*- coding: utf-8 -*-
"""
02_cluster_keywords.py — 需求/痛点 TOP5 聚类（词表驱动，零第三方依赖）
输入: data/raw_comments.json（01 的输出，已去水军）
输出: data/needs_top5.json / data/painpoints_top5.json / data/must_fix.json / data/lexicon.json
规则: 每条 TOP 结论强制附 2-3 句买家原话；差评只留可改良项（R9 已标记的不进痛点榜）
运行: python 02_cluster_keywords.py
"""
import json, re, os, sys
from collections import Counter, defaultdict
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = lambda n: os.path.join(BASE, "data", n)
TODAY = datetime.now().strftime("%Y-%m-%d")

# ---------- 需求/痛点 桶定义（正则桶 → 桶名） ----------
NEED_BUCKETS = [
    ("淡化细纹 / 眼周抗老", r"细纹|干纹|抗老|抗皱|淡纹|祛皱|皱纹|紧致|松弛"),
    ("黑眼圈改善", r"黑眼圈|眼袋|泪沟|暗沉"),
    ("好吸收不油腻", r"好吸收|易吸收|不油|清爽|不腻|吸收快"),
    ("平价大碗 / 学生党友好", r"平价|便宜|学生|穷鬼|性价比|大碗|百元内|实惠"),
    ("手法简单易上手", r"手法|怎么涂|怎么用|教程|按摩|步骤"),
    ("温和不刺激", r"温和|不辣|不刺激|敏感肌|孕妇|无酒精"),
]
PAIN_BUCKETS = [
    ("卡粉 / 搓泥", r"卡粉|搓泥|搓开|搓泥感|不服帖|搓泥了"),
    ("分不清是什么纹（认知模糊）", r"这是.*纹|什么纹|不知道.*纹|是干纹还是|泪沟还是|帮忙看看"),
    ("辣眼 / 刺激", r"辣眼|刺眼|熏眼|刺痛|蛰|蜇|扎眼|辣眼睛"),
    ("太油腻 / 长脂肪粒", r"太油|油乎乎|闷痘|脂肪粒|脂肪球|长粒|起粒"),
    ("没效果 / 怕智商税", r"没用|无效|智商税|白买|踩雷|交钱|噱头|一个月.*没|还是老样"),
    ("难清洗 / 假滑", r"洗不掉|难洗|假滑|糊眼睛|糊得慌"),
    ("长脂肪粒", None),  # 占位防重复，实际并入上面
]
R9_PAT = re.compile(r"太贵|价格.*贵|物流|快递|发货|包装")

def load_comments():
    with open(DATA("raw_comments.json"), encoding="utf-8") as f:
        doc = json.load(f)
    return [c for c in doc["comments"]]  # 已过滤；R9 标记保留

def pick_quotes(rows, n=3):
    """按点赞降序挑 n 条原话"""
    rows = sorted(rows, key=lambda x: -(x.get("likeCount") or 0))
    out = []
    for r in rows[:n]:
        out.append({"text": r["content"][:80],
                    "source": f"小红书笔记 {r['noteId']} · {r.get('date') or '时间未知'}",
                    "likes": r.get("likeCount", 0)})
    return out

def bucketize(rows, buckets):
    """返回 [(桶名, 命中行列表, 频次)] 按频次降序"""
    assigned = defaultdict(list)
    for r in rows:
        text = r["content"]
        for name, pat in buckets:
            if pat and re.search(pat, text):
                assigned[name].append(r)
                break  # 每条评论只归入第一个命中桶，保证频次不重复计数
    ranked = sorted(assigned.items(), key=lambda kv: -len(kv[1]))
    return [(name, rows_, len(rows_)) for name, rows_ in ranked if len(rows_) >= 2]

def main():
    rows = load_comments()
    if not rows:
        print("[warn] raw_comments.json 为空，先完成采集+01")
        sys.exit(0)

    # 需求 TOP5
    need_ranked = bucketize(rows, NEED_BUCKETS)[:5]
    needs = {"generatedAt": TODAY, "items": [
        {"name": name, "count": cnt, "quotes": pick_quotes(rs)}
        for name, rs, cnt in need_ranked]}

    # 痛点 TOP5：排除 R9 不可改良 + 桶内剔除不可改良
    fixable = [r for r in rows if not r.get("r9NonFixable")]
    pain_ranked = bucketize(fixable, [b for b in PAIN_BUCKETS if b[1]])[:5]
    pains = {"generatedAt": TODAY, "items": [
        {"name": name, "count": cnt, "quotes": pick_quotes(rs)}
        for name, rs, cnt in pain_ranked]}

    # 研发红线：从痛点中取，要求 ≥2 独立笔记来源
    must_fix = {"generatedAt": TODAY, "items": []}
    for name, rs, cnt in pain_ranked:
        notes = {r["noteId"] for r in rs}
        if len(notes) >= 2:
            must_fix["items"].append({
                "name": name,
                "why": f"命中 {cnt} 条评论、来自 {len(notes)} 个独立笔记，属可改良问题",
                "evidence": "；".join(f"「{q['text']}」" for q in pick_quotes(rs, 2))})

    # 词库三栏 + 词云
    good_pat = re.compile("|".join(p for _, p in NEED_BUCKETS if p))
    def words_from(rows_, lex_pat=None):
        cnt = Counter()
        for r in rows_:
            for h in r.get("categoryHits", []):
                cnt[h] += 1
        return cnt
    good_cnt = words_from([r for r in rows if good_pat.search(r["content"])])
    bad_cnt = words_from(fixable)
    say_cnt = Counter()
    # 口语表达：抓「不X」「好X」高频二连
    for r in rows:
        for m in re.findall(r"[不好超真的确贼巨蛮挺][油润干爽滑香贵妙]", r["content"]):
            say_cnt[m] += 1
    lexicon = {
        "generatedAt": TODAY,
        "good": [{"word": w, "count": c, "sensitive": w in ("淡纹", "抗皱", "祛皱")} for w, c in good_cnt.most_common(15)],
        "bad": [{"word": w, "count": c, "sensitive": False} for w, c in bad_cnt.most_common(10) if re.search(r"卡粉|搓泥|辣|刺激|油|脂肪|糊|洗不掉|没效果", w)],
        "say": [{"word": w, "count": c, "sensitive": False} for w, c in say_cnt.most_common(15)],
        "cloud": [],  # 前端由 good+bad+say 拼接渲染
    }
    cloud_pool = ([{**x, "polarity": "good"} for x in lexicon["good"]] +
                  [{**x, "polarity": "bad"} for x in lexicon["bad"]] +
                  [{**x, "polarity": "mid"} for x in lexicon["say"]])
    lexicon["cloud"] = sorted(cloud_pool, key=lambda x: -x["count"])[:40]

    for name, obj in [("needs_top5", needs), ("painpoints_top5", pains),
                      ("must_fix", must_fix), ("lexicon", lexicon)]:
        with open(DATA(name + ".json"), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        print(f"[done] data/{name}.json")

    print("\n===== 需求 TOP5 =====")
    for n, c in [(x["name"], x["count"]) for x in needs["items"]]:
        print(f"  {c:>4}  {n}")
    print("===== 痛点 TOP5 =====")
    for n, c in [(x["name"], x["count"]) for x in pains["items"]]:
        print(f"  {c:>4}  {n}")
    print("[next] python 03_lexicon 敏感词终筛 → 04 → 05 → 07")

if __name__ == "__main__":
    main()
