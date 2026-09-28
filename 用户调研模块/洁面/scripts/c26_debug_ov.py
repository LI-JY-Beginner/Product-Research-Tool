# -*- coding: utf-8 -*-
"""c26_debug_ov.py — 打印某个商品详情页概览的原始文本段，核对指标解析是否错位"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import c23_feigua_profile as P

gid = sys.argv[1] if len(sys.argv) > 1 else None
gd = json.load(open(os.path.join(P.RAW, "feigua_gid_洁面_%s.json" % P.TODAY.replace("-", "")), encoding="utf-8"))
it = next((x for x in gd["goods"] if x["gid"] == gid), gd["goods"][1])
gid = it["gid"]
url = "https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=%s&tab=overview" % gid
if it.get("ts") and it.get("sign"):
    url += "&ts=%s&sign=%s" % (it["ts"], it["sign"])
print("open", url, flush=True)
P.wb("navigate", {"url": url, "newTab": True}, wait=9)
time.sleep(9)
P.ev(P.helper_js())
P.ev("window.__killMask()")
for _ in range(10):
    t = P.body_text()
    if "上架时间" in t or "近30天销量" in t:
        break
    time.sleep(2.5)
    P.ev("window.__killMask()")
t = P.body_text()
print("\n=========== 基础信息段 ===========")
print(P._seg(t, "更新时间", "分析同类商品热度")[:900])
print("\n=========== 商品数据段 ===========")
print(P._seg(t, "商品数据", "销售渠道")[:900])
print("\n=========== parse_overview 结果 ===========")
print(json.dumps(P.parse_overview(t), ensure_ascii=False, indent=1))
