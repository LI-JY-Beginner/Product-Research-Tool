"""视图模型组装：读 data/raw + pipeline 计算结果 → web/data/view.json。

结构：
{
  meta: {date, window, markets, currency},
  category_tree: config.CATEGORY_TREE + LEVEL1（带 has_data 标记）,
  boards: {
    growth:     增速产品看板（每类目 TOP3 增速 + 结论 hero 数据候选）
    trend:      类目增长趋势（三级类目行 + 环比 + 四级展开数据）
    ingredient: 成分榜（增速榜 + 热度榜 + 成分关联明细）
    product:    商品榜（全量明细，前端筛选用）
    strategy:   策略台（每类目四段分析 + 规则结论 + LLM 结论）
  }
}
"""
import os, sys, json, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collector import config
from pipeline import caliber, growth, ingredient, strategy, llm as llm_mod


def _product_view_rows(rows, growth_map):
    """商品行 → 前端视图行（含可读金额区间与环比字符串）。"""
    out = []
    for r in rows:
        mom = growth_map.get(r.get("product_id"))
        out.append({
            "product_id": r.get("product_id"),
            "rank": r.get("rank"),
            "name": r.get("name"),
            "brand": r.get("brand"),
            "price_bin": r.get("price_bin"),
            "image_url": r.get("image_url"),
            "detail_url": r.get("detail_url"),
            "leaf_category_id": r.get("leaf_category_id"),
            "leaf_category_name": (ingredient.LEAF_PATH.get(r.get("leaf_category_id")) or [None])[-1],
            "category_name": r.get("category_name"),
            "category_path": r.get("category_path"),
            "brand_type": r.get("brand_type"),
            "newly_on_ranking": r.get("newly_on_ranking"),
            "pay_range": caliber.range_str(r.get("pay_lower"), r.get("pay_upper")),
            "pay_mid": r.get("pay_mid"),
            "mom": mom,                       # None = 待积累
            "mom_str": caliber.mom_str(mom),  # None = 待积累
        })
    return out


