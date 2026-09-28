# -*- coding: utf-8 -*-
"""
c04_collect_xhs.py — 洁面（洗面奶）小红书候选笔记采集
沿用眼油模块 04 脚本的取数方式（Kimi WebBridge + 页面 DOM 取 a[href] 带 xsec_token）
差异：关键词换成洁面/洗面奶口径；每个关键词多滚几屏，尽量多拿笔记
用法: python c04_collect_xhs.py
输出: raw/xhs_links_<日期>.json
"""
import json, os, re, subprocess, sys, time
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../洁面
WORKSPACE = os.path.dirname(os.path.dirname(BASE))
TMP = os.path.join(WORKSPACE, "tmp")
os.makedirs(TMP, exist_ok=True)
RAW = os.path.join(BASE, "raw")
os.makedirs(RAW, exist_ok=True)
WB = "http://127.0.0.1:10086/command"
SESSION = "xhs-cleanser-research"
REQ = os.path.join(TMP, "req_c04.json")
TODAY = datetime.now().strftime("%Y-%m-%d")

# 洁面 / 洗面奶 关键词（围绕需求 / 痛点 / 求安利 / 吐槽）
XHS_KEYWORDS = [
    ("洗面奶", "综合"), ("洗面奶推荐", "求安利"), ("洗面奶避雷", "吐槽"),
    ("洗面奶测评", "测评"), ("洗面奶 平价", "需求"), ("洗面奶 学生", "需求"),
    ("氨基酸洗面奶", "需求"), ("洗面奶 油皮", "需求"), ("洗面奶 干皮", "需求"),
    ("洗面奶 敏感肌", "需求"), ("洗面奶 痘肌", "需求"), ("洗面奶 智商税", "吐槽"),
    ("洗面奶 紧绷", "痛点"), ("洗面奶 假滑", "痛点"), ("洗面奶 黑头", "需求"),
    ("洁面推荐", "求安利"), ("洁面 测评", "测评"), ("洗面奶 空瓶", "需求"),
    ("洗面奶 翻车", "吐槽"), ("男士洗面奶", "需求"),
]
# 噪音：不是「面部洁面」的命中
NOISE = ["沐浴", "洗发", "沐浴露", "洗发水", "卸妆", "美甲", "洗衣机", "洗洁精",
         "宠物", "狗狗", "猫", "洗碗", "洗手液", "私处", "内衣", "鞋", "地毯"]


def wb(action, args=None, wait=0):
    with open(REQ, "w", encoding="utf-8") as f:
        json.dump({"action": action, "args": args or {}, "session": SESSION}, f, ensure_ascii=False)
    try:
        r = subprocess.run(["curl.exe", "-s", "-X", "POST", WB, "-H", "Content-Type: application/json",
                            "--data-binary", "@" + REQ], capture_output=True, text=True,
                           encoding="utf-8", timeout=60)
        return json.loads(r.stdout)
    except Exception as e:
        return {"ok": False, "err": str(e)}
    finally:
        if wait:
            time.sleep(wait)


def get_text():
    r = wb("evaluate", {"code": "document.body.innerText"})
    if not r.get("ok"):
        return ""
    try:
        return json.loads(r["data"]["value"])
    except Exception:
        return r["data"].get("value", "")


def check_login(txt):
    bad = ["重新登录", "登录超限", "已退出登录", "超出登录设备上限", "扫码登录", "手机号登录"]
    for b in bad:
        if b in txt[:600]:
            return False, b
    return True, ""


JS_LINKS = """(() => { var o=[]; document.querySelectorAll('a[href]').forEach(function(a){
  var h=a.getAttribute('href')||''; if(h.indexOf('xsec_token')<0) return;
  var t=(a.innerText||'').trim();
  var sec=a.closest('section')||a.parentElement.parentElement;
  var st=(sec&&sec.innerText||'');
  var m=st.match(/([\\d.]+)w?\\s*\\n?\\s*(赞|点赞)/);
  o.push({title:t.slice(0,80), url:h, likes:(m?m[1]:'')}); });
  var seen={}; return JSON.stringify(o.filter(function(x){
    if(!x.title||seen[x.url])return false; seen[x.url]=1; return true; }).slice(0,40)); })()"""


def collect():
    print("=== 小红书 · 洁面/洗面奶 候选笔记采集 ===", flush=True)
    out, expired = [], False
    for i, (kw, tag) in enumerate(XHS_KEYWORDS, 1):
        url = f"https://www.xiaohongshu.com/search_result?keyword={kw.replace(' ', '%20')}&type=51"
        wb("navigate", {"url": url}, wait=6)
        items = []
        # 多滚几屏，尽量多拿
        for y in (1500, 3000, 4500):
            wb("evaluate", {"code": f"window.scrollTo(0,{y})"}, wait=1.8)
        txt = get_text()
        ok, why = check_login(txt)
        if not ok:
            print(f"  ⚠️ 小红书登录过期（{why}），请重新扫码登录后重跑", flush=True)
            expired = True
            break
        r = wb("evaluate", {"code": JS_LINKS})
        try:
            items = json.loads(r["data"]["value"])
        except Exception:
            items = []
        for it in items:
            it["keyword"], it["tag"], it["fetchDate"] = kw, tag, TODAY
            it["isNoise"] = any(n in it["title"] for n in NOISE)
        out += items
        print(f"  [{i}/{len(XHS_KEYWORDS)}] {kw} → {len(items)} 条", flush=True)
    fp = os.path.join(RAW, f"xhs_links_{TODAY.replace('-','')}.json")
    json.dump({"fetchedAt": TODAY, "count": len(out), "links": out},
              open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"  → {fp}（{len(out)} 条）", flush=True)
    return out, expired


if __name__ == "__main__":
    collect()
