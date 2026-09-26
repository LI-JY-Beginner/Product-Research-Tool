# -*- coding: utf-8 -*-
"""罗盘·增速产品榜采集任务（每日）。
抓面部洗护/眼部护理两个类目的商品榜，取两段不重叠 7 天窗口算环比增速。
只负责「原样抓下来」，增速计算在 normalize。"""
import json, os, sys, time
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from webbridge import Bridge
import config
from normalize.caliber import growth_rate, fmt_range, pct

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)


def _rank_url(category_id, begin, end, date_type=21):
    """罗盘商品榜接口（market_hot_sale）。
    ⚠️ 实测：该接口不支持 date_type=7 自然日自定义（返回 total=0），
    只支持预设值（2=近1天 / 21=近7天 / 23=近30天）。
    因此增速看板用「每日抓近7天(date_type=21)存快照」，环比对 7 天前的快照。"""
    q = (
        "page_no=1&page_size=10&industry_id=%d&category_id=%s"
        "&brand_type=-1&price_bin=不限&rank_data_type=1"
        "&begin_date=%s&end_date=%s&date_type=%d"
        % (config.INDUSTRY_ID, quote(category_id, safe=","),
           quote(begin), quote(end), date_type)
    )
    return config.COMPASS["product_rank"] + "?" + q


def _parse_rows(payload):
    """从 market_hot_sale 响应里抽商品行。"""
    rows = []
    for item in (payload.get("data", {}) or {}).get("data_result", []) or []:
        info = item.get("product_info", {}) or {}
        pay = (item.get("new_pay_amt") or {}).get("value_range") or []
        lower = pay[0].get("value") if len(pay) > 0 else None
        upper = pay[1].get("value") if len(pay) > 1 else None
        rows.append({
            "rank": info.get("rank"),
            "name": info.get("name"),
            "brand": (info.get("brand_type") is not None and "—") or "—",
            "price_bin": info.get("price_bin"),
            "leaf_category_id": info.get("leaf_category_id"),
            "pay_lower": lower,
            "pay_upper": upper,
        })
    return rows


def run(end_date="2026/09/24", session="compass-collect", compare_snapshot=None):
    """主入口：抓两个类目的「近7天」商品榜（date_type=21）存今日快照。
    compare_snapshot：若提供 7 天前的快照文件路径，则算环比增速；否则只存快照。"""
    br = Bridge(session)
    st = br.status()
    if not st.get("extension_connected"):
        return {"ok": False, "error": "Kimi 扩展未连接，请打开装了扩展的 Chrome 后重试"}

    (b1, e1), _ = config.growth_windows(end_date)
    result = {"date": end_date, "window": [b1, e1], "date_type": 21, "categories": []}

    # 先导航到罗盘页面（同源 cookie 才生效），再 fetch 接口
    br.navigate("https://compass.jinritemai.com/shop/chance/rank-product", new_tab=False, group_title="罗盘·增速采集")
    br.wait(8)

    for cate in config.TARGET_CATEGORIES:
        cid = cate["category_id"]
        cur = br.fetch_json(_rank_url(cid, b1, e1, date_type=21))
        br.wait(1.5)
        cur_rows = _parse_rows(cur)
        result["categories"].append({
            "path": cate["path"],
            "category_id": cid,
            "rows": cur_rows,
            "count": len(cur_rows),
        })

    # 若提供 7 天前快照，算环比
    if compare_snapshot and os.path.exists(compare_snapshot):
        prev = json.load(open(compare_snapshot, encoding="utf-8"))
        prev_map = {}
        for c in prev.get("categories", []):
            for r in c.get("rows", []):
                prev_map[(c["category_id"], r["name"])] = r
        for c in result["categories"]:
            out_rows = []
            for r in c["rows"]:
                p = prev_map.get((c["category_id"], r["name"]))
                cur_mid = (r["pay_lower"] + r["pay_upper"]) / 2 if r["pay_lower"] and r["pay_upper"] else None
                prev_mid = (p["pay_lower"] + p["pay_upper"]) / 2 if p and p["pay_lower"] and p["pay_upper"] else None
                rate = growth_rate(cur_mid, prev_mid)
                out_rows.append({
                    "rank": r["rank"], "name": r["name"], "price_bin": r["price_bin"],
                    "pay_range": fmt_range(r["pay_lower"], r["pay_upper"]),
                    "growth": rate, "growth_str": pct(rate),
                    "leaf_category_id": r["leaf_category_id"],
                })
            out_rows.sort(key=lambda x: (x["growth"] is None, -(x["growth"] or 0)))
            c["top_with_growth"] = out_rows[:3]

    path = os.path.join(DATA_DIR, "growth_%s.json" % end_date.replace("/", "-"))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return {"ok": True, "file": path, "categories": len(result["categories"]), "with_growth": bool(compare_snapshot)}


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else "2026/09/24"
    print(json.dumps(run(d), ensure_ascii=False, indent=2))
