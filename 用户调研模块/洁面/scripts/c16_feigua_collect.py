# -*- coding: utf-8 -*-
"""
c16_feigua_collect.py — 飞瓜采集「洁面/洗面奶」商品库（商品库 + 详情页）

思路对齐眼油模块：
  1) 进「商品/SPU → SPU库」或「实时爆款商品」，切到「个护家清」类目，逐个关键词搜索
  2) 从结果行里解析：商品标题 / gid / 品牌 / 销量档 / 达人/视频/直播数 / 好评率
  3) 对 TOP N 商品进详情页，采「受众画像」+「商品评价」（好评/差评/词云）
  4) 落 raw/feigua_goods_洁面_<date>.json 与 raw/feigua_detail_<gid12>.json

用法:
  python c16_feigua_collect.py list                 # 只采商品库列表
  python c16_feigua_collect.py detail <gid>=<url>   # 采单个商品详情
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
REQ = os.path.join(TMP, "req_c16.json")
TODAY = datetime.now().strftime("%Y-%m-%d")

# 洁面 / 洗面奶 关键词（搜索框逐个搜）
KEYWORDS = ["洗面奶", "洁面", "氨基酸洗面奶", "洗面奶 油皮", "洗面奶 敏感肌", "男士洗面奶", "洁面慕斯"]

# 非洁面的噪音（沐浴露/洗发水等误命中）
NOISE = ["沐浴", "洗发", "沐浴露", "洗发水", "卸妆", "洗手液", "洗洁精", "洗衣", "私处",
         "宠物", "狗狗", "猫", "洗碗", "内衣", "地毯", "足", "身体乳", "磨砂膏"]


def wb(action, args=None, wait=0):
    with open(REQ, "w", encoding="utf-8") as f:
        json.dump({"action": action, "args": args or {}, "session": SESSION}, f, ensure_ascii=False)
    try:
        r = subprocess.run(["curl.exe", "-s", "-X", "POST", WB, "-H", "Content-Type: application/json",
                            "--data-binary", "@" + REQ], capture_output=True, text=True,
                           encoding="utf-8", timeout=120)
        return json.loads(r.stdout)
    except Exception as e:
        return {"ok": False, "err": str(e)}
    finally:
        if wait:
            time.sleep(wait)


def ev(code, wait=0):
    r = wb("evaluate", {"code": code}, wait=wait)
    if not r.get("ok"):
        return ""
    return r.get("data", {}).get("value", "")


def set_input(ph, text):
    """往指定 placeholder 的输入框写值并派发 input/change"""
    js = """(() => {
      const el=[...document.querySelectorAll('input')].find(i=>(i.placeholder||'').indexOf(%s)>=0);
      if(!el) return 'NF';
      const setter=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
      setter.call(el, %s);
      el.dispatchEvent(new Event('input',{bubbles:true}));
      el.dispatchEvent(new Event('change',{bubbles:true}));
      return 'SET:'+el.value;
    })()""" % (json.dumps(ph, ensure_ascii=False), json.dumps(text, ensure_ascii=False))
    return ev(js)


def click_text(text, exact=True):
    js = """(() => {
      const want=%s, exact=%s;
      const els=[...document.querySelectorAll('button,.el-button,div,span,li,a')]
        .filter(e=>{const t=(e.innerText||'').trim();
          return (exact? t===want : t.indexOf(want)===0) && t.length<%d && e.children.length<=2;});
      if(!els.length) return 'NF';
      const el=els[els.length-1];
      const r=el.getBoundingClientRect();
      const o={bubbles:true,cancelable:true,view:window,clientX:r.left+r.width/2,clientY:r.top+r.height/2};
      ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(k=>
        el.dispatchEvent(new MouseEvent(k,o)));
      return 'CLICK:'+el.innerText.trim().slice(0,20);
    })()""" % (json.dumps(text, ensure_ascii=False), "true" if exact else "false", 26)
    return ev(js)


# 商品行解析：优先 <tr>，退化到卡片
JS_ROWS = """(() => {
  const out=[];
  const push=(txt, html)=>{
    const gid=(html.match(/gid=([A-Za-z0-9]{20,})/)||[])[1]||'';
    out.push({txt:(txt||'').replace(/\\n/g,'|'), gid});
  };
  const trs=[...document.querySelectorAll('tr,.el-table__row')];
  if(trs.length){
    trs.forEach(tr=>{ if((tr.innerText||'').trim().length>20)
      push(tr.innerText, tr.innerHTML); });
  } else {
    [...document.querySelectorAll('.goods-item,.goods-card,.card-item,[class*=goods]')]
      .forEach(c=>{ const t=(c.innerText||'').trim(); if(t.length>20) push(t, c.innerHTML); });
  }
  return JSON.stringify(out.slice(0,200));
})()"""


def parse_rows(rows, keyword):
    items = []
    for r in rows:
        t = r["txt"]
        if not r["gid"]:
            continue
        # 销量档：形如 25w-50w / 7.5w-10w / 100w+
        sales = ""
        m = re.search(r"(\d+(?:\.\d+)?w?\+?(?:\s*-\s*\d+(?:\.\d+)?w?)?)", t)
        for pat in [r"(\d+(?:\.\d+)?w+\s*-\s*\d+(?:\.\d+)?w+)", r"(\d+w\+)", r"(\d+(?:\.\d+)?w+)"]:
            mm = re.search(pat, t)
            if mm:
                sales = mm.group(1).replace(" ", "")
                break
        nums = re.findall(r"(?<![\d.])(\d{1,6})(?![\d.%w])", t)
        items.append({
            "gid": r["gid"], "rawText": t, "keyword": keyword,
            "fetchDate": TODAY, "sales": sales, "nums": nums[:8],
        })
    return items


def collect_list():
    wb("navigate", {"url": "https://dy.feigua.cn/app/#/real-time-goods-rank/index"}, wait=10)
    print("URL:", ev("location.href"), flush=True)
    # 切到「个护家清」
    print("切类目:", click_text("个护家清", exact=False), flush=True)
    time.sleep(4)

    seen, all_items = {}, []
    for i, kw in enumerate(KEYWORDS, 1):
        print(f"\n[{i}/{len(KEYWORDS)}] 搜「{kw}」", flush=True)
        print("  写关键词:", set_input("请输入商品关键字搜索", kw), flush=True)
        time.sleep(1)
        print("  点搜索:", click_text("搜索", exact=True), flush=True)
        time.sleep(6)
        rows = ev(JS_ROWS, wait=1)
        try:
            rs = json.loads(rows)
        except Exception:
            rs = []
        got = parse_rows(rs, kw)
        new = 0
        for it in got:
            if it["gid"] in seen:
                continue
            seen[it["gid"]] = it
            all_items.append(it)
            new += 1
        print(f"  → 行 {len(rs)} 条 / 新增 {new}（累计 {len(all_items)}）", flush=True)
        for x in got[:3]:
            print(f"     · {x['gid'][:14]} | {x['rawText'][:110]}", flush=True)

    fp = os.path.join(RAW, f"feigua_goods_洁面_{TODAY.replace('-','')}.json")
    json.dump({"fetchedAt": TODAY, "count": len(all_items), "keywords": KEYWORDS,
               "goods": all_items}, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n[list done] {fp}（{len(all_items)} 条）", flush=True)
    return all_items


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "list"
    if mode == "list":
        collect_list()
