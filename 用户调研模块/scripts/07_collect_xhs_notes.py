# -*- coding: utf-8 -*-
"""
07_collect_xhs_notes.py — 用 Kimi WebBridge 批量采集小红书笔记正文 + 评论
（xhs-note-scraper 需要 Chrome 9222 调试端口；本脚本走 Kimi WebBridge，无需重启浏览器）
输入: raw/xhs_candidates_clean.json（取前 N 条）
输出: raw/xhs_output/note_<nid>.json
"""
import json, os, re, subprocess, sys, time
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 自动定位：.../用户调研模块
WORKSPACE = os.path.dirname(BASE)
TMP = os.path.join(WORKSPACE, "tmp")
os.makedirs(TMP, exist_ok=True)
RAW = os.path.join(BASE, "raw")
OUT = os.path.join(RAW, "xhs_output")
WB = "http://127.0.0.1:10086/command"
SESSION = "xhs-user-research"
REQ = os.path.join(TMP, "req_xhs_notes.json")
TODAY = datetime.now().strftime("%Y-%m-%d")

N = int(sys.argv[1]) if len(sys.argv) > 1 else 20

def wb(action, args=None, wait=0):
    with open(REQ, "w", encoding="utf-8") as f:
        json.dump({"action": action, "args": args or {}, "session": SESSION}, f, ensure_ascii=False)
    try:
        r = subprocess.run(["curl.exe", "-s", "-X", "POST", WB, "-H", "Content-Type: application/json",
                            "--data-binary", "@" + REQ], capture_output=True, text=True,
                           encoding="utf-8", timeout=90)
        return json.loads(r.stdout)
    except Exception as e:
        return {"ok": False, "err": str(e)}
    finally:
        if wait: time.sleep(wait)

def get_text():
    r = wb("evaluate", {"code": "document.body.innerText"})
    if not r.get("ok"): return ""
    try: return json.loads(r["data"]["value"])
    except Exception: return r["data"].get("value", "")

def login_ok(txt):
    for b in ["重新登录", "登录超限", "已退出登录", "手机号登录", "扫码登录"]:
        if b in txt[:500]: return False
    return True

JS_EXTRACT = """(() => {
  var q=function(s){var e=document.querySelector(s);return e?(e.innerText||'').trim():'';};
  var cs=[...document.querySelectorAll('.parent-comment, .comment-item')].map(function(e){
    return (e.innerText||'').trim();
  });
  return JSON.stringify({title:q('#detail-title'), desc:q('#detail-desc'),
                         author:q('.author-container'), comments:cs.slice(0,25)});
})()"""

TIME_LINE = re.compile(r"^(\d{2}-\d{2}[\u4e00-\u9fa5]{0,8}|\d{4}-\d{2}-\d{2}|\d+分钟前|\d+小时前|\d+天前|昨天|前天|刚刚)[\u4e00-\u9fa5]{0,10}$")

def parse_comment_block(block):
    """从 .parent-comment 的 innerText 解析：昵称 / 内容 / 时间地点"""
    lines = [l.strip() for l in block.split("\n") if l.strip()]
    if len(lines) < 2: return None
    nick = lines[0]
    idx = None
    for i, l in enumerate(lines[1:], 1):
        if TIME_LINE.match(l): idx = i; break
    if idx is None:
        content, t = " ".join(lines[1:3]), ""
    else:
        content, t = " ".join(lines[1:idx]), lines[idx]
    if len(content) < 3: return None
    return {"nickname": nick, "content": content[:200], "time": t}

def parse_note(txt):
    """txt 是 JS_EXTRACT 返回的 JSON 字符串"""
    out = {"title": "", "desc": "", "comments": [], "author": ""}
    try:
        d = json.loads(txt)
    except Exception:
        return out
    out["title"] = d.get("title", "")
    out["desc"] = d.get("desc", "")
    out["author"] = d.get("author", "").split("\n")[0][:20]
    for b in d.get("comments", []):
        c = parse_comment_block(b)
        if c: out["comments"].append(c)
    return out

def main():
    os.makedirs(OUT, exist_ok=True)
    picked_p = os.path.join(RAW, "xhs_picked.json")
    if os.path.exists(picked_p):
        # 优先采「高价值筛选清单」（已剔除教程类）
        cands = json.load(open(picked_p, encoding="utf-8"))["items"][:N]
        print(f"[info] 使用高价值清单 xhs_picked.json（{len(cands)} 条）")
    else:
        cands = json.load(open(os.path.join(RAW, "xhs_candidates_clean.json"), encoding="utf-8"))["candidates"][:N]
    done, fail = 0, 0
    for i, c in enumerate(cands, 1):
        m = re.search(r"/(?:search_result|explore|discovery/item)/([0-9a-f]{20,32})", c["url"])
        tok = re.search(r"xsec_token=([^&]+)", c["url"])
        if not m or not tok: continue
        url = f"https://www.xiaohongshu.com/explore/{m.group(1)}?xsec_token={tok.group(1)}&xsec_source=pc_search"
        wb("navigate", {"url": url}, wait=5)
        wb("evaluate", {"code": "window.scrollTo(0,1200)"}, wait=2)
        r = wb("evaluate", {"code": JS_EXTRACT})
        txt = r.get("data", {}).get("value", "") if r.get("ok") else ""
        if not txt:
            t2 = get_text()
            if not login_ok(t2):
                print("⚠️ 小红书登录过期，停止采集"); break
        nd = parse_note(txt)
        nd.update({"nid": m.group(1), "url": url, "keyword": c.get("keyword", ""),
                   "tag": c.get("tag", ""), "fetchDate": TODAY, "srcTitle": c.get("title", "")})
        if not nd["title"]: nd["title"] = c.get("title", "")
        with open(os.path.join(OUT, f"note_{m.group(1)[:16]}.json"), "w", encoding="utf-8") as f:
            json.dump(nd, f, ensure_ascii=False, indent=1)
        done += 1
        print(f"[{i}/{len(cands)}] {nd['title'][:34]} | 正文{len(nd['desc'])}字 评论{len(nd['comments'])}条", flush=True)
        time.sleep(1.5)
    print(f"\n[done] 成功 {done} / 失败 {fail} → {OUT}")

if __name__ == "__main__":
    main()
