# -*- coding: utf-8 -*-
"""
01b_collect_details.py — 修复版（v2）
修复：①临时文件复用避免触发安全删除 ②差评tab点击（按钮文本带数量）③词云解析 ④类目精确匹配 ⑤原始文本落盘
"""
import json, os, re, subprocess, time
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 自动定位：.../用户调研模块
WORKSPACE = os.path.dirname(BASE)
TMP = os.path.join(WORKSPACE, "tmp")
os.makedirs(TMP, exist_ok=True)
RAW = os.path.join(BASE, "raw")
WB = "http://127.0.0.1:10086/command"
SESSION = "feigua-user-research"
REQ_FILE = os.path.join(TMP, "wbq_current.json")   # 复用同一文件，不再频繁创建/删除
TODAY = datetime.now().strftime("%Y-%m-%d")

# 剩余未采集 + 需要重采的（词云/差评失败）
TARGETS = {
    "RKroG1lXyAil3zW3ZOdxIEg2QvXz6XS7p": "https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=RKroG1lXyAil3zW3ZOdxIEg2QvXz6XS7p&tab=overview&ts=1790244793&sign=9c058b9c78eb598713ecb029fd95362e",
    "BZkm65p5qwsorkpQoxwosqvWR6QOZMc6n": "https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=BZkm65p5qwsorkpQoxwosqvWR6QOZMc6n&tab=overview&ts=1790244604&sign=ca9fb4643959ab28001cc17c867241a3",
    "JZkLQqK13qhYEy4np99DTx7jZ5xygAFrm": "https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=JZkLQqK13qhYEy4np99DTx7jZ5xygAFrm&tab=overview&ts=1790244604&sign=cb5308a69141d20ada8b8a5a7cda925d",
    "EMKO7QdnjZTB4OYeldnVi4LnrxgDDdFW2": "https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=EMKO7QdnjZTB4OYeldnVi4LnrxgDDdFW2&tab=overview&ts=1790244604&sign=611b2b727a8297ee991fbf2ed0bbfa93",
    "0Z0WeLp1dLfeMQ5v6o31FnpxoGKpjBiLw": "https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=0Z0WeLp1dLfeMQ5v6o31FnpxoGKpjBiLw&tab=overview&ts=1790244793&sign=02e90043da435cac147c836417bfd9a7",
    # 重采：修正词云与差评
    "3Z649OBD1oFEBM7YnOjwcJ410p8vmBFjA": "https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=3Z649OBD1oFEBM7YnOjwcJ410p8vmBFjA&tab=overview&ts=1790244793&sign=10d4613389633a583b0a8f82309b91fd",
    "BZkMxyX1vrSpvERLVmxnH6rleZv4Kdf68": "https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=BZkMxyX1vrSpvERLVmxnH6rleZv4Kdf68&tab=overview&ts=1790244793&sign=b4f8fc87866631294bdf55008a1e4b81",
    "3Z6vd1E3wqFEBVA1oApxtJ9j630mpXHjZ": "https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=3Z6vd1E3wqFEBVA1oApxtJ9j630mpXHjZ&tab=overview&ts=1790244793&sign=17502c01b8dc8199e20cd495458504d8",
}

def wb(action, args=None, wait=0):
    with open(REQ_FILE, "w", encoding="utf-8") as f:
        json.dump({"action": action, "args": args or {}, "session": SESSION}, f, ensure_ascii=False)
    try:
        r = subprocess.run(["curl.exe", "-s", "-X", "POST", WB, "-H", "Content-Type: application/json",
                            "--data-binary", "@" + REQ_FILE], capture_output=True, text=True,
                           encoding="utf-8", timeout=60)
        out = json.loads(r.stdout)
    except Exception as e:
        return {"ok": False, "err": str(e)}
    if wait: time.sleep(wait)
    return out

