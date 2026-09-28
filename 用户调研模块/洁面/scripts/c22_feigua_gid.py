# -*- coding: utf-8 -*-
"""
c22_feigua_gid.py — 从飞瓜「商品榜」抽取每条商品的 gid / ts / sign（详情页门票）

★ c20 只解析 innerText，拿不到 gid；但商品详情页必须靠 gid 才能进。
  商品榜每行标题其实是 <a href="#/goods-detail/index?id=..&gid=..&tab=overview&ts=..&sign=..">，
  所以直接读 DOM 的 href 就能把「标题 → gid + ts + sign」一起拿下来。

用法:
  python c22_feigua_gid.py probe          # 只探路：dump 前 10 个 href
  python c22_feigua_gid.py collect        # 全关键词采集，落 raw/feigua_gid_洁面_<date>.json
"""
import json, os, re, sys, time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import c20_feigua_rank as C   # 复用 open_rank / search / body_text / ev / wb

BASE = C.BASE
RAW = C.RAW
TMP = C.TMP
TODAY = C.TODAY
KEYWORDS = C.KEYWORDS

# 只抽这几个词的第 1 页就够覆盖头部商品；想全量就把 TOPN_KW 调大
TOPN_KW = 8

DUMP_HREFS = """(function(){
  var out=[];
  var as=[].slice.call(document.querySelectorAll('a[href*="gid="]'));
  for(var i=0;i<as.length;i++){
    var a=as[i];
    var r=a.getBoundingClientRect();
    if(r.width<=0) continue;
    out.push({href:a.getAttribute('href'), text:(a.innerText||a.textContent||'').trim().slice(0,120)});
  }
  return JSON.stringify({n:as.length, items:out.slice(0,60)});
})()"""

# 兜底：如果标题不是 <a>，就从整行 <tr> 里找 gid
DUMP_ROWS = """(function(){
  var out=[];
  var trs=[].slice.call(document.querySelectorAll('tr,tr td,div'));
  var seen={};
  var as=[].slice.call(document.querySelectorAll('[href*="gid="],a'));
  for(var i=0;i<as.length;i++){
    var a=as[i]; var h=a.getAttribute('href')||'';
    if(h.indexOf('gid=')<0) continue;
    var tr=a.closest('tr')||a.parentElement;
    var txt=(tr&&(tr.innerText||tr.textContent)||a.innerText||'').trim().replace(/\\s+/g,' ').slice(0,160);
    if(seen[h]) continue; seen[h]=1;
    out.push({href:h, row:txt});
  }
  return JSON.stringify({n:out.length, items:out.slice(0,60)});
})()"""

GID_RE = re.compile(r"gid=([A-Za-z0-9_\-]{16,})")
TS_RE = re.compile(r"[?&]ts=(\d{9,})")
SIGN_RE = re.compile(r"[?&]sign=([A-Za-z0-9]{8,})")
ID_RE = re.compile(r"[?&]id=([A-Za-z0-9_\-]+)")


def extract(js=DUMP_HREFS):
    v = C.ev(js)
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return {"n": 0, "items": []}
    return v or {"n": 0, "items": []}


def norm_title(t):
    return re.sub(r"[【】\[\]（）()「」\s]+", "", t or "")


def probe():
    C.open_rank()
    t, acts = C.search("洗面奶")
    print("搜索动作:", acts, flush=True)
    d = extract()
    print("带 gid= 的 <a> 总数:", d.get("n"), flush=True)
    for it in d.get("items", [])[:10]:
        print("  ", it["href"][:150])
        print("     text:", it.get("text", "")[:70])
    d2 = extract(DUMP_ROWS)
    print("\n[兜底] 行数:", d2.get("n"), flush=True)
    for it in d2.get("items", [])[:6]:
        print("  ", it["href"][:150])
        print("     row:", it.get("row", "")[:90])
    open(os.path.join(TMP, "c22_probe.json"), "w", encoding="utf-8").write(
        json.dumps({"a": d, "rows": d2}, ensure_ascii=False, indent=1))
    print("\n已存 tmp/c22_probe.json", flush=True)


def collect():
    C.open_rank()
    goods, seen = [], {}
    kws = KEYWORDS[:TOPN_KW]
    for i, kw in enumerate(kws, 1):
        print(f"\n[{i}/{len(kws)}] 搜「{kw}」", flush=True)
        t, acts = C.search(kw)
        d = extract()
        # 兜底：整行文本（标题 + 指标），用于 <a> 自身没有文字时回填
        d2 = extract(DUMP_ROWS)
        rowmap = {}
        for it in d2.get("items", []):
            h = it.get("href") or ""
            if h and it.get("row"):
                rowmap[h] = it["row"]
        n0 = len(goods)
        for it in d.get("items", []):
            h = it.get("href") or ""
            m = GID_RE.search(h)
            if not m:
                continue
            gid = m.group(1)
            # ★ 同一个 gid 在 DOM 里有多个 <a>：封面图链接（无文字）在前、标题链接在后。
            #   早期按 gid 去重会把「无文字」那条先存进去，导致 title 全空 —— 必须取文本更长的那条。
            txt = (it.get("text") or "").strip()
            if not txt:
                txt = (rowmap.get(h) or "").strip()
            rec = {
                "gid": gid,
                "title": txt[:160],
                "brand": C.guess_brand(txt),
                "id": (ID_RE.search(h).group(1) if ID_RE.search(h) else ""),
                "ts": (TS_RE.search(h).group(1) if TS_RE.search(h) else ""),
                "sign": (SIGN_RE.search(h).group(1) if SIGN_RE.search(h) else ""),
                "href": h,
                "keyword": kw,
                "isNoise": C.is_noise(txt),
                "kw": {kw},
            }
            prev = seen.get(gid)
            if prev is None:
                seen[gid] = rec
                goods.append(rec)
            else:
                prev["kw"].add(kw)
                if len(txt) > len(prev.get("title") or ""):
                    prev["title"] = txt[:160]
                    prev["brand"] = C.guess_brand(txt)
                    prev["isNoise"] = C.is_noise(txt)
        bad = sum(1 for x in goods if not (x.get("title") or "").strip())
        print(f"  本轮新增 {len(goods)-n0} 条，累计 {len(goods)}（带 gid 的 <a>: {d.get('n')}，无标题 {bad} 条）", flush=True)

    for g in goods:
        g["kw"] = sorted(g["kw"])
    fp = os.path.join(RAW, f"feigua_gid_洁面_{TODAY.replace('-','')}.json")
    json.dump({"fetchedAt": TODAY, "keywords": kws, "count": len(goods),
               "category": {"L1": "个护家清", "L2": "面部护理", "L3": "洁面"},
               "goods": goods}, open(fp, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\n[gid done] {fp}（{len(goods)} 条；有 sign 的 {sum(1 for x in goods if x['sign'])} 条）", flush=True)
    return goods


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "probe"
    if mode == "probe":
        probe()
    elif mode == "collect":
        collect()
