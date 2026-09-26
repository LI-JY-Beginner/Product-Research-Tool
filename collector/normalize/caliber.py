# -*- coding: utf-8 -*-
"""口径统一：区间值 / 增速计算（沿用 PRD 3.2 口径，不可绕过）。"""

def growth_rate(current, previous):
    """增速 = 本期 ÷ 前段 − 1。前段为 0 或 None 时返回 None（低基数不算）。"""
    if previous is None or previous <= 0 or current is None:
        return None
    return current / previous - 1

def parse_range_mid(lower, upper):
    """区间值取中点（仅用于排序展示，不作精确口径）。
    罗盘金额单位是分（unit=3）。"""
    if lower is None and upper is None:
        return None
    if lower is None:
        return upper
    if upper is None:
        return lower
    return (lower + upper) / 2

def fmt_range(lower, upper, unit=3):
    """把区间值格式化为可读字符串（¥xx万-¥xx亿）。"""
    def f(v):
        if v is None:
            return "—"
        if unit == 3:
            yuan = v / 100.0
        else:
            yuan = float(v)
        if yuan >= 1e8:
            return "¥%.1f亿" % (yuan / 1e8)
        if yuan >= 1e4:
            return "¥%.0f万" % (yuan / 1e4)
        return "¥%.0f" % yuan
    if lower is None and upper is None:
        return "—"
    return "%s-%s" % (f(lower), f(upper))

def pct(x, digits=2):
    """小数转百分比字符串。"""
    if x is None:
        return "—"
    return ("%+." + str(digits) + "f%%") % (x * 100)