def click_by_prefix(prefix):
    """点击文本以 prefix 开头的元素（如 '差评(368)'）"""
    code = ("(() => { var els=[...document.querySelectorAll('div,span,a,li,button')]"
            ".filter(function(e){ var t=(e.innerText||'').trim(); return t.indexOf('" + prefix + "')===0 && t.length<20 && e.children.length<=2; });"
            "if(els.length){ els[els.length-1].click(); return 'ok:'+els[els.length-1].innerText.trim(); } return 'nf'; })()")
    return wb("evaluate", {"code": code})

def get_text():
    r = wb("evaluate", {"code": "document.body.innerText"})
    if not r.get("ok"): return ""
    try: return json.loads(r["data"]["value"])
    except Exception: return r["data"].get("value", "")

def parse_wordcloud(txt):
    """词云表：序号 / 词 / 评价数 / 占比"""
    out = []
    # 定位词云区
    idx = txt.find("占比")
    if idx < 0: return out
    body = txt[idx:idx + 8000]
    # 模式：行首数字 → 词 → 数字 → 百分比
    for mm in re.finditer(r"(?:^|\n)(\d{1,3})\s*\n\s*([^\n]{1,14}?)\s*\n\s*([\d.]+)\s*\n\s*([\d.]+)%", body):
        w = mm.group(2).strip()
        if w in ("评价词", "评价数", "占比", "全部", "关键词", "短语"): continue
        out.append({"rank": int(mm.group(1)), "word": w, "count": mm.group(3), "pct": float(mm.group(4))})
        if len(out) >= 60: break
    return out

def parse_reviews(txt):
    out = {"reviews": []}
    idx = txt.find("评价时间")
    if idx > 0:
        body = txt[idx:idx + 12000]
        for mm in re.finditer(r"([^\n]{6,200}?)\s*\n\s*(\d{4}-\d{2}-\d{2})\s*\n\s*(\d{2}:\d{2}:\d{2})", body):
            out["reviews"].append({"content": mm.group(1).strip(), "date": mm.group(2), "time": mm.group(3)})
            if len(out["reviews"]) >= 25: break
    return out

def parse_sentiment(txt):
    m = re.search(r"全部\(([^)]+)\)\s*好评\(([^)]+)\)\s*中评\(([^)]+)\)\s*差评\(([^)]+)\)", txt)
    if m: return {"全部": m.group(1), "好评": m.group(2), "中评": m.group(3), "差评": m.group(4)}
    return {}

def parse_audience(txt):
    out = {"summary": "", "gender": [], "region": [], "prefer": "", "age": ""}
    m = re.search(r"基础画像[：:]\s*([^\n]+)", txt)
    if m: out["summary"] = m.group(1).strip()
    m2 = re.search(r"内容偏好[：:]\s*([^\n]+)", txt)
    if m2: out["prefer"] = m2.group(1).strip()
    ma = re.search(r"年龄集中分布在([^，,\n]+)[，,]\s*占比([\d.]+)%", txt)
    if ma: out["age"] = {"range": ma.group(1).strip(), "pct": float(ma.group(2))}
    # ★ 兜底：飞瓜文案里「年龄集中分布在31-40， 占比51.35%」的分隔符有时是逗号+空格、
    #   有时夹了换行，老正则要求紧跟逗号 → 解析成 None，但 summary 明明有值。
    #   实测 9 行画像里 3 行（凌博士/雏菊的天空/白云山）因此丢了年龄。
    #   这里再不依赖标点，直接从「年龄集中分布在」往后找第一个「X-Y岁/50+」+ 后面的百分比。
    if not out.get("age"):
        ma2 = re.search(
            r"年龄[^\n]{0,20}?((?:\d{1,2}[-~—]\d{1,2})|(?:\d{1,2}\s*岁以下)|(?:50\+|55\+|60\+))"
            r"[^\d%]{0,12}?([\d.]+)\s*%", txt)
        if ma2:
            out["age"] = {"range": ma2.group(1).strip().replace("~", "-").replace("—", "-"),
                          "pct": float(ma2.group(2))}
    g = re.search(r"性别分布([\s\S]{0,260})", txt)
    if g:
        for mm in re.finditer(r"(男性|女性)\s*([\d.]+)%\s*\n?\s*TGI\s*([\d.]+)", g.group(1)):
            out["gender"].append({"gender": mm.group(1), "pct": float(mm.group(2)), "tgi": float(mm.group(3))})
    r = re.search(r"地域分布([\s\S]{0,400})", txt)
    if r:
        for mm in re.finditer(r"([一-龥]{2,4})\s*\n\s*([\d.]+)%", r.group(1)):
            out["region"].append({"region": mm.group(1), "pct": float(mm.group(2))})
            if len(out["region"]) >= 12: break
    return out

