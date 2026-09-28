# -*- coding: utf-8 -*-
"""
10_collect_links.py — 第 1 步：按关键词搜索，收集候选笔记链接

走浏览器真实搜索页，从 DOM 里抠带 xsec_token 的笔记链接。
输出: raw/xhs_links_<日期>.json

★ 三个坑（都在这里处理掉了）：
  1) 搜索结果里的笔记链接是 /search_result/<nid>?xsec_token=...，
     不是 /explore/<nid>。正则漏了 search_result 会静默采到 0 条。
  2) 结果里混着大量 /user/profile/ 的作者主页链接，必须过滤。
  3) 每个关键词多滚几屏能多拿几条；xsec_token 会过期，
     想扩量要重新跑本脚本拿新 token，而不是重刷旧链接。

用法: python 10_collect_links.py [--cat cleanser] [--limit 20]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xcommon as X

JS_LINKS = """(() => { var o=[]; document.querySelectorAll('a[href]').forEach(function(a){
  var h=a.getAttribute('href')||''; if(h.indexOf('xsec_token')<0) return;
  var t=(a.innerText||'').trim();
  var sec=a.closest('section')||a.parentElement.parentElement;
  var st=(sec&&sec.innerText||'');
  var m=st.match(/([\\d.]+w?)\\s*\\n?\\s*(赞|点赞)/);
  o.push({title:t.slice(0,120), url:h, likes:(m?m[1]:'')}); });
  var seen={}; return JSON.stringify(o.filter(function(x){
    if(!x.title||seen[x.url])return false; seen[x.url]=1; return true; })); })()"""


def main():
    opt, _ = X.cli("小红书候选笔记链接采集")
    cfg = X.load_cfg(explicit=opt.config, cat=opt.cat)
    wb = X.WB(cfg._session, cfg._tmp)

    kws = [(k, t) for k, t in (cfg.get("keywords") or [])]
    if opt.limit:
        kws = kws[: opt.limit]
    if not kws:
        raise SystemExit("[配置错误] keywords 是空的。请先在配置里填搜索关键词。")

    lc = cfg.getpath("collect.links", {}) or {}
    scroll_to = lc.get("scrollTo", [1500, 3000, 4500])
    scroll_wait = lc.get("scrollWait", 1.8)
    cap = lc.get("perKeywordCap", 40)
    nav_wait = lc.get("navWait", 6)
    noise = list(cfg.getpath("category.noise", []) or [])

    print(f"=== {cfg.project.name} · 候选笔记采集（{len(kws)} 组关键词）===", flush=True)
    out, expired = [], False

    for i, (kw, tag) in enumerate(kws, 1):
        url = f"https://www.xiaohongshu.com/search_result?keyword={str(kw).replace(' ', '%20')}&type=51"
        wb("navigate", {"url": url}, wait=nav_wait)
        for y in scroll_to:
            wb("evaluate", {"code": f"window.scrollTo(0,{y})"}, wait=scroll_wait)

        txt = wb.eval_text("document.body.innerText") or ""
        ok, why = X.login_ok(txt)
        if not ok:
            print(f"  ⚠️ 小红书登录过期（{why}），请重新扫码登录后重跑", flush=True)
            expired = True
            break

        items = wb.eval_json(JS_LINKS) or []
        kept = 0
        for it in items:
            u = it.get("url", "")
            if X.is_author_profile(u):          # 坑 2：作者主页链接
                continue
            nid = X.note_id_from_url(u)
            if not nid or not X.token_from_url(u):
                continue
            it["nid"] = nid
            it["keyword"], it["tag"], it["fetchDate"] = kw, tag, cfg._today
            it["isNoise"] = any(n in it["title"] for n in noise)
            out.append(it)
            kept += 1
            if kept >= cap:
                break
        print(f"  [{i}/{len(kws)}] {kw} → {kept} 条", flush=True)

    # 全量去重（同一条笔记可能命中多个关键词）
    seen, uniq = set(), []
    for x in out:
        if x["nid"] in seen:
            continue
        seen.add(x["nid"])
        uniq.append(x)

    fp = os.path.join(cfg._raw, f"xhs_links_{cfg._stamp}.json")
    X.jdump({"fetchedAt": cfg._today, "category": cfg.project.name,
             "count": len(uniq), "links": uniq}, fp)
    print(f"\n[done] 共 {len(uniq)} 条候选（去重后）→ {fp}", flush=True)
    if expired:
        print("       ⚠️ 因登录过期提前中断，登录后重跑本步即可（会把新旧合并去重）", flush=True)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
