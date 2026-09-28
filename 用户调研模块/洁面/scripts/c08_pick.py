# -*- coding: utf-8 -*-
"""
c08_pick.py — 从洁面候选中剔除「纯教程/手法类」，挑高挖掘价值笔记待采集
输出: raw/xhs_picked.json
用法: python c08_pick.py [上限条数]
"""
import json, os, re, glob, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw")

# 纯教学/手法类 → 排除（对「为什么买」挖掘价值低）
TUTORIAL = re.compile(r"手法|教程|跟练|小课堂|正确使用方法|按摩|穴位|步骤|教学|示范|演示|"
                      r"正确洗脸|洗脸步骤|洗脸方式|怎么洗脸|洗脸教学")
# 高价值信号
HIGH = re.compile(r"避雷|避坑|别买|千万别|后悔|智商税|翻车|吐槽|踩雷|没用|无效|难用|差评|"
                  r"空瓶|用完|用了|感受|体验|实测|测评|对比|真实|亲测|回购|"
                  r"求推荐|哪个好|用哪个|怎么样|可以吗|推荐|平价|学生|"
                  r"过敏|紧绷|假滑|干涩|刺痛|泛红|爆痘|闷痘|闭口|黑头|清洁力|洗不干净|"
                  r"清洁力太强|香精|味道|难闻|油皮|干皮|敏感肌|痘肌|混油|混干")
BRANDS = ["芙丽芳丝", "freeplus", "Freeplus", "elta", "EltaMD", "珂润", "Curel", "薇诺娜",
          "至本", "逐本", "HFP", "hfp", "半亩花田", "谷雨", "优时颜", "珀莱雅", "薇姿",
          "理肤泉", "雅漾", "丝塔芙", "CeraVe", "适乐肤", "大宝", "旁氏", "妮维雅",
          "曼秀雷敦", "资生堂", "洗颜专科", "珊珂", "SENKA", "悦诗风吟", "innisfree",
          "FANCL", "芳珂", "DHC", "城野医生", "石泽研究所", "suisai", "嘉娜宝", "Kanebo",
          "诗留美屋", "牛乳石碱", "花印", "玉泽", "瑷尔博士", "可复美", "敷尔佳",
          "欧莱雅", "OLAY", "露得清", "Neutrogena", "可伶可俐", "相宜本草", "百雀羚",
          "自然堂", "韩束", "御泥坊", "一叶子", "膜法世家", "阿芙", "林清轩", "兰蔻",
          "SK-II", "黛珂", "雪肌精", "高丝", "KOSE", "溪木源", "肌肤未来", "RNW",
          "UNNY", "柳丝木", "摇滚动物园", "优斐斯", "博乐达", "三亩"]


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    cands = json.load(open(os.path.join(RAW, "xhs_candidates_clean.json"), encoding="utf-8"))["candidates"]
    done = set()
    for f in glob.glob(os.path.join(RAW, "xhs_output", "*.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
            done.add(d.get("nid", ""))
        except Exception:
            pass

    keep, drop = [], []
    for c in cands:
        t = c["title"]
        if c["nid"] in done:
            continue
        if TUTORIAL.search(t):
            drop.append((t, "教程/手法类"))
            continue
        score = 0
        if HIGH.search(t):
            score += 2
        bs = [b for b in BRANDS if b in t]
        if bs:
            score += 2
        if c.get("tag") in ("吐槽", "测评", "求安利"):
            score += 1
        keep.append({**c, "score": score, "brands": bs})
    keep.sort(key=lambda x: -x["score"])
    picked = [k for k in keep if k["score"] > 0][:limit]
    json.dump({"pickedAt": "2026-09-28", "count": len(picked), "items": picked},
              open(os.path.join(RAW, "xhs_picked.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"候选 {len(cands)} 条，已采 {len(done)} 条，剔教程 {len(drop)} 条，新选高价值 {len(picked)} 条", flush=True)
    print("=== 已剔除（教程/手法类）===", flush=True)
    for t, why in drop[:12]:
        print(f"  ✗ {t[:44]}", flush=True)
    print("\n=== 待采集（前 25）===", flush=True)
    for i, k in enumerate(picked[:25], 1):
        b = ("·" + ",".join(k["brands"])) if k["brands"] else ""
        print(f"{i:>2}. [分{k['score']}] {k['title'][:40]} {b}", flush=True)


if __name__ == "__main__":
    main()