def collect(gid, url):
    wb("navigate", {"url": url}, wait=7)
    base = get_text()
    info = {}
    for key, pat in [("brand", r"\n品牌\s*\n\s*([^\n]+)"), ("shop", r"\n小店\s*\n\s*([^\n]+)"),
                     ("category3", r"\n分类\s*\n\s*([^\n]+)"), ("sales30d", r"近30天销量[：:]\s*\n?\s*([^\n]+)")]:
        m = re.search(pat, base)
        if m: info[key] = m.group(1).strip()
    m = re.search(r"共([\d.]+w?)条评价好评([\d.]+)%", base)
    if m: info["reviewCount"], info["goodRate"] = m.group(1), float(m.group(2))
    m = re.search(r"商品销售榜/([^/]+)/月榜第(\d+)名", base)
    if m: info["rank"] = {"cat": m.group(1), "monthRank": int(m.group(2))}
    m = re.search(r"^(【[^\n]+】[^\n]+|[^\n]{10,80})\n复制标题", base, re.M)
    if m: info["title"] = m.group(1).strip()

    # 商品评价
    click_by_prefix("商品评价"); time.sleep(6)
    t1 = get_text()
    senti, wc, revs = parse_sentiment(t1), parse_wordcloud(t1), parse_reviews(t1)["reviews"]
    # 差评专项
    click_by_prefix("差评"); time.sleep(5)
    t2 = get_text()
    neg = parse_reviews(t2)["reviews"]
    # 受众画像
    click_by_prefix("受众画像"); time.sleep(6)
    aud = parse_audience(get_text())
    return {"gid": gid, "fetchDate": TODAY, "info": info, "audience": aud,
            "sentiment": senti, "wordcloud": wc, "reviews": revs, "negativeReviews": neg}

def main():
    os.makedirs(RAW, exist_ok=True)
    for i, (gid, url) in enumerate(TARGETS.items(), 1):
        print(f"[{i}/{len(TARGETS)}] {gid[:12]}", flush=True)
        try:
            d = collect(gid, url)
            with open(os.path.join(RAW, f"feigua_detail_{gid[:12]}.json"), "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=1)
            print(f"    ✓ {d['info'].get('brand','?')} | 词云{len(d['wordcloud'])} 评价{len(d['reviews'])} 差评{len(d['negativeReviews'])} | {d['info'].get('category3','?')}", flush=True)
        except Exception as e:
            print(f"    ✗ {e}", flush=True)
    # 合并
    allf = {}
    for fp in os.listdir(RAW):
        if fp.startswith("feigua_detail_") and fp.endswith(".json"):
            d = json.load(open(os.path.join(RAW, fp), encoding="utf-8"))
            allf[d["gid"]] = d
    with open(os.path.join(RAW, "feigua_details_all.json"), "w", encoding="utf-8") as f:
        json.dump({"fetchedAt": TODAY, "count": len(allf), "details": allf}, f, ensure_ascii=False, indent=1)
    print(f"\n[done] 合并 {len(allf)} 个商品")

if __name__ == "__main__":
    main()
