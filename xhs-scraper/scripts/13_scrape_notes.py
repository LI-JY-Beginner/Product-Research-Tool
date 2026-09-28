# -*- coding: utf-8 -*-
"""
13_scrape_notes.py — 第 4 步：逐篇打开笔记，抓正文 + 评论（尽量多抓）

输入: raw/xhs_picked.json（没有就退回 raw/xhs_candidates_clean.json）
输出: raw/xhs_output/note_<nid>.json

抓取手法：
  1) 打开笔记（统一走 /explore/<nid>?xsec_token=...，实测比 /search_result/ 稳）
  2) 分阶段下滑 + 反复点「展开N条回复 / 查看更多评论」，让懒加载的评论渲染出来
  3) 读 #detail-title / #detail-desc / .parent-comment / .comment-item

已知限制（如实说明，不装作能拿到）：
  · 小红书只渲染"可见范围"的评论，声明 1000 条的笔记实际能读到的通常几十到一百多条
  · 二次深挖（14_deep_comments.py）能再补一点，但 xsec_token 过期后会几乎无新增
  · 想大幅扩量，正确做法是回去重跑 10_collect_links.py 拿新笔记，
    而不是反复重刷同一批旧链接

用法: python 13_scrape_notes.py [--limit 40] [--cat cleanser]
"""
import glob
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xcommon as X

# 展开所有可展开的回复/评论（点 3 轮，每轮同时滚到底）
JS_EXPAND = """(() => {
  let clicked = 0;
  for (let round = 0; round < 3; round++) {
    const nodes = [...document.querySelectorAll('div,span,button,a')];
    for (const e of nodes) {
      const t = (e.innerText || '').trim();
      if (!t) continue;
      if (/^展开\\d*条?回复$|^展开更多评论$|更多回复|查看更多评论|展开更多|共\\d+条回复/.test(t)) {
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
                         commentCount:cnt, comments:cs});
})()"""


def main():
    opt, _ = X.cli("笔记正文 + 评论采集")
    cfg = X.load_cfg(explicit=opt.config, cat=opt.cat)
    wb = X.WB(cfg._session, cfg._tmp)

    picked_p = os.path.join(cfg._raw, "xhs_picked.json")
    if os.path.exists(picked_p):
        cands = X.jload(picked_p, {}).get("items", [])
        print(f"[info] 用高价值清单 xhs_picked.json（{len(cands)} 条）", flush=True)
    else:
        cands = X.jload(os.path.join(cfg._raw, "xhs_candidates_clean.json"), {}).get("candidates", [])
        print("[info] 没有 xhs_picked.json，退回用全部候选", flush=True)
    if not cands:
        raise SystemExit("[缺少输入] 请先跑 12_pick_notes.py")

    limit = opt.limit or len(cands)
    cands = cands[:limit]

    nc = cfg.getpath("collect.notes", {}) or {}
    rounds = nc.get("rounds", 2)
    scrolls = nc.get("scrollTo", [900, 1800, 2700, 3600, 4500, 6000, 7500])
    max_comments = nc.get("maxComments", 120)
    nav_wait = nc.get("navWait", 5)
    gap = nc.get("gap", 1.2)

    done = total_comments = 0
    for i, c in enumerate(cands, 1):
        nid = c.get("nid") or X.note_id_from_url(c.get("url", ""))
        tok = X.token_from_url(c.get("url", ""))
        if not nid or not tok:
            continue
        fp = os.path.join(cfg._notes, f"note_{nid[:16]}.json")
        if os.path.exists(fp):                    # 断点续跑：已抓过的跳过
            continue
        url = X.build_note_url(nid, tok)
        wb("navigate", {"url": url}, wait=nav_wait)

        # 分阶段下滑，中途穿插「展开回复」
        half = max(1, len(scrolls) // 2)
        for y in scrolls[:half]:
            wb("evaluate", {"code": f"window.scrollTo(0,{y})"}, wait=1.2)
        for _ in range(rounds):
            wb("evaluate", {"code": JS_EXPAND}, wait=2.2)
        for y in scrolls[half:]:
            wb("evaluate", {"code": f"window.scrollTo(0,{y})"}, wait=1.2)
        wb("evaluate", {"code": JS_EXPAND}, wait=2.0)

        d = wb.eval_json(JS_EXTRACT)
        if not d:
            txt = wb.eval_text("document.body.innerText") or ""
            ok, why = X.login_ok(txt)
            if not ok:
                print(f"⚠️ 小红书登录过期（{why}），停止采集。已抓 {done} 篇，登录后重跑本步可续传。", flush=True)
                break
            d = {"title": "", "desc": "", "author": "", "comments": [], "commentCount": ""}

        nd = {"nid": nid, "url": url, "fetchDate": cfg._today,
              "title": d.get("title") or c.get("title", ""),
              "desc": d.get("desc", ""),
              "author": (d.get("author", "") or "").split("\n")[0][:24],
              "like": d.get("like", ""),
              "commentCount": d.get("commentCount", ""),
              "keyword": c.get("keyword", ""), "tag": c.get("tag", ""),
              "srcTitle": c.get("title", ""), "likes": c.get("likes", ""),
              "comments": []}

        seen = set()
        for b in (d.get("comments") or []):
            cc = X.parse_comment_block(b)
            if cc and cc["content"] not in seen:
                seen.add(cc["content"])
                nd["comments"].append(cc)
            if len(nd["comments"]) >= max_comments:
                break

        X.jdump(nd, fp)
        done += 1
        total_comments += len(nd["comments"])
        print(f"[{i}/{len(cands)}] {nd['title'][:30]} | 正文{len(nd['desc'])}字 "
              f"评论{len(nd['comments'])}条 (累计{total_comments})", flush=True)
        time.sleep(gap)

    print(f"\n[done] 本次抓取 {done} 篇，评论 {total_comments} 条 → {cfg._notes}", flush=True)
    nfiles = len(glob.glob(os.path.join(cfg._notes, "*.json")))
    print(f"       目录内累计 {nfiles} 篇笔记", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
