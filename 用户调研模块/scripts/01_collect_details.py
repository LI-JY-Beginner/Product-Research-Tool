# -*- coding: utf-8 -*-
"""
01_collect_details.py — 批量采集飞瓜商品详情页（受众画像 + 商品评价/词云）
通过 Kimi WebBridge 驱动用户已登录的浏览器，逐个打开商品详情页取数
输出: raw/feigua_detail_<gid>.json
"""
import json, os, re, subprocess, time, sys
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 自动定位：.../用户调研模块
WORKSPACE = os.path.dirname(BASE)
TMP = os.path.join(WORKSPACE, "tmp")
os.makedirs(TMP, exist_ok=True)
RAW = os.path.join(BASE, "raw")
WB = "http://127.0.0.1:10086/command"
SESSION = "feigua-user-research"
TODAY = datetime.now().strftime("%Y-%m-%d")

# TOP10 玩家代表 SPU（gid -> 完整 href）
TARGETS = {
    "3Z649OBD1oFEBM7YnOjwcJ410p8vmBFjA": "https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=3Z649OBD1oFEBM7YnOjwcJ410p8vmBFjA&tab=overview&ts=1790244793&sign=10d4613389633a583b0a8f82309b91fd",
    "3Z6vd1E3wqFEBVA1oApxtJ9j630mpXHjZ": "https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=3Z6vd1E3wqFEBVA1oApxtJ9j630mpXHjZ&tab=overview&ts=1790244793&sign=17502c01b8dc8199e20cd495458504d8",
    "BZkMxyX1vrSpvERLVmxnH6rleZv4Kdf68": "https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=BZkMxyX1vrSpvERLVmxnH6rleZv4Kdf68&tab=overview&ts=1790244793&sign=b4f8fc87866631294bdf55008a1e4b81",
    "VDkQ7ZQrKnHej2DrlYkkcGXGpAyXxmTZm": "https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=VDkQ7ZQrKnHej2DrlYkkcGXGpAyXxmTZm&tab=overview&ts=1790244604&sign=b2dc73a9dc169ba3c44ed516d19e38fe",
    "9ZB2e8QR7ls3kzD0gXe8FApVyWpyKRIpn": "https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=9ZB2e8QR7ls3kzD0gXe8FApVyWpyKRIpn&tab=overview&ts=1790244793&sign=7654e426e2e1bee905da025588d78ef5",
    "vzA9mr5qLgTmWm6vOY1wu5RndzOxDjsgJ": "https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=vzA9mr5qLgTmWm6vOY1wu5RndzOxDjsgJ&tab=overview&ts=1790244604&sign=159591adad6959544b393cb53ff517ed",
    "RKroG1lXyAil3zW3ZOdxIEg2QvXz6XS7p": "https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=RKroG1lXyAil3zW3ZOdxIEg2QvXz6XS7p&tab=overview&ts=1790244793&sign=9c058b9c78eb598713ecb029fd95362e",
    "BZkm65p5qwsorkpQoxwosqvWR6QOZMc6n": "https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=BZkm65p5qwsorkpQoxwosqvWR6QOZMc6n&tab=overview&ts=1790244604&sign=ca9fb4643959ab28001cc17c867241a3",
    "JZkLQqK13qhYEy4np99DTx7jZ5xygAFrm": "https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=JZkLQqK13qhYEy4np99DTx7jZ5xygAFrm&tab=overview&ts=1790244604&sign=cb5308a69141d20ada8b8a5a7cda925d",
    "EMKO7QdnjZTB4OYeldnVi4LnrxgDDdFW2": "https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=EMKO7QdnjZTB4OYeldnVi4LnrxgDDdFW2&tab=overview&ts=1790244604&sign=611b2b727a8297ee991fbf2ed0bbfa93",
    "0Z0WeLp1dLfeMQ5v6o31FnpxoGKpjBiLw": "https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=0Z0WeLp1dLfeMQ5v6o31FnpxoGKpjBiLw&tab=overview&ts=1790244793&sign=02e90043da435cac147c836417bfd9a7",
}

_n = [0]
def wb(action, args, wait=0):
    _n[0] += 1
    fp = os.path.join(TMP, f"wbq-{os.getpid()}-{_n[0]}.json")
    with open(fp, "w", encoding="utf-8") as f:
        json.dump({"action": action, "args": args, "session": SESSION}, f, ensure_ascii=False)
    try:
        r = subprocess.run(["curl.exe", "-s", "-X", "POST", WB, "-H", "Content-Type: application/json",
                            "--data-binary", "@" + fp], capture_output=True, text=True, encoding="utf-8", timeout=60)
        out = json.loads(r.stdout)
    except Exception as e:
        return {"ok": False, "err": str(e)}
    finally:
        try: os.remove(fp)
        except Exception: pass
    if wait: time.sleep(wait)
    return out

def click_tab(name):
    code = ("(() => { var els=[...document.querySelectorAll('div,span,a,li,button')]"
            ".filter(function(e){ var t=(e.innerText||'').trim(); return t==='" + name + "' && e.children.length<=2; });"
            "if(els.length){ els[els.length-1].click(); return 'ok'; } return 'nf'; })()")
    return wb("evaluate", {"code": code})

def get_text():
    r = wb("evaluate", {"code": "document.body.innerText"})
    if not r.get("ok"): return ""
    try: return json.loads(r["data"]["value"])
    except Exception: return r["data"].get("value", "")

def parse_pct(s):
    try: return float(str(s).replace("%", "").strip())
    except Exception: return 0.0

