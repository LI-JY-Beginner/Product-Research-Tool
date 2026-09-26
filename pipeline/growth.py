"""增速计算：
- 类目级环比：直接取罗盘 category_overview 的 out_period_ratio（现成字段）
- 商品级增速：读 data/raw/ 近 90 天快照，本期近7天 vs 7天前同商品金额中值环比；
  首日无快照标「待积累」（返回 None）
"""
import os, sys, json, datetime, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collector import config
from pipeline import caliber


# ---------- 类目级 ----------

def load_category_overview(date_str=None):
    """读某日的类目概览原始数据。date_str=None 时取最新。"""
    if date_str is None:
        days = sorted(glob.glob(os.path.join(config.DATA_RAW, "*")), reverse=True)
        for d in days:
            fp = os.path.join(d, "compass_category_overview.json")
            if os.path.exists(fp):
                date_str = os.path.basename(d)
                break
        else:
            return None
    fp = os.path.join(config.DATA_RAW, date_str, "compass_category_overview.json")
    if not os.path.exists(fp):
        return None
    with open(fp, encoding="utf-8") as f:
        return json.load(f)


def category_mom_map(date_str=None):
    """三级类目名 → 环比小数（罗盘现成 out_period_ratio）。"""
    raw = load_category_overview(date_str)
    if not raw:
        return {}
    out = {}
    for r in raw.get("rows", []):
        name = r.get("name")
        mom = (r.get("pay_amt") or {}).get("mom")
        if name and mom is not None:
            out[name] = mom
    return out


def category_rows(date_str=None):
    """类目概览全量行（name/rank/pay_amt{lower,upper,mom}/pay_amt_ratio/pay_product_cnt）。"""
    raw = load_category_overview(date_str)
    return (raw or {}).get("rows", []), (raw or {}).get("date")


def load_category_mining(date_str=None):
    """读类目挖掘原始数据（三级/四级类目的增速+供需比）。"""
    if date_str is None:
        days = sorted(glob.glob(os.path.join(config.DATA_RAW, "*")), reverse=True)
        for d in days:
            fp = os.path.join(d, "compass_category_mining.json")
            if os.path.exists(fp):
                date_str = os.path.basename(d)
                break
        else:
            return None
    fp = os.path.join(config.DATA_RAW, date_str, "compass_category_mining.json")
    if not os.path.exists(fp):
        return None
    with open(fp, encoding="utf-8") as f:
        return json.load(f)


def mining_rows(date_str=None):
    """类目挖掘行列表：{cid,name,tags,pay_amt_incr_rate,demand_supply_rate,...}"""
    raw = load_category_mining(date_str)
    return (raw or {}).get("rows", []), (raw or {}).get("date")


# ---------- 商品级快照环比 ----------

def _snapshot_dates():
    """所有有商品榜快照且非空的日期，升序。"""
    days = []
    for d in glob.glob(os.path.join(config.DATA_RAW, "*")):
        fp = os.path.join(d, "compass_product_rank.json")
        if os.path.exists(fp):
            try:
                with open(fp, encoding="utf-8") as f:
                    j = json.load(f)
                if sum(len(c.get("rows", [])) for c in j.get("categories", [])) > 0:
                    days.append(os.path.basename(d))
            except Exception:
                pass
    return sorted(days)


def load_product_rank(date_str):
    fp = os.path.join(config.DATA_RAW, date_str, "compass_product_rank.json")
    if not os.path.exists(fp):
        return None
    with open(fp, encoding="utf-8") as f:
        return json.load(f)


def _product_mid_map(date_str):
    """某快照：product_id → (金额中值[分], row)。"""
    raw = load_product_rank(date_str)
    if not raw:
        return {}
    m = {}
    for cate in raw.get("categories", []):
        for r in cate.get("rows", []):
            mid = caliber.range_mid(r.get("pay_lower"), r.get("pay_upper"))
            if r.get("product_id"):
                m[r["product_id"]] = (mid, r, cate["name"])
    return m


def product_growth(target_date=None, lookback_days=7):
    """商品级环比：target_date 快照 vs 7 天前最接近的快照。
    返回 {product_id: mom_decimal or None}。首日无快照 → 全部 None（待积累）。
    """
    days = _snapshot_dates()
    if not days:
        return {}, None, None
    target_date = target_date or days[-1]
    if target_date not in days:
        return {}, None, None
    t_dt = datetime.date.fromisoformat(target_date)
    prev_target = (t_dt - datetime.timedelta(days=lookback_days)).isoformat()
    # 找 ≤ prev_target 的最近快照
    prev_days = [d for d in days if d <= prev_target]
    prev_date = prev_days[-1] if prev_days else None
    cur = _product_mid_map(target_date)
    if prev_date is None:
        return {pid: None for pid in cur}, target_date, None
    prev = _product_mid_map(prev_date)
    out = {}
    for pid, (mid, _r, _c) in cur.items():
        pm = prev.get(pid)
        if pm is None or pm[0] in (None, 0) or mid is None:
            out[pid] = None  # 新上榜或无基期 → 待积累
        else:
            out[pid] = (mid - pm[0]) / pm[0]
    return out, target_date, prev_date


def latest_product_rows(date_str=None):
    """最新商品榜全量行（拍平 categories），每行附加 category_name 与金额中值。"""
    days = _snapshot_dates()
    if not days:
        return [], None
    date_str = date_str or days[-1]
    raw = load_product_rank(date_str)
    rows = []
    for cate in raw.get("categories", []):
        for r in cate.get("rows", []):
            r = dict(r)
            r["category_name"] = cate["name"]
            r["category_path"] = cate.get("path")
            r["pay_mid"] = caliber.range_mid(r.get("pay_lower"), r.get("pay_upper"))
            rows.append(r)
    return rows, date_str
