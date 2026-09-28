# -*- coding: utf-8 -*-
"""
c07b_deep_comments.py — 二次深挖：对已采笔记重新打开，滚动评论区容器 + 反复展开回复，补齐评论
用法: python c07b_deep_comments.py [只处理评论数<该阈值的笔记，默认9999] [最多处理篇数]
"""
import json, os, re, subprocess, sys, time
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.dirname(os.path.dirname(BASE))
TMP = os.path.join(WORKSPACE, "tmp")
os.makedirs(TMP, exist_ok=True)
RAW = os.path.join(BASE, "raw")
OUT = os.path.join(RAW, "xhs_output")
WB = "http://127.0.0.1:10086/command"
SESSION = "xhs-cleanser-research"
REQ = os.path.join(TMP, "req_c07b.json")
TODAY = datetime.now().strftime("%Y-%m-%d")

THRESH = int(sys.argv[1]) if len(sys.argv) > 1 else 9999
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else 999

# 滚动所有可滚动容器（评论区通常在内部容器里）
JS_SCROLL = """(() => {
  let n=0;
  const cands=[...document.querySelectorAll('div')].filter(d=>d.scrollHeight>d.clientHeight+150 && d.clientHeight>150);
  cands.forEach(d=>{ try{ d.scrollTop=d.scrollHeight; n++; }catch(e){} });
  window.scrollTo(0, document.body.scrollHeight);
  return n;
})()"""

JS_EXPAND = """(() => {
  let clicked=0;
  for(let r=0;r<4;r++){
    const nodes=[...document.querySelectorAll('div,span,button,a')];
    for(const e of nodes){
      const t=(e.innerText||'').trim();
      if(!t) continue;
      if(/^展开\\s*\\d*\\s*条?回复$|更多回复|查看更多评论|展开更多|共\\s*\\d+\\s*条回复|查看全部\\s*\\d+\\s*条回复/.test(t)){
        try{ e.click(); clicked++; }catch(err){}
      }
    }
    const cands=[...document.querySelectorAll('div')].filter(d=>d.scrollHeight>d.clientHeight+150&&d.clientHeight>150);
    cands.forEach(d=>{ try{ d.scrollTop=d.scrollHeight; }catch(e){} });
  }
  return clicked;
})()"""

JS_EXTRACT = """(() => {
  var q=function(s){var e=document.querySelector(s);return e?(e.innerText||'').trim():'';};
  var cs=[...document.querySelectorAll('.parent-comment, .comment-item')].map(function(e){
    return (e.innerText||'').trim(); });
  var cnt=''; var m=document.body.innerText.match(/(\\d+)\\s*条评论/); if(m) cnt=m[1];
  return JSON.stringify({title:q('#detail-title'), comments:cs.slice(0,200), commentCount:cnt});
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


def main():
    fs = sorted(os.listdir(OUT))
    targets = []
    for f in fs:
        if not f.endswith(".json"):
            continue
        d = json.load(open(os.path.join(OUT, f), encoding="utf-8"))
        have = len(d.get("comments", []) or [])
        decl = d.get("commentCount", "")
        try:
            decln = int(decl)
        except Exception:
            decln = 0
        if have < THRESH and (decln == 0 or have < decln):
            targets.append((f, d, have, decln))
    targets.sort(key=lambda x: -(x[3] - x[2]))
    targets = targets[:LIMIT]
    print(f"[info] 待深挖 {len(targets)} 篇（阈值 {THRESH}）", flush=True)

    added_total = 0
    for i, (f, d, have, decln) in enumerate(targets, 1):
        url = d.get("url", "")
        if not url:
            continue
        wb("navigate", {"url": url}, wait=5)
        for _ in range(2):
            wb("evaluate", {"code": JS_SCROLL}, wait=1.5)
            wb("evaluate", {"code": JS_EXPAND}, wait=2.0)
        for _ in range(3):
            wb("evaluate", {"code": JS_SCROLL}, wait=1.5)
        wb("evaluate", {"code": JS_EXPAND}, wait=2.0)
        r = wb("evaluate", {"code": JS_EXTRACT})
        txt = r.get("data", {}).get("value", "") if r.get("ok") else ""
        try:
            j = json.loads(txt)
            blocks = j.get("comments", [])
            if j.get("commentCount"):
                d["commentCount"] = j["commentCount"]
        except Exception:
            blocks = []
        have_txt = {c["content"] for c in (d.get("comments") or [])}
        added = 0
        for b in blocks:
            c = parse_comment_block(b)
            if c and c["content"] not in have_txt:
                have_txt.add(c["content"])
                d.setdefault("comments", []).append(c)
                added += 1
        d["deepFetched"] = TODAY
        json.dump(d, open(os.path.join(OUT, f), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        added_total += added
        print(f"[{i}/{len(targets)}] {d.get('title','')[:26]} | 原有{have} +新{added} = {len(d.get('comments',[]))}（声明{decln}）", flush=True)
    print(f"\n[done] 深挖新增评论 {added_total} 条", flush=True)


if __name__ == "__main__":
    main()
