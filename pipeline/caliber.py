"""口径工具：罗盘区间值 → 可读字符串 / 中值；占比 / 环比 / 货币符号。

罗盘金额单位是「分」，区间 {lower, upper}（None 表示开放端）。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------- 金额区间 ----------

def _fen_to_yi(fen):
    """分 → 亿元（float）"""
    return fen / 1e8 / 100 if fen is not None else None


def fmt_yi(fen):
    """分 → 可读字符串：≥1亿 用「亿」，否则用「万」。"""
    if fen is None:
        return None
    yuan = fen / 100.0
    if yuan >= 1e8:
        v = yuan / 1e8
        return ("¥%g亿" % round(v, 2))
    if yuan >= 1e4:
        v = yuan / 1e4
        return ("¥%g万" % round(v, 1)).replace(".0万", "万")
    return "¥%g" % round(yuan)


def range_str(lower, upper, currency="¥"):
    """罗盘区间值（分）→ 可读字符串。如 ¥10亿-¥25亿 / ¥99-¥149 / ¥399。
    lower/upper 为 None 表示开放端。
    """
    if lower is None and upper is None:
        return None
    if lower == upper and lower is not None:
        return fmt_yi(lower)
    lo = fmt_yi(lower) if lower is not None else "0"
    hi = fmt_yi(upper) if upper is not None else "∞"
    if currency != "¥":
        lo, hi = lo.replace("¥", currency), hi.replace("¥", currency)
    return "%s-%s" % (lo, hi)


def range_mid(lower, upper):
    """区间中值（分）。开放端用另一端近似。"""
    if lower is None and upper is None:
        return None
    if lower is None:
        return upper
    if upper is None:
        return lower
    return (lower + upper) / 2.0


# ---------- 占比 / 环比 ----------

def pct(frac, digits=1):
    """占比小数 → 百分比字符串。0.3776 → '37.8%'"""
    if frac is None:
        return None
    return ("%.*f%%" % (digits, frac * 100))


def mom_str(frac, digits=2):
    """环比小数 → '+37.8%' / '-5.2%' 字符串。"""
    if frac is None:
        return None
    sign = "+" if frac >= 0 else ""
    return "%s%.*f%%" % (sign, digits, frac * 100)


# ---------- 货币符号 ----------

def currency_symbol(market):
    """市场 → 货币符号。国内 ¥，海外 $。"""
    return "$" if market and market not in ("中国", "全部") else "¥"
