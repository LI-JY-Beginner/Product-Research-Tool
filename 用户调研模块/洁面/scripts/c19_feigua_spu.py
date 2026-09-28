# -*- coding: utf-8 -*-
"""
c19_feigua_spu.py — 飞瓜「商品库 / SPU库」采集洁面/洗面奶商品池

结论（对齐产品调研模块 g21/g22/g17 的探测）：
  · 正确路由是 #/spu-search/index（不是 goods-library，那个已 404）
  · 列表接口 /api/v3/spu/lib/list —— 明文 JSON，页面内 fetch 即可，无需解密
  · 商品搜索框 placeholder「请输入商品名、商品链接或抖音口令」
  · 类目筛选走 el-cascader（个护家清 / 面部护理 / 洁面）

用法:
  python c19_feigua_spu.py keywords      # 关键词逐个搜
  python c19_feigua_spu.py list          # 只拉个护家清全类目前 N 页
"""
import json, os, re, subprocess, sys, time
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.dirname(os.path.dirname(BASE))
TMP = os.path.join(WORKSPACE, "tmp")
os.makedirs(TMP, exist_ok=True)
RAW = os.path.join(BASE, "raw")
os.makedirs(RAW, exist_ok=True)
WB = "http://127.0.0.1:10086/command"
SESSION = "fg-cleanser"
REQ = os.path.join(TMP, "req_c19.json")
TODAY = datetime.now().strftime("%Y-%m-%d")

KEYWORDS = ["洗面奶", "洁面", "氨基酸洗面奶", "洗面奶 油皮", "洗面奶 敏感肌",
            "洗面奶 干皮", "男士洗面奶", "洁面慕斯", "洗面奶 控油", "洗面奶 祛痘"]

NOISE = ["沐浴", "洗发", "沐浴露", "洗发水", "卸妆", "洗手液", "洗洁精", "洗衣", "私处",
         "宠物", "狗狗", "猫", "洗碗", "内衣", "地毯", "身体乳", "磨砂膏", "牙膏", "漱口"]


def wb(action, args=None, wait=0, timeout=120):
    with open(REQ, "w", encoding="utf-8") as f:
        json.dump({"action": action, "args": args or {}, "session": SESSION}, f, ensure_ascii=False)
    try:
        r = subprocess.run(["curl.exe", "-s", "--noproxy", "*", "-X", "POST", WB,
                            "-H", "Content-Type: application/json", "--data-binary", "@" + REQ],
                           capture_output=True, text=True, encoding="utf-8", timeout=timeout)
        return json.loads(r.stdout)
    except Exception as e:
        return {"ok": False, "err": str(e)}
    finally:
        if wait:
            time.sleep(wait)


def ev(code, wait=0):
    r = wb("evaluate", {"code": code}, wait=wait)
    if not r.get("ok"):
        return None
    try:
        return json.loads(r["data"]["value"])
    except Exception:
        return r["data"].get("value")


# 页面内直接调接口（同源，自动带 cookie）
REPLAY = r"""
(async function(P){
  var qs = P.qs;
  var r = await fetch('/api/v3/spu/lib/list?' + qs, {method:'GET', headers:{'Accept':'application/json'}});
  var t = await r.text();
  var j = null; try{ j = JSON.parse(t); }catch(e){}
  if(!j) return JSON.stringify({status:r.status, code:-1, raw:t.slice(0,300)});
  var D = j.Data;
  var out = {status:r.status, code:j.Code, msg:j.Msg, dataType: (typeof D)};
  if (D && typeof D === 'object' && !Array.isArray(D)) {
    out.dataKeys = Object.keys(D);
    // 逐个 key 探：哪个是数组
    var arrKey = null, arrLen = 0;
    Object.keys(D).forEach(function(k){
      if (Array.isArray(D[k]) && D[k].length > arrLen) { arrKey = k; arrLen = D[k].length; }
    });
    out.arrKey = arrKey; out.arrLen = arrLen;
    out.total = D.Total || D.Count || D.TotalCount || 0;
    if (arrKey) {
      out.items = D[arrKey].slice(0, 100);
      out.itemKeys = D[arrKey].length ? Object.keys(D[arrKey][0]) : [];
    }
  } else if (Array.isArray(D)) {
    out.items = D.slice(0, 100);
    out.itemKeys = D.length ? Object.keys(D[0]) : [];
    out.total = D.length;
  } else {
    out.rawHead = String(D).slice(0, 400);
  }
  return JSON.stringify(out);
})(__P__)
"""


def spu_list(page=1, size=30, period=30, sort=1, keyword="", cate_id="", page_type=1):
    qs = "period=%d&sort=%d&searchType=1&page=%d&pageSize=%d&pageType=%d&_=%d" % (
        period, sort, page, size, page_type, int(time.time() * 1000))
    if keyword:
        qs += "&keyword=" + _q(keyword)
    if cate_id:
        qs += "&categoryId=" + str(cate_id)
    code = REPLAY.replace("__P__", json.dumps({"qs": qs}, ensure_ascii=False))
    r = ev(code, wait=1)
    try:
        return json.loads(r) if isinstance(r, str) else (r or {})
    except Exception:
        return {"status": -1, "n": 0, "items": [], "raw": str(r)[:300]}


def _q(s):
    import urllib.parse
    return urllib.parse.quote(str(s))


def open_spu():
    """进商品库页（spu-search），land 在可 fetch 的同源上下文"""
    wb("navigate", {"url": "https://dy.feigua.cn/app/#/workbench/index"}, wait=8)
    ev("location.hash='#/spu-search/index'")
    for i in range(15):
        t = ev("(document.body.innerText||'').length")
        if isinstance(t, int) and t > 1500:
            print(f"  商品库已渲染（len={t}）", flush=True)
            return True
        time.sleep(2)
    print("  ⚠️ 商品库页未渲染完成，仍继续", flush=True)
    return False


def probe_shape():
    """先探一条，看返回的真实结构"""
    open_spu()
    d = spu_list(page=1, size=3)
    print("\n=== 接口探测 ===", flush=True)
    print("status:", d.get("status"), "code:", d.get("code"), "msg:", repr(d.get("msg")), flush=True)
    print("dataType:", d.get("dataType"), "| dataKeys:", d.get("dataKeys"), flush=True)
    print("arrKey:", d.get("arrKey"), "arrLen:", d.get("arrLen"), "total:", d.get("total"), flush=True)
    print("itemKeys:", json.dumps(d.get("itemKeys"), ensure_ascii=False), flush=True)
    its = d.get("items") or []
    if its:
        print("样本:", json.dumps(its[0], ensure_ascii=False)[:1800], flush=True)
    else:
        print("raw:", json.dumps(d, ensure_ascii=False)[:800], flush=True)
    return d


if __name__ == "__main__":
    probe_shape()
