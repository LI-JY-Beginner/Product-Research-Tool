# -*- coding: utf-8 -*-
"""11 · 补采：属性（规格/成分）+ 受众画像（消费人群）+ 商品评价（好评/差评/差评率）
产出 data/profile.json
用法:
  python scripts/11_collect_profile.py                 # 全部 30 个（可断点续跑）
  PROFILE_ONLY_GIDS=gid1,gid2 python scripts/11_collect_profile.py
  PROFILE_TOPN=5 python scripts/11_collect_profile.py
"""
import os, sys, json, time, re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
import pcommon as P

DATA = os.path.join(BASE, "data")
HELPER = open(os.path.join(BASE, "tmp", "_helper.js"), encoding="utf-8").read()
OUT = os.path.join(DATA, "profile.json")
LOG = open(os.path.join(BASE, "tmp", "11_profile.log"), "w", encoding="utf-8")


def out(*a):
    s = " ".join(str(x) for x in a)
    LOG.write(s + "\n"); LOG.flush(); print(s, flush=True)


cards = json.load(open(os.path.join(DATA, "cards.json"), encoding="utf-8"))
items = []
for gid, c in cards.items():
    c = dict(c); c["gid"] = gid
    items.append(c)
items.sort(key=lambda x: (x.get("榜_rank") or 999))

ONLY = [x for x in os.environ.get("PROFILE_ONLY_GIDS", "").split(",") if x.strip()]
if ONLY:
    items = [i for i in items if i["gid"] in ONLY]
TOPN = int(os.environ.get("PROFILE_TOPN", "0"))
if TOPN:
    items = items[:TOPN]

OK_MARK = ("attr", "audience", "review")


def seg(txt, key, nxt_keys, cap=2500):
    """从 body_text 里切出某个 tab 之后到下一个 tab 之前的内容"""
    i = txt.find(key)
    if i < 0:
        return ""
    j = len(txt)
    for k in nxt_keys:
        p = txt.find(k, i + len(key))
        if p > 0:
            j = min(j, p)
    return txt[i:j][:cap].strip()


def one(it):
    gid = it["gid"]
    ts, sg = it.get("ts", ""), it.get("sign", "")
    d = {"gid": gid, "title": it.get("title")}

    P.wb("navigate", {"url": "https://dy.feigua.cn/app/#/product-rank/index?tab=product", "newTab": True}, wait=8)
    time.sleep(7)
    P.ev(HELPER); P.install_hook()
    P.ev("location.hash='#/goods-detail/index?id=&gid=%s&tab=overview&ts=%s&sign=%s'" % (gid, ts, sg))
    time.sleep(13); P.ev("window.__killMask()")

    # ---------- 1. 属性 ----------
    P.ev("window.__clickText('属性')")
    time.sleep(6); P.ev("window.__killMask()")
    t = P.body_text()
    d["attr_text"] = seg(t, "属性", ["带货视频", "带货直播", "带货达人", "受众画像", "商品评价"], 2500)
    out("   属性 %s 字" % len(d["attr_text"]))

    # ---------- 2. 受众画像 ----------
    P.ev("window.__clickText('受众画像')")
    time.sleep(10); P.ev("window.__killMask()")
    t2 = P.body_text()
    d["audience_text"] = seg(t2, "受众画像", ["商品评价", "相似商品", "带货视频"], 3000)
    out("   受众画像 %s 字" % len(d["audience_text"]))
    # 画像里的图表取值：找带百分号的短文本对
    charts = P.ev(r"""
(function(){
  var res=[];
  document.querySelectorAll('*').forEach(function(el){
    if(el.children.length) return;
    var s=(el.innerText||'').trim();
    if(/^[\d.]+%$/.test(s)){
      var p=el.closest('div');
      var lbl='';
      for(var k=0;k<4&&p;k++){ var t=(p.innerText||'').split('\n')[0]; if(t&&t.length<12){lbl=t;break;} p=p.parentElement; }
      res.push({v:s, near:lbl});
    }
  });
  return JSON.stringify(res.slice(0,80));
})()
""", wait=0)
    d["audience_pcts"] = charts if isinstance(charts, (list, str)) else charts

    # ---------- 3. 商品评价 ----------
    P.ev("window.__clickText('商品评价')")
    time.sleep(10); P.ev("window.__killMask()")
    t3 = P.body_text()
    d["review_text"] = seg(t3, "商品评价", ["相似商品", "带货视频", "属性"], 3500)
    out("   商品评价 %s 字" % len(d["review_text"]))

    P.wb("close_tab", {}, timeout=20)
    time.sleep(1)
    return d


def main():
    prof = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    out("login:", P.check_login(), " 商品数=%s" % len(items))
    done = 0
    for i, it in enumerate(items):
        gid = it["gid"]
        old = prof.get(gid) or {}
        if all(old.get(k) for k in OK_MARK):
            out("[%d/%d] skip 已补采 %s" % (i + 1, len(items), (it.get("title") or "")[:24]))
            continue
        out("\n[%d/%d] %s" % (i + 1, len(items), (it.get("title") or "")[:40]))
        try:
            d = one(it)
        except Exception as e:
            out("   !! 异常:", e)
            d = dict(old); d.update({"gid": gid, "title": it.get("title"), "err": str(e)})
        prof[gid] = d
        done += 1
        json.dump(prof, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    out("\n已写 data/profile.json (%d 个，本次 %d)" % (len(prof), done))
    for g, d in prof.items():
        out("  %s 属性%s 画像%s 评价%s" % (g[:12], len(d.get("attr_text") or ""),
                                        len(d.get("audience_text") or ""), len(d.get("review_text") or "")))


if __name__ == "__main__":
    main()
