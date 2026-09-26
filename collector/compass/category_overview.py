"""罗盘·类目概览采集器：子类目表 + 现成的类目级环比（out_period_ratio）。

实测结论：类目级环比增速在 cell_info.<指标>.<指标>_index_values.index_values.out_period_ratio，
unit=4 是小数（0.3776 = +37.76%），直接取，不用算。
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from urllib.parse import quote
from collector.webbridge import Bridge
from collector import config


def _url(category_id, begin, end, date_type=21, page_size=20):
    q = (
        "sort_field=cate_pay_amt&is_asc=false&page_no=1&page_size=%d"
        "&industry_id=%d&category_id=%s&price_band_type=1"
        "&begin_date=%s&end_date=%s&date_type=%d"
        % (page_size, config.INDUSTRY_ID, quote(category_id, safe=","),
           quote(begin), quote(end), date_type)
    )
    return config.COMPASS["category_overview"] + "?" + q


def _metric(cell_info, key):
    """从 cell_info 里抽一个指标的 区间 + 环比。"""
    node = cell_info.get(key, {}).get(key + "_index_values", {})
    iv = node.get("index_values", {})
    extra = iv.get("extra_value", {})
    ratio = iv.get("out_period_ratio", {})
    lower = (extra.get("lower_range") or {}).get("value")
    upper = (extra.get("upper_range") or {}).get("value")
    ratio_val = ratio.get("value") if ratio.get("unit") == 4 else None
    return {"lower": lower, "upper": upper, "mom": ratio_val}


def _parse_row(x):
    ci = x.get("cell_info", {})
    name_node = ci.get("price_band", {}).get("price_band_value", {}).get("value", {})
    return {
        "name": name_node.get("value_str"),
        "rank": ci.get("rank_no", {}).get("rank_no_value", {}).get("value", {}).get("value_str"),
        "pay_amt": _metric(ci, "cate_pay_amt"),          # 成交金额 + 环比
        "pay_amt_ratio": _metric(ci, "cate_pay_amt_ratio"),  # 占比
        "pay_cnt": _metric(ci, "cate_pay_cnt"),          # 成交件数
        "pay_product_cnt": _metric(ci, "cate_pay_product_cnt"),  # 关联商品数
    }


def run(date_str, begin, end, date_type=21, session="compass-collect"):
    """采集类目概览子类目表（含现成环比）。category_id 用 '二级,0' 表示看三级全部。"""
    bridge = Bridge(session)
    st = bridge.status()
    if not st.get("extension_connected"):
        return {"ok": False, "error": "Kimi 扩展未连接"}

    bridge.navigate(config.COMPASS["base"] + "/shop/chance/category-overview",
                    new_tab=False, group_title="罗盘·类目概览采集")
    bridge.wait(8)

    # 个人护理二级下所有三级类目（1000003462,0 = 个人护理/全部三级）
    j = bridge.fetch_json(_url("1000003462,0", begin, end, date_type))
    rows = [_parse_row(x) for x in (j.get("data") or [])]

    out = {"date": date_str, "window": [begin, end], "date_type": date_type,
           "parent": "个护家清/个人护理", "rows": rows}

    os.makedirs(config.DATA_RAW, exist_ok=True)
    path = os.path.join(config.DATA_RAW, date_str.replace("/", "-"))
    os.makedirs(path, exist_ok=True)
    fp = os.path.join(path, "compass_category_overview.json")
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return {"ok": True, "file": fp, "rows": len(rows)}


if __name__ == "__main__":
    import datetime
    # 罗盘近7天数据截止 T-2（当天与前一天数据未跑完），与 product_rank 对齐
    today = datetime.date.today()
    end_date = today - datetime.timedelta(days=2)
    end = end_date.strftime("%Y/%m/%d")
    begin = (end_date - datetime.timedelta(days=6)).strftime("%Y/%m/%d")
    print(json.dumps(run(end, begin, end), ensure_ascii=False, indent=2))
