"""罗盘·类目挖掘采集器：三级/四级类目的成交增速 + 需求供给比。

实测结论（2026-09-26）：
- 接口 dig_cate_list 返回 module_data.core_data_0.compass_general_table_value（JSON 字符串需二次解析）
- cell_info.cate_info.category = {category_id, category_name, tags}
- cell_info.pay_amt_incr_rate = 成交增速（环比，unit=4 小数）
- cell_info.demand_supply_rate = 需求供给比（越大竞争越小）
- cell_info.pay_amt = 支付金额区间（lower/upper，分）
"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from urllib.parse import quote
from collector.webbridge import Bridge
from collector import config


def _url(first_cate_id, begin, end, date_type=21, page_no=1, page_size=20):
    q = (
        "date_type=%d&begin_date=%s&end_date=%s&cate_tag_list=&content_type=1"
        "&first_cate_id=%s&source_biz_type=1&page_size=%d&page_no=%d"
        "&is_asc=false&sort_field=pay_amt_incr_rate"
        % (date_type, quote(begin), quote(end), first_cate_id, page_size, page_no)
    )
    return config.COMPASS["category_mining_list"] + "?" + q


def _val(cell, key):
    """抽 cell_info.<key>.index_values.value.value（unit=4 小数 / unit=5 数量）。"""
    node = cell.get(key, {})
    iv = node.get("index_values", {})
    v = iv.get("value", {})
    return v.get("value")


def _range(cell, key):
    node = cell.get(key, {})
    iv = node.get("index_values", {})
    ex = iv.get("extra_value", {})
    lo = (ex.get("lower_range") or {}).get("value")
    hi = (ex.get("upper_range") or {}).get("value")
    return lo, hi


def _parse_row(x):
    ci = x.get("cell_info", {})
    cate = ci.get("cate_info", {}).get("category", {})
    lo, hi = _range(ci, "pay_amt")
    return {
        "cid": cate.get("category_id"),
        "name": cate.get("category_name"),
        "tags": [t.get("tag_name") for t in (cate.get("tags") or [])],
        "pay_amt_incr_rate": _val(ci, "pay_amt_incr_rate"),   # 成交增速（小数）
        "demand_supply_rate": _val(ci, "demand_supply_rate"),  # 需求供给比
        "pay_lower": lo, "pay_upper": hi,
        "top_pay_price_bin": (ci.get("top_pay_price_bin", {}).get("index_values", {}).get("value", {}) or {}).get("value"),
    }


def run(date_str, begin, end, date_type=21, first_cate_id="1000003462", session="compass-collect"):
    """采集二级类目下的潜力类目列表（三级/四级），翻页拉满。"""
    bridge = Bridge(session)
    st = bridge.status()
    if not st.get("extension_connected"):
        return {"ok": False, "error": "Kimi 扩展未连接"}

    bridge.navigate(config.COMPASS["base"] + "/shop/chance/category-mining",
                    new_tab=False, group_title="罗盘·类目挖掘采集")
    bridge.wait(6)

    seen, rows = set(), []
    for page in range(1, 6):
        j = bridge.fetch_json(_url(first_cate_id, begin, end, date_type, page))
        md = (j.get("data") or {}).get("module_data") or {}
        gtv = None
        for k, v in md.items():
            if isinstance(v, dict) and "compass_general_table_value" in v:
                gtv = v["compass_general_table_value"]
                break
        if not gtv:
            break
        inner = json.loads(gtv) if isinstance(gtv, str) else gtv
        batch = inner.get("data") or []
        if not batch:
            break
        for x in batch:
            r = _parse_row(x)
            if r["cid"] and r["cid"] not in seen:
                seen.add(r["cid"])
                rows.append(r)
        total = (inner.get("page_result") or {}).get("total", 0)
        if len(rows) >= total:
            break
        time.sleep(0.8)

    out = {"date": date_str, "window": [begin, end], "date_type": date_type,
           "first_cate_id": first_cate_id, "rows": rows}
    path = os.path.join(config.DATA_RAW, date_str.replace("/", "-"))
    os.makedirs(path, exist_ok=True)
    fp = os.path.join(path, "compass_category_mining.json")
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return {"ok": True, "file": fp, "rows": len(rows)}


if __name__ == "__main__":
    import datetime
    today = datetime.date.today()
    end_date = today - datetime.timedelta(days=2)
    end = end_date.strftime("%Y/%m/%d")
    begin = (end_date - datetime.timedelta(days=6)).strftime("%Y/%m/%d")
    print(json.dumps(run(end, begin, end), ensure_ascii=False, indent=2))
