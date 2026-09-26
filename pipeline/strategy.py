"""策略台分析：CR4/CR10 / 玩家结构 / 价格带分布 / SKU矩阵 / GO·NOGO 规则引擎。

- CR4/CR10：类目商品榜前4/前10 支付金额区间中值占比
- 玩家结构：brand_type=1 知名 / 2 非知名(白牌)；知名品牌按国际品牌名单分国际大牌 vs 新锐
- 价格带分布：price_bin 直方图，标最卷价格带与空白带
- SKU矩阵：TOP5 品牌商品按价格带分引流款/利润款/复购款
- GO/NOGO：规则引擎按 config.STRATEGY_THRESHOLD 出初步结论
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collector import config
from pipeline import caliber, growth as growth_mod

# 常见国际品牌名单（Q1 已定口径；匹配到=国际大牌，其余知名=新锐）
INTL_BRAND_KEYWORDS = [
    "海蓝之谜", "LA MER", "兰蔻", "雅诗兰黛", "SK-II", "SKII", "资生堂", "欧莱雅",
    "科颜氏", "倩碧", "娇韵诗", "赫莲娜", "迪奥", "香奈儿", "CPB", "肌肤之钥",
    "娇兰", "希思黎", "莱珀妮", "馥蕾诗", "悦木之源", "黛珂", "雪花秀", "后",
    "兰芝", "伊索", "修丽可", "理肤泉", "雅漾", "薇姿", "碧欧泉", "欧舒丹",
]

# 价格带排序基准（解析 price_bin 文本中的数字，取下限做排序键）
def _price_bin_key(pb):
    if not pb:
        return 0
    import re
    m = re.search(r"¥?\s*([\d,]+(?:\.\d+)?)", pb.replace(",", ""))
    return float(m.group(1)) if m else 0


def is_intl_brand(brand_name):
    if not brand_name:
        return False
    b = brand_name.upper()
    return any(kw.upper() in b for kw in INTL_BRAND_KEYWORDS)


def _category_rows(category_name, date_str=None):
    """取某三级类目的商品榜行（按 rank 升序）。"""
    rows, date_str = growth_mod.latest_product_rows(date_str)
    rows = [r for r in rows if r.get("category_name") == category_name]
    rows.sort(key=lambda r: r.get("rank") or 9999)
    return rows, date_str


def concentration(rows):
    """CR4/CR10：前4/前10 金额中值占全榜中值和的比例。"""
    mids = [r["pay_mid"] for r in rows if r.get("pay_mid")]
    if not mids:
        return {"cr4": None, "cr10": None}
    total = sum(mids)
    cr4 = sum(mids[:4]) / total if total else None
    cr10 = sum(mids[:10]) / total if total else None
    return {"cr4": cr4, "cr10": cr10}


def player_structure(rows):
    """玩家结构：国际大牌 / 新锐 / 白牌 的商品数与金额中值占比。
    罗盘 brand_type 字段：1=知名 2=非知名。
    若全为 0（默认榜未区分），按国际品牌名单兜底：命中=国际大牌，其余=未区分（计白牌）。
    """
    groups = {"intl": {"cnt": 0, "pay": 0}, "new": {"cnt": 0, "pay": 0},
              "white": {"cnt": 0, "pay": 0}}
    bt_known = any(r.get("brand_type") in (1, 2) for r in rows)
    for r in rows:
        bt = r.get("brand_type")
        pay = r.get("pay_mid") or 0
        if bt == 1:
            g = "intl" if is_intl_brand(r.get("brand")) else "new"
        elif bt == 2:
            g = "white"
        else:
            # brand_type 未区分时的兜底：国际品牌名单命中按国际大牌估
            g = "intl" if is_intl_brand(r.get("brand")) else "white"
        groups[g]["cnt"] += 1
        groups[g]["pay"] += pay
    total_cnt = sum(g["cnt"] for g in groups.values()) or 1
    total_pay = sum(g["pay"] for g in groups.values()) or 1
    out = {k: {"cnt": v["cnt"], "cnt_ratio": v["cnt"] / total_cnt,
               "pay_ratio": v["pay"] / total_pay} for k, v in groups.items()}
    out["_caliber"] = "brand_type" if bt_known else "brand_name_fallback"
    return out


def price_band_hist(rows):
    """价格带直方图：price_bin → 商品数 + 金额中值和。
    标最卷价格带（商品数最多）与空白带（商品数 ≤3 但金额和不为 0）。
    """
    hist = {}
    for r in rows:
        pb = r.get("price_bin") or "未知"
        e = hist.setdefault(pb, {"cnt": 0, "pay": 0})
        e["cnt"] += 1
        e["pay"] += r.get("pay_mid") or 0
    bands = sorted(hist.items(), key=lambda kv: _price_bin_key(kv[0]))
    if not bands:
        return {"bands": [], "hottest": None, "gap": None}
    hottest = max(bands, key=lambda kv: kv[1]["cnt"])
    gaps = [(k, v) for k, v in bands if v["cnt"] <= 3 and v["pay"] > 0]
    gap = max(gaps, key=lambda kv: kv[1]["pay"]) if gaps else None
    return {
        "bands": [{"price_bin": k, "cnt": v["cnt"], "pay_mid_sum": v["pay"]} for k, v in bands],
        "hottest": {"price_bin": hottest[0], "cnt": hottest[1]["cnt"]},
        "gap": {"price_bin": gap[0], "cnt": gap[1]["cnt"], "pay_mid_sum": gap[1]["pay"]} if gap else None,
    }


def sku_matrix(rows, top_n=5):
    """TOP 玩家（按品牌金额中值和取前 N）的商品按价格带分：
    引流款（价格带最低 1/3）/ 利润款（最高 1/3）/ 复购款（名称含套装/组合/装）。
    """
    brand_pay = {}
    for r in rows:
        b = r.get("brand") or "未知"
        brand_pay[b] = brand_pay.get(b, 0) + (r.get("pay_mid") or 0)
    top_brands = sorted(brand_pay.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    matrix = []
    for brand, pay in top_brands:
        items = [r for r in rows if (r.get("brand") or "未知") == brand]
        items.sort(key=lambda r: _price_bin_key(r.get("price_bin")))
        entry = {"brand": brand, "pay_mid_sum": pay,
                 "引流款": None, "利润款": None, "复购款": None}
        # 复购款：名称含套装/组合/礼盒/双支/多支
        for r in items:
            name = r.get("name") or ""
            if any(k in name for k in ("套装", "组合", "礼盒", "双支", "多支", "两瓶装")):
                if entry["复购款"] is None:
                    entry["复购款"] = {"name": name, "price_bin": r.get("price_bin")}
        if items:
            lo = items[0]
            hi = items[-1]
            entry["引流款"] = {"name": lo.get("name"), "price_bin": lo.get("price_bin")}
            entry["利润款"] = {"name": hi.get("name"), "price_bin": hi.get("price_bin")}
        matrix.append(entry)
    return matrix


def rule_conclude(category_name, conc, players, price, market_size=None, mom=None):
    """GO/NOGO 规则引擎（阈值见 config.STRATEGY_THRESHOLD）。
    返回 {verdict, title, reasons[], segment, price_band}
    """
    th = config.STRATEGY_THRESHOLD
    cr4 = conc.get("cr4")
    reasons, score = [], 0

    if mom is not None:
        if mom > 0.2:
            score += 1
            reasons.append("类目环比 %s，市场有增量" % caliber.mom_str(mom))
        elif mom < -0.1:
            score -= 1
            reasons.append("类目环比 %s，大盘收缩" % caliber.mom_str(mom))
    if cr4 is not None:
        if cr4 > th["cr4_hard"]:
            score -= 2
            reasons.append("CR4=%.0f%% > %d%%，头部垄断难进入" % (cr4 * 100, th["cr4_hard"] * 100))
        elif cr4 < th["cr4_easy"]:
            score += 1
            reasons.append("CR4=%.0f%% < %d%%，竞争分散有机会" % (cr4 * 100, th["cr4_easy"] * 100))
        else:
            reasons.append("CR4=%.0f%%，集中度中等" % (cr4 * 100))
    white = players.get("white", {}).get("pay_ratio", 0)
    if white > 0.5:
        score += 1
        reasons.append("白牌金额占比 %.0f%%，品牌壁垒不强" % (white * 100))
    gap = (price or {}).get("gap")
    if gap:
        score += 1
        reasons.append("价格带 %s 竞品仅 %d 个但有成交，存在供给空白" % (gap["price_bin"], gap["cnt"]))

    verdict = "GO" if score >= 2 else ("NOGO" if score <= -1 else "观察")
    title = {"GO": "%s：竞争分散、有增量或供给空白，建议进入" % category_name,
             "NOGO": "%s：集中度高或大盘收缩，暂不建议进入" % category_name,
             "观察": "%s：信号混合，建议观察后再决策" % category_name}[verdict]
    return {
        "verdict": verdict,
        "title": title,
        "reasons": reasons,
        "segment": None,  # 细分方向由 LLM 结合成分数据给，规则引擎不编造
        "price_band": (gap or {}).get("price_bin") or (price.get("hottest") or {}).get("price_bin"),
        "score": score,
        "engine": "rule",
    }


def analyze_category(category_name, date_str=None):
    """策略台主入口：一个三级类目的完整四段分析。"""
    rows, date_str = _category_rows(category_name, date_str)
    if not rows:
        return None
    conc = concentration(rows)
    players = player_structure(rows)
    price = price_band_hist(rows)
    sku = sku_matrix(rows)
    # 类目级规模与增速（罗盘概览）
    mom_map = growth_mod.category_mom_map(date_str)
    mom = mom_map.get(category_name)
    overview_rows, _ = growth_mod.category_rows(date_str)
    size = None
    for r in overview_rows:
        if r.get("name") == category_name:
            pa = r.get("pay_amt") or {}
            size = {"lower": pa.get("lower"), "upper": pa.get("upper"),
                    "range_str": caliber.range_str(pa.get("lower"), pa.get("upper"))}
            break
    conclusion = rule_conclude(category_name, conc, players, price, size, mom)
    return {
        "category": category_name, "date": date_str, "sample_size": len(rows),
        "market_size": size, "mom": mom,
        "concentration": conc, "player_structure": players,
        "price_band": price, "sku_matrix": sku,
        "rule_conclusion": conclusion,
    }
