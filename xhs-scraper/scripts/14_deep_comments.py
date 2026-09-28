# -*- coding: utf-8 -*-
"""
14_deep_comments.py — 第 5 步（可选）：对已抓笔记再深挖一轮评论

和 13 的差别：这版会滚动「内部可滚动容器」（评论区常是独立滚动区），
所以经常能比 13 多扒出一些。

★ 实测提醒：对**同一批旧链接**重刷，收益很小（xsec_token 过期后
  页面只给回已缓存的那部分，实测 115 篇只多 13 条）。
  真正有效的扩量方式 = 回第 1 步重新搜索拿新笔记。
  本步的价值是「把已抓到但评论没展开全的那些笔记再压一压」。

用法: python 14_deep_comments.py [--limit 30] [--cat cleanser]
  只处理「已抓条数 < 声明条数」的笔记，优先补差距最大的。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xcommon as X

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
  var cs=[...document.querySelectorAll('.parent-comment, .comment-item')].map(function(e){
    return (e.innerText||'').trim(); });
  var cnt=''; var m=document.body.innerText.match(/(\\d+)\\s*条评论/); if(m) cnt=m[1];
  return JSON.stringify({comments:cs, commentCount:cnt});
})()"""


def main():
    opt, _ = X.cli("评论二次深挖")
    cfg = X.load_cfg(explicit=opt.config, cat=opt.cat)
    wb = X.WB(cfg._session, cfg._tmp)

    limit = opt.limit or 30

    # 挑「实际抓到的 < 页面声明的」笔记，按差距从大到小
    targets = []
    for f in sorted(os.listdir(cfg._notes)):
        if not f.endswith(".json"):
            continue
        d = X.jload(os.path.join(cfg._notes, f), {}) or {}
        have = len(d.get("comments") or [])
        try:
            decl = int(d.get("commentCount") or 0)
        except Exception:
            decl = 0
        if decl == 0 or have < decl:
            targets.append((f, have, decl))
    targets.sort(key=lambda x: -(x[2] - x[1]))
    targets = targets[:limit]
    if not targets:
        print("[done] 没有需要深挖的笔记（都抓全了，或目录为空）", flush=True)
        return 0
    print(f"[info] 待深挖 {len(targets)} 篇", flush=True)

    added_total = 0
    for i, (f, have, decl) in enumerate(targets, 1):
        p = os.path.join(cfg._notes, f)
        d = X.jload(p, {}) or {}
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

        r = wb.eval_json(JS_EXTRACT)
        blocks = (r or {}).get("comments") or []
        if r and r.get("commentCount"):
            d["commentCount"] = r["commentCount"]

        have_txt = {c["content"] for c in (d.get("comments") or [])}
        added = 0
        for b in blocks:
            c = X.parse_comment_block(b)
            if c and c["content"] not in have_txt:
                have_txt.add(c["content"])
                d.setdefault("comments", []).append(c)
                added += 1
        d["deepFetched"] = cfg._today
        X.jdump(d, p)
        added_total += added
        print(f"[{i}/{len(targets)}] {str(d.get('title',''))[:26]} | 原有{have} +新{added} "
              f"= {len(d.get('comments', []))}（声明{decl}）", flush=True)

    print(f"\n[done] 深挖新增评论 {added_total} 条", flush=True)
    if added_total <= max(3, len(targets) // 10):
        print("       提示：新增很少，通常是 xsec_token 已过期。"
              "想扩量请重跑 10_collect_links.py 拿新笔记。", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