def build(use_llm=True, date_str=None):
    # ---- 基础数据 ----
    rows, date_str = growth.latest_product_rows(date_str)
    if not rows:
        raise SystemExit("[build_view] 无商品榜快照，请先跑 collector.compass.product_rank")
    growth_map, cur_date, prev_date = growth.product_growth(date_str)
    print("[build_view] 商品榜快照 %s（基期 %s）" % (cur_date, prev_date or "无·待积累"))

    overview_rows, ov_date = growth.category_rows(date_str)
    mom_map = growth.category_mom_map(date_str)
    print("[build_view] 类目概览 %s，%d 个三级类目" % (ov_date, len(overview_rows)))

    ing_idx, _ = ingredient.build_ingredient_index(date_str)
    ing_growth, _, ing_prev = ingredient.ingredient_growth(date_str)
    heat, _ = ingredient.heat_scores(date_str)
    print("[build_view] 成分 %d 个（增速基期 %s）" % (len(ing_idx), ing_prev or "无"))

    product_rows = _product_view_rows(rows, growth_map)

    # ---- growth 看板：每类目 TOP3（按 rank，首日环比待积累时以榜序代替）----
    growth_board = {"hero": None, "groups": []}
    best = None
    for cate in config.TARGET_CATEGORIES:
        cname = cate["name"]
        crows = [r for r in product_rows if r["category_name"] == cname]
        # 有环比的按环比降序，无环比（待积累）按榜序
        with_mom = [r for r in crows if r["mom"] is not None]
        top3 = (sorted(with_mom, key=lambda r: r["mom"], reverse=True) or crows)[:3]
        growth_board["groups"].append({
            "category": cname, "path": cate["path"],
            "mom": mom_map.get(cname), "mom_str": caliber.mom_str(mom_map.get(cname)),
            "top3": top3, "total": len(crows),
        })
        cand = with_mom or crows
        if cand:
            c0 = max(cand, key=lambda r: r["mom"]) if with_mom else cand[0]
            if best is None or (c0["mom"] or 0) > (best["mom"] or -9):
                best = c0
    if best:
        growth_board["hero"] = {
            "name": best["name"], "brand": best["brand"],
            "gmv_mom_str": best["mom_str"] or "待积累",
            "country": "中国",
            "price_bin": best["price_bin"],
            "currency": "¥",
            "category": best["leaf_category_name"] or best["category_name"],
            "image_url": best["image_url"], "detail_url": best["detail_url"],
            "note": "首日无 7 天前快照，商品级环比待积累；hero 按榜单第 1 名展示" if prev_date is None else None,
        }

    # ---- trend 看板：三级类目全列（类目树）+ 四级（类目挖掘增速/供需比）----
    mrows, mdate = growth.mining_rows(date_str)
    mining_by_cid = {r["cid"]: r for r in mrows}
    print("[build_view] 类目挖掘 %s，%d 个类目" % (mdate, len(mrows)))

    def _leaf_nodes(l3_node):
        return l3_node.get("children") or []

    l2 = next(c for c in config.CATEGORY_TREE["children"] if c["name"] == "个人护理")
    trend_rows = []
    for l3 in l2.get("children", []):
        l3_has = l3.get("has_data", False)
        # 四级行：挂类目挖掘数据（有则实测，无则待采集）
        children = []
        for l4 in _leaf_nodes(l3):
            m = mining_by_cid.get(l4["cid"])
            children.append({
                "cid": l4["cid"], "name": l4["name"],
                "mom": (m or {}).get("pay_amt_incr_rate"),
                "mom_str": caliber.mom_str((m or {}).get("pay_amt_incr_rate")),
                "demand_supply_rate": (m or {}).get("demand_supply_rate"),
                "pay_range": caliber.range_str((m or {}).get("pay_lower"), (m or {}).get("pay_upper")),
                "has_data": m is not None,
            })
        children.sort(key=lambda x: (x["mom"] is None, -(x["mom"] or 0)))
        # 三级增速：有实测四级取最高；否则用概览（若有）
        moms = [c["mom"] for c in children if c["mom"] is not None]
        l3_mom = max(moms) if moms else None
        trend_rows.append({
            "name": l3["name"], "has_data": l3_has,
            "mom": l3_mom, "mom_str": caliber.mom_str(l3_mom),
            "children": children,
        })
    trend_rows.sort(key=lambda x: (x["mom"] is None, -(x["mom"] or 0)))
    fastest = next((r for r in trend_rows if r["mom"] is not None), None)
    # fastest 下增速最高的四级（顶部展示块更细粒度）
    fastest_leaf = None
    if fastest:
        leaves = [c for c in fastest["children"] if c["mom"] is not None]
        if leaves:
            fastest_leaf = max(leaves, key=lambda c: c["mom"])
    trend_board = {"rows": trend_rows, "fastest": fastest, "fastest_leaf": fastest_leaf}

    # ---- ingredient 看板 ----
    ing_list = []
    for ing, e in ing_idx.items():
        g = ing_growth.get(ing, {})
        h = heat.get(ing, {})
        prods = sorted(e["products"], key=lambda r: r.get("rank") or 9999)
        ing_list.append({
            "name": ing,
            "product_cnt": e["product_cnt"],
            "share": e["product_cnt"] / len(rows),
            "share_str": caliber.pct(e["product_cnt"] / len(rows)),
            "mom": g.get("mom"), "mom_str": caliber.mom_str(g.get("mom")),
            "new": g.get("new", False),
            "heat": h.get("heat"),
            "on_rank_freq": h.get("on_rank_freq"),
            "multi_category": h.get("multi_category", False),
            "level3": h.get("level3", []),
            "category_paths": h.get("category_paths", []),
            "products": [{
                "product_id": p.get("product_id"), "name": p.get("name"),
                "brand": p.get("brand"), "price_bin": p.get("price_bin"),
                "image_url": p.get("image_url"), "detail_url": p.get("detail_url"),
                "category_name": p.get("category_name"),
                "leaf_category_name": (ingredient.LEAF_PATH.get(p.get("leaf_category_id")) or [None])[-1],
            } for p in prods[:20]],
        })
    ing_list.sort(key=lambda x: (x["mom"] is None, -(x["mom"] or 0)))
    ingredient_board = {
        "by_growth": ing_list[:30],
        "by_heat": sorted(ing_list, key=lambda x: -(x["heat"] or 0))[:30],
        "all": ing_list,
    }

    # ---- strategy 看板：每个目标类目四段分析 ----
    strategy_board = {}
    for cate in config.TARGET_CATEGORIES:
        a = strategy.analyze_category(cate["name"], date_str)
        if not a:
            continue
        llm_res = llm_mod.llm_conclude(a) if use_llm else None
        if llm_res:
            a["llm_conclusion"] = llm_res
        else:
            a["llm_conclusion"] = None
        # 玩家结构补充可读百分比
        ps = a["player_structure"]
        for k in ("intl", "new", "white"):
            ps[k]["pay_ratio_str"] = caliber.pct(ps[k]["pay_ratio"])
            ps[k]["cnt_ratio_str"] = caliber.pct(ps[k]["cnt_ratio"])
        conc = a["concentration"]
        conc["cr4_str"] = caliber.pct(conc.get("cr4"))
        conc["cr10_str"] = caliber.pct(conc.get("cr10"))
        a["mom_str"] = caliber.mom_str(a.get("mom"))
        strategy_board[cate["name"]] = a
        print("[build_view] 策略台·%s：CR4=%s LLM=%s" % (
            cate["name"], conc["cr4_str"], "✓" if llm_res else "规则兜底"))

    # ---- 类目树（附 has_data）----
    def _mark(node):
        node = dict(node)
        node["has_data"] = node.get("has_data", False)
        if node.get("children"):
            node["children"] = [_mark(c) for c in node["children"]]
        return node
    cat_tree = _mark(config.CATEGORY_TREE)

    view = {
        "meta": {
            "date": cur_date, "growth_base": prev_date,
            "window": (growth.load_product_rank(cur_date) or {}).get("window"),
            "markets": ["全部", "中国", "美国(待接入)", "东南亚(待接入)"],
            "default_market": "全部",
            "periods": ["近7天", "近30天"],
            "active_period": "近7天",
        },
        "category_tree": cat_tree,
        "level1": config.LEVEL1,
        "boards": {
            "growth": growth_board,
            "trend": trend_board,
            "ingredient": ingredient_board,
            "product": {"rows": product_rows},
            "strategy": strategy_board,
        },
    }
    os.makedirs(config.WEB_DATA, exist_ok=True)
    fp = os.path.join(config.WEB_DATA, "view.json")
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(view, f, ensure_ascii=False, indent=1)
    print("[build_view] -> %s（%.1f KB）" % (fp, os.path.getsize(fp) / 1024))
    return fp


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true", help="不调 LLM（调试前端用）")
    ap.add_argument("--date", default=None, help="指定快照日期 YYYY-MM-DD")
    args = ap.parse_args()
    build(use_llm=not args.no_llm, date_str=args.date)