def parse_reviews(txt):
    """解析商品评价 tab：情感统计 + 词云 + 评价列表"""
    out = {"sentiment": {}, "wordcloud": [], "reviews": []}
    m = re.search(r"全部\(([^)]+)\)\s*好评\(([^)]+)\)\s*中评\(([^)]+)\)\s*差评\(([^)]+)\)", txt)
    if m:
        out["sentiment"] = {"全部": m.group(1), "好评": m.group(2), "中评": m.group(3), "差评": m.group(4)}
    # 词云表：序号 词 评价数 占比
    seg = txt.split("评价词")
    if len(seg) > 1:
        body = seg[1][:6000]
        for mm in re.finditer(r"(\d+)\s*\n\s*([^\n\d%]{1,12})\s*\n\s*([\d.]+)\s*\n\s*([\d.]+)%", body):
            out["wordcloud"].append({"word": mm.group(2).strip(), "count": mm.group(3), "pct": float(mm.group(4))})
            if len(out["wordcloud"]) >= 60: break
    # 评价列表：内容 + 时间
    seg2 = txt.split("评价时间")
    if len(seg2) > 1:
        body = seg2[1]
        for mm in re.finditer(r"([^\n]{8,200}?)\s*\n\s*(\d{4}-\d{2}-\d{2})\s*\n\s*(\d{2}:\d{2}:\d{2})", body):
            out["reviews"].append({"content": mm.group(1).strip(), "date": mm.group(2), "time": mm.group(3)})
            if len(out["reviews"]) >= 25: break
    return out

def parse_audience(txt):
    """解析受众画像 tab"""
    out = {"summary": "", "gender": [], "region": [], "prefer": ""}
    m = re.search(r"基础画像[：:]\s*([^\n]+)", txt)
    if m: out["summary"] = m.group(1).strip()
    m2 = re.search(r"内容偏好[：:]\s*([^\n]+)", txt)
    if m2: out["prefer"] = m2.group(1).strip()
    g = re.search(r"性别分布([\s\S]{0,300})", txt)
    if g:
        for mm in re.finditer(r"(男性|女性)\s*([\d.]+)%\s*\n?\s*TGI\s*([\d.]+)", g.group(1)):
            out["gender"].append({"gender": mm.group(1), "pct": float(mm.group(2)), "tgi": float(mm.group(3))})
    r = re.search(r"地域分布[\s\S]{0,80}?(省份|城市)[\s\S]{0,300}", txt)
    if r:
        for mm in re.finditer(r"([一-龥]{2,4})\s*\n\s*([\d.]+)%", r.group(0)):
            out["region"].append({"region": mm.group(1), "pct": float(mm.group(2))})
            if len(out["region"]) >= 12: break
    return out

def collect(gid, url):
    wb("navigate", {"url": url}, wait=7)
    # 基础信息（概览页）
    base_txt = get_text()
    info = {}
    m = re.search(r"品牌\s*\n\s*([^\n]+)", base_txt)
    if m: info["brand"] = m.group(1).strip()
    m = re.search(r"小店\s*\n\s*([^\n]+)", base_txt)
    if m: info["shop"] = m.group(1).strip()
    m = re.search(r"分类\s*\n\s*([^\n]+)", base_txt)
    if m: info["category3"] = m.group(1).strip()
    m = re.search(r"共([\d.]+w?)条评价好评([\d.]+)%", base_txt)
    if m: info["reviewCount"], info["goodRate"] = m.group(1), float(m.group(2))
    m = re.search(r"近30天销量[：:]\s*\n?\s*([^\n]+)", base_txt)
    if m: info["sales30d"] = m.group(1).strip()
    m = re.search(r"商品销售榜/([^/]+)/月榜第(\d+)名", base_txt)
    if m: info["rank"] = {"cat": m.group(1), "monthRank": int(m.group(2))}
    m = re.search(r"^(【[^\n]+】[^\n]+|[^\n]{10,80})\n复制标题", base_txt, re.M)
    if m: info["title"] = m.group(1).strip()
    # 评价
    click_tab("商品评价"); time.sleep(5)
    rev = parse_reviews(get_text())
    # 差评专项
    click_tab("差评"); time.sleep(4)
    neg = parse_reviews(get_text())
    # 受众画像
    click_tab("受众画像"); time.sleep(5)
    aud = parse_audience(get_text())
    return {"gid": gid, "fetchDate": TODAY, "info": info,
            "audience": aud, "reviews": rev, "negativeReviews": neg["reviews"]}

def main():
    os.makedirs(RAW, exist_ok=True)
    results = {}
    for i, (gid, url) in enumerate(TARGETS.items(), 1):
        print(f"[{i}/{len(TARGETS)}] 采集 {gid[:12]}...", flush=True)
        try:
            d = collect(gid, url)
            results[gid] = d
            with open(os.path.join(RAW, f"feigua_detail_{gid[:12]}.json"), "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=1)
            print(f"    ✓ 品牌={d['info'].get('brand','?')} 类目={d['info'].get('category3','?')} "
                  f"词云={len(d['reviews']['wordcloud'])} 评价={len(d['reviews']['reviews'])} 差评={len(d['negativeReviews'])}")
        except Exception as e:
            print(f"    ✗ {e}")
    with open(os.path.join(RAW, "feigua_details_all.json"), "w", encoding="utf-8") as f:
        json.dump({"fetchedAt": TODAY, "count": len(results), "details": results}, f, ensure_ascii=False, indent=1)
    print(f"\n[done] 采集 {len(results)} 个商品 → raw/feigua_details_all.json")

if __name__ == "__main__":
    main()
