# -*- coding: utf-8 -*-
"""
c07_collect_notes.py — 批量采集洁面笔记正文 + 评论（尽量多抓评论）
沿用眼油模块 07 的 WebBridge 取数方式，增强：
  1) 进入笔记后多次下滑 + 反复点击「展开更多回复 / 查看更多评论」
  2) 评论上限从 25 提到 120
  3) 同时记录笔记点赞/收藏/评论数（能取到就取）
用法: python c07_collect_notes.py [N条]
输出: raw/xhs_output/note_<nid>.json
"""
import json, os, re, subprocess, sys, time
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.dirname(os.path.dirname(BASE))
TMP = os.path.join(WORKSPACE, "tmp")
os.makedirs(TMP, exist_ok=True)
RAW = os.path.join(BASE, "raw")
OUT = os.path.join(RAW, "xhs_output")
os.makedirs(OUT, exist_ok=True)
WB = "http://127.0.0.1:10086/command"
SESSION = "xhs-cleanser-research"
REQ = os.path.join(TMP, "req_c07.json")
TODAY = datetime.now().strftime("%Y-%m-%d")

N = int(sys.argv[1]) if len(sys.argv) > 1 else 40

# 展开所有可展开的回复/评论
JS_EXPAND = """(() => {
  let clicked = 0;
  for (let round = 0; round < 3; round++) {
    const nodes = [...document.querySelectorAll('div,span,button,a')];
    for (const e of nodes) {
      const t = (e.innerText || '').trim();
      if (!t) continue;
      if (/^展开\\d*条?回复$|更多回复|查看更多评论|展开更多|共\\d+条回复/.test(t)) {
        try { e.click(); clicked++; } catch (err) {}
      }
    }
    window.scrollTo(0, document.body.scrollHeight);
  }
  return clicked;
})()"""

JS_EXTRACT = """(() => {
  var q=function(s){var e=document.querySelector(s);return e?(e.innerText||'').trim():'';};
  var cs=[...document.querySelectorAll('.parent-comment, .comment-item')].map(function(e){
    return (e.innerText||'').trim();
  });
  var cnt='';
  var m=document.body.innerText.match(/(\\d+)\\s*条评论/); if(m) cnt=m[1];
  return JSON.stringify({title:q('#detail-title'), desc:q('#detail-desc'),
                         author:q('.author-container'), like:q('.like-wrapper'),
                         commentCount:cnt, comments:cs.slice(0,120)});
})()"""


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


def get_text():
    r = wb("evaluate", {"code": "document.body.innerText"})
    if not r.get("ok"):
        return ""
    try:
        return json.loads(r["data"]["value"])
    except Exception:
        return r["data"].get("value", "")


def login_ok(txt):
    for b in ["重新登录", "登录超限", "已退出登录", "手机号登录", "扫码登录"]:
        if b in txt[:500]:
            return False
    return True


TIME_LINE = re.compile(r"^(\d{2}-\d{2}[\u4e00-\u9fa5]{0,8}|\d{4}-\d{2}-\d{2}|\d+分钟前|\d+小时前|\d+天前|昨天|前天|刚刚)[\u4e00-\u9fa5]{0,10}$")


def parse_comment_block(block):
    lines = [l.strip() for l in block.split("\n") if l.strip()]
    if len(lines) < 2:
        return None
    nick = lines[0]
    idx = None
    for i, l in enumerate(lines[1:], 1):
        if TIME_LINE.match(l):
            idx = i
            break
    if idx is None:
        content, t = " ".join(lines[1:3]), ""
    else:
        content, t = " ".join(lines[1:idx]), lines[idx]
    if len(content) < 3:
        return None
    return {"nickname": nick, "content": content[:300], "time": t}


def parse_note(txt):
    out = {"title": "", "desc": "", "comments": [], "author": "", "commentCount": ""}
    try:
        d = json.loads(txt)
    except Exception:
        return out
    out["title"] = d.get("title", "")
    out["desc"] = d.get("desc", "")
    out["author"] = (d.get("author", "") or "").split("\n")[0][:20]
    out["commentCount"] = d.get("commentCount", "")
    out["like"] = d.get("like", "")
    seen = set()
    for b in d.get("comments", []):
        c = parse_comment_block(b)
        if c and c["content"] not in seen:
            seen.add(c["content"])
            out["comments"].append(c)
    return out


def main():
    picked_p = os.path.join(RAW, "xhs_picked.json")
    if os.path.exists(picked_p):
        cands = json.load(open(picked_p, encoding="utf-8"))["items"][:N]
        print(f"[info] 使用高价值清单 xhs_picked.json（{len(cands)} 条）", flush=True)
    else:
        cands = json.load(open(os.path.join(RAW, "xhs_candidates_clean.json"), encoding="utf-8"))["candidates"][:N]
    done = 0
    total_comments = 0
    for i, c in enumerate(cands, 1):
        m = re.search(r"/(?:search_result|explore|discovery/item)/([0-9a-f]{20,32})", c["url"])
        tok = re.search(r"xsec_token=([^&]+)", c["url"])
        if not m or not tok:
            continue
        nid = m.group(1)
        fp = os.path.join(OUT, f"note_{nid[:16]}.json")
        url = f"https://www.xiaohongshu.com/explore/{nid}?xsec_token={tok.group(1)}&xsec_source=pc_search"
        wb("navigate", {"url": url}, wait=5)
        # 展开 + 下滑
        for y in (900, 1800, 2700, 3600):
            wb("evaluate", {"code": f"window.scrollTo(0,{y})"}, wait=1.2)
        wb("evaluate", {"code": JS_EXPAND}, wait=2.5)
        for y in (4500, 6000, 7500):
            wb("evaluate", {"code": f"window.scrollTo(0,{y})"}, wait=1.2)
        wb("evaluate", {"code": JS_EXPAND}, wait=2.0)
        r = wb("evaluate", {"code": JS_EXTRACT})
        txt = r.get("data", {}).get("value", "") if r.get("ok") else ""
        if not txt:
            t2 = get_text()
            if not login_ok(t2):
                print("⚠️ 小红书登录过期，停止采集", flush=True)
                break
        nd = parse_note(txt)
        nd.update({"nid": nid, "url": url, "keyword": c.get("keyword", ""),
                   "tag": c.get("tag", ""), "fetchDate": TODAY,
                   "srcTitle": c.get("title", ""), "likes": c.get("likes", "")})
        if not nd["title"]:
            nd["title"] = c.get("title", "")
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(nd, f, ensure_ascii=False, indent=1)
        done += 1
        total_comments += len(nd["comments"])
        print(f"[{i}/{len(cands)}] {nd['title'][:30]} | 正文{len(nd['desc'])}字 评论{len(nd['comments'])}条 (累计{total_comments})", flush=True)
        time.sleep(1.2)
    print(f"\n[done] 笔记 {done} 篇，评论 {total_comments} 条 → {OUT}", flush=True)


if __name__ == "__main__":
    main()
