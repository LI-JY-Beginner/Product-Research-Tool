"""罗盘·商品榜采集器：翻页拉满 TOP200，含商品图与真实链接。

实测结论（2026-09-26）：
- page_size 服务端固定 10，total=200，需翻 20 页
- date_type 只支持预设 2/21/23，不支持自然日自定义
- product_info.image_url = 商品缩略图，product_detail_h5_url = 真实链接
"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from urllib.parse import quote
from collector.webbridge import Bridge
from collector import config


def _rank_url(category_id, begin, end, page_no, date_type, brand_type=-1):
    """brand_type: -1 全部（默认）/ 1 知名 / 2 非知名（策略台玩家结构用）。"""
    q = (
        "page_no=%d&page_size=%d&industry_id=%d&category_id=%s"
        "&brand_type=%d&price_bin=不限&rank_data_type=1"
        "&begin_date=%s&end_date=%s&date_type=%d"
        % (page_no, config.RANK_PAGE_SIZE, config.INDUSTRY_ID,
           quote(category_id, safe=","), brand_type, quote(begin), quote(end), date_type)
    )
    return config.COMPASS["product_rank"] + "?" + q


def _parse_row(x):
    pi = x.get("product_info", {})
    amt = x.get("new_pay_amt") or {}
    rng = amt.get("value_range") or []
    lower = rng[0].get("value") if len(rng) > 0 else None
    upper = rng[1].get("value") if len(rng) > 1 else None
    # 品牌：shop_list 第一个的 author_nick_name 近似（罗盘商品榜无独立 brand 字段）
    shops = pi.get("shop_list") or []
    brand = shops[0].get("author_info", {}).get("author_nick_name") if shops else None
    return {
        "product_id": pi.get("id"),
        "rank": pi.get("rank"),
        "rank_change": pi.get("rank_change"),
        "newly_on_ranking": pi.get("newly_on_ranking"),
        "name": pi.get("name"),
        "brand": brand,
        "price_bin": pi.get("price_bin"),
        "image_url": pi.get("image_url"),
        "detail_url": pi.get("product_detail_h5_url"),
        "category_id": pi.get("category_id"),
        "second_category_id": pi.get("second_category_id"),
        "third_category_id": pi.get("third_category_id"),
        "leaf_category_id": pi.get("leaf_category_id"),
        "brand_type": pi.get("brand_type"),  # 知名/非知名（策略台玩家结构用）
        "pay_lower": lower,
        "pay_upper": upper,
    }


def collect_category(bridge, category_id, begin, end, date_type=21, max_page=None, brand_type=-1):
    """翻页拉满一个类目的商品榜，返回去重后的全部商品行。brand_type 透传给接口。"""
    max_page = max_page or config.RANK_MAX_PAGE
    seen, rows, total = set(), [], None
    for page in range(1, max_page + 1):
        j = bridge.fetch_json(_rank_url(category_id, begin, end, page, date_type, brand_type))
        data = j.get("data") or {}
        if total is None:
            total = (data.get("page_result") or {}).get("total")
        batch = data.get("data_result") or []
        if not batch:
            break
        for x in batch:
            r = _parse_row(x)
            if r["product_id"] and r["product_id"] not in seen:
                seen.add(r["product_id"])
                rows.append(r)
        if total is not None and len(rows) >= total:
            break
        time.sleep(0.8)  # 串行限速，防风控
    return {"category_id": category_id, "total": total, "count": len(rows), "rows": rows}


def run(date_str, begin, end, date_type=21, session="compass-collect"):
    """采集本轮目标类目的全量商品榜，落原始快照。"""
    bridge = Bridge(session)
    st = bridge.status()
    if not st.get("extension_connected"):
        return {"ok": False, "error": "Kimi 扩展未连接"}

    bridge.navigate(config.COMPASS["base"] + "/shop/chance/rank-product",
                    new_tab=False, group_title="罗盘·商品榜采集")
    bridge.wait(8)

    out = {"date": date_str, "window": [begin, end], "date_type": date_type, "categories": []}
    for cate in config.TARGET_CATEGORIES:
        res = collect_category(bridge, cate["category_id"], begin, end, date_type)
        res["name"] = cate["name"]
        res["path"] = cate["path"]
        out["categories"].append(res)
        print("[product_rank] %s -> %d 条 (total=%s)" % (cate["name"], res["count"], res["total"]))

    os.makedirs(config.DATA_RAW, exist_ok=True)
    path = os.path.join(config.DATA_RAW, date_str.replace("/", "-"))
    os.makedirs(path, exist_ok=True)
    fp = os.path.join(path, "compass_product_rank.json")
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return {"ok": True, "file": fp, "categories": len(out["categories"])}


if __name__ == "__main__":
    import datetime
    # 罗盘近7天数据截止 T-1 或 T-2（当天未跑完），对齐到最近可用截止日
    today = datetime.date.today()
    end_date = today - datetime.timedelta(days=2)  # 数据截止日（罗盘当天数据未出）
    end = end_date.strftime("%Y/%m/%d")
    begin = (end_date - datetime.timedelta(days=6)).strftime("%Y/%m/%d")
    print(json.dumps(run(end, begin, end), ensure_ascii=False, indent=2))
