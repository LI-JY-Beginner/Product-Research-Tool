"""成分提取 / 成分增速 / 热度分 / 成分关联。

- 成分提取：从商品标题解析成分词（内置词典）
- 成分增速：7天前 vs 今天的关联商品数变化 + 新上榜标记
- 热度分：关联商品数*0.4 + 销量加权*0.35 + 上榜频次*0.25（Q2 确认的初始权重）
- 成分关联：每个成分关联的商品列表 + 出现的类目层级（是否多类目）
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collector import config
from pipeline import growth as growth_mod

# 成分词典（起步，后续扩充）
INGREDIENT_DICT = [
    "烟酰胺", "玻色因", "角鲨烷", "胶原蛋白", "黑参提取物", "积雪草", "玻尿酸",
    "视黄醇", "维生素C", "果酸", "氨基酸", "侧柏叶", "何首乌", "山茶花",
    "角蛋白", "水杨酸", "神经酰胺", "泛醇", "甘草", "熊果苷",
]
# 长词优先（避免「胶原蛋白」被「蛋白」截断等情况，词典内按长度降序匹配）
INGREDIENT_DICT_SORTED = sorted(INGREDIENT_DICT, key=len, reverse=True)

# 四级类目 cid → 名称（从 config.CATEGORY_TREE 展开）
def _leaf_name_map():
    m = {}
    def walk(node, path):
        for ch in node.get("children", []) or []:
            p = path + [ch["name"]]
            m[ch["cid"]] = p
            walk(ch, p)
    walk(config.CATEGORY_TREE, [config.CATEGORY_TREE["name"]])
    return m

LEAF_PATH = _leaf_name_map()


def extract_ingredients(title):
    """从商品标题提取成分词列表（按词典匹配，去重保序）。"""
    if not title:
        return []
    found = []
    for w in INGREDIENT_DICT_SORTED:
        if w in title and w not in found:
            found.append(w)
    return found


def build_ingredient_index(date_str=None):
    """基于某日商品榜，构建成分索引：
    {ingredient: {products: [row...], category_paths: set, product_cnt, pay_mid_sum}}
    """
    rows, date_str = growth_mod.latest_product_rows(date_str)
    idx = {}
    for r in rows:
        ings = extract_ingredients(r.get("name"))
        leaf = r.get("leaf_category_id")
        path = LEAF_PATH.get(leaf)
        for ing in ings:
            e = idx.setdefault(ing, {"products": [], "category_paths": set(),
                                     "level3": set(), "pay_mid_sum": 0})
            e["products"].append(r)
            if path:
                e["category_paths"].add("/".join(path))
                if len(path) >= 3:
                    e["level3"].add(path[2])  # 三级类目名
            if r.get("pay_mid"):
                e["pay_mid_sum"] += r["pay_mid"]
    for e in idx.values():
        e["product_cnt"] = len(e["products"])
    return idx, date_str


def ingredient_growth(target_date=None, lookback_days=7):
    """成分增速：target vs 7天前快照的关联商品数变化 + 新上榜标记。
    返回 {ingredient: {"mom": float|None, "new": bool, "cur_cnt": int, "prev_cnt": int}}
    """
    import datetime
    days = growth_mod._snapshot_dates()
    if not days:
        return {}, None, None
    target_date = target_date or days[-1]
    t_dt = datetime.date.fromisoformat(target_date)
    prev_target = (t_dt - datetime.timedelta(days=lookback_days)).isoformat()
    prev_days = [d for d in days if d <= prev_target]
    prev_date = prev_days[-1] if prev_days else None

    cur_idx, _ = build_ingredient_index(target_date)
    prev_idx = build_ingredient_index(prev_date)[0] if prev_date else {}
    out = {}
    for ing, e in cur_idx.items():
        prev_cnt = prev_idx.get(ing, {}).get("product_cnt", 0) if prev_date else 0
        cur_cnt = e["product_cnt"]
        if not prev_date or prev_cnt == 0:
            out[ing] = {"mom": None, "new": prev_date is not None and prev_cnt == 0,
                        "cur_cnt": cur_cnt, "prev_cnt": prev_cnt}
        else:
            out[ing] = {"mom": (cur_cnt - prev_cnt) / prev_cnt, "new": False,
                        "cur_cnt": cur_cnt, "prev_cnt": prev_cnt}
    return out, target_date, prev_date


def heat_scores(date_str=None):
    """热度分 = 关联商品数*0.4 + 销量加权*0.35 + 上榜频次*0.25。
    - 关联商品数 / 销量加权（pay_mid_sum）：min-max 归一化到 0-100
    - 上榜频次：快照窗口内该成分出现的天数占比（首日只有 1 个快照时退化为 1.0）
    """
    idx, date_str = build_ingredient_index(date_str)
    if not idx:
        return {}, date_str
    w = config.HEAT_WEIGHT
    max_cnt = max(e["product_cnt"] for e in idx.values()) or 1
    max_pay = max(e["pay_mid_sum"] for e in idx.values()) or 1

    # 上榜频次：统计窗口内每日快照中成分出现情况
    days = growth_mod._snapshot_dates()
    freq = {ing: 0 for ing in idx}
    if len(days) > 1:
        for d in days:
            day_idx, _ = build_ingredient_index(d)
            for ing in freq:
                if ing in day_idx:
                    freq[ing] += 1
        denom = len(days)
    else:
        for ing in freq:
            freq[ing] = 1
        denom = 1

    scores = {}
    for ing, e in idx.items():
        s_cnt = e["product_cnt"] / max_cnt * 100
        s_pay = e["pay_mid_sum"] / max_pay * 100
        s_freq = freq[ing] / denom * 100
        scores[ing] = {
            "heat": round(s_cnt * w["product_cnt"] + s_pay * w["volume"] + s_freq * w["on_rank_freq"], 1),
            "product_cnt": e["product_cnt"],
            "pay_mid_sum": e["pay_mid_sum"],
            "on_rank_freq": "%d/%d" % (freq[ing], denom),
            "multi_category": len(e["level3"]) > 1,
            "category_paths": sorted(e["category_paths"]),
            "level3": sorted(e["level3"]),
        }
    return scores, date_str
