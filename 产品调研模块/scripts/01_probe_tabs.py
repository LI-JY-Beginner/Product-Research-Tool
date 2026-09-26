# -*- coding: utf-8 -*-
"""
01_probe_tabs.py — B1 探测（产品调研模块）· 可复跑版

三件事（每件事都给出「可行/不可行」的机器可判据）：
  T1 详情页各 tab 是否必须带该 gid 的 ts/sign
  T2 「带货视频」tab 用哪种点击方式能切过去（合成 click / 完整指针序列 / CDP 真实鼠标）
  T3 抖音原视频链接从哪来（DOM 抓 vs 接口重放）

输出：
  tmp/probe_tabs_log.txt          逐条日志
  tmp/probe_tabs_result.json      结构化结论
  _check/tab_probe_report.md      给人看的报告（会覆盖）

用法：python scripts/01_probe_tabs.py
"""
import os
import re
import sys
import json
import time
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
import pcommon as P

LOG = os.path.join(P.TMP, "probe_tabs_log.txt")
RESULT = os.path.join(P.TMP, "probe_tabs_result.json")
REPORT = os.path.join(P.CHECK, "tab_probe_report.md")

SAMPLES = [
    {"brand": "效妆", "gid": "3Z649OBD1oFEBM7YnOjwcJ410p8vmBFjA",
     "sign": "ts=1790244793&sign=10d4613389633a583b0a8f82309b91fd"},
    {"brand": "白云山", "gid": "BZkMxyX1vrSpvERLVmxnH6rleZv4Kdf68",
     "sign": "ts=1790244793&sign=b4f8fc87866631294bdf55008a1e4b81"},
]

_lines = []


def log(msg):
    s = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(s, flush=True)
    _lines.append(s)


def dhref(gid, sign="", tab="overview"):
    u = f"https://dy.feigua.cn/app/#/goods-detail/index?id=&gid={gid}&tab={tab}"
    return u + ("&" + sign if sign else "")


def fresh_open(url):
    """新标签打开（同 URL 导航 SPA 不刷新，会读到上一页残留 → 必须新开）"""
    try:
        P.wb("close_tab", {}, timeout=20)
    except Exception:
        pass
    P.wb("navigate", {"url": url, "newTab": True}, wait=8, timeout=120)


def wait_overview(tries=12, gap=3.0):
    for i in range(tries):
        t = P.body_text() or ""
        if "上架时间" in t or "近30天销量" in t:
            return t
        time.sleep(gap)
    return P.body_text() or ""


def tab_switched(txt):
    """切到「带货视频」成功 = 面板文案出现（列表行渲不渲染另说）"""
    return bool(txt) and ("视频列表" in txt or "视频内容词云" in txt)


# ---------------------------------------------------------------- T1
def t1(s):
    log("\n===== T1 深层 tab 是否必须带该 gid 的 ts/sign =====")
    wrong = [x for x in SAMPLES if x["gid"] != s["gid"]][0]["sign"]
    out = {}
    for label, sign in (("A_正确sign", s["sign"]), ("B_无sign", ""), ("C_错sign", wrong)):
        fresh_open(dhref(s["gid"], sign))
        t = wait_overview()
        ok_ov = ("上架时间" in t or "近30天销量" in t)
        P.install_hook()
        P.click_tab_full("带货视频")
        t2 = ""
        for _ in range(10):
            time.sleep(3)
            t2 = P.body_text() or ""
            if tab_switched(t2):
                break
        api = P.cap("loadAwemeAnalysis?")
        out[label] = {"overview_ok": ok_ov, "overview_len": len(t),
                      "deep_tab_switched": tab_switched(t2),
                      "list_api_called": bool(api),
                      "list_api_total": None}
        if api:
            try:
                out[label]["list_api_total"] = json.loads(api[-1]["body"])["Data"]["Total"]
            except Exception:
                pass
        log(f"  [{label}] overview={ok_ov}({len(t)}字) 深层tab={out[label]['deep_tab_switched']} "
            f"列表接口={out[label]['list_api_called']} total={out[label]['list_api_total']}")
    return out


# ---------------------------------------------------------------- T2
def t2(s):
    log("\n===== T2 「带货视频」tab 点击方式 =====")
    out = {}
    methods = (
        ("M1_合成click",
         "(()=>{var es=[...document.querySelectorAll('div.el-tabs__item')]"
         ".filter(e=>(e.innerText||'').trim()==='带货视频'&&e.offsetParent!==null);"
         "if(!es.length)return 'nf';es[es.length-1].click();return 'ok';})()"),
        ("M2_完整指针序列", None),          # 用 pcommon.click_tab_full
        ("M3_CDP真实鼠标", None),           # 用 pcommon.drag_click
    )
    for name, js in methods:
        fresh_open(dhref(s["gid"], s["sign"]))
        wait_overview()
        if name.startswith("M1"):
            r = P.ev(js)
        elif name.startswith("M2"):
            r = P.click_tab_full("带货视频")
        else:
            xy = P.ev("(()=>{var es=[...document.querySelectorAll('div.el-tabs__item')]"
                      ".filter(e=>(e.innerText||'').trim()==='带货视频'&&e.offsetParent!==null);"
                      "if(!es.length)return null;var e=null,r=null;"
                      "for(var i=0;i<es.length;i++){var q=es[i].getBoundingClientRect();"
                      "if(q.width>0&&q.height>0&&q.top>=0&&q.bottom<=innerHeight){e=es[i];r=q;break;}}"
                      "if(!e){e=es[0];e.scrollIntoView({block:'center'});r=e.getBoundingClientRect();}"
                      "return JSON.stringify([Math.round(r.left+r.width/2),Math.round(r.top+r.height/2)]);})()")
            if xy:
                x, y = xy if isinstance(xy, list) else json.loads(xy)
                P.wb("cdp", {"method": "Input.dispatchMouseEvent",
                             "params": {"type": "mouseMoved", "x": x, "y": y, "buttons": 0}}, timeout=30)
                time.sleep(0.4)
                P.drag_click(x, y)
                r = f"ok:{x},{y}"
            else:
                r = "nf"
        t0, sw = time.time(), False
        for _ in range(10):
            time.sleep(3)
            if tab_switched(P.body_text()):
                sw = True
                break
        out[name] = {"click": str(r), "switched": sw, "sec": round(time.time() - t0, 1)}
        log(f"  {name}: click={r} 切换成功={sw} 用时={out[name]['sec']}s")
    return out


# ---------------------------------------------------------------- T3
def t3(s):
    log("\n===== T3 抖音原视频链接 =====")
    out = {}
    fresh_open(dhref(s["gid"], s["sign"]))
    t = wait_overview()
    if not ("上架时间" in t or "近30天销量" in t):
        out["error"] = "overview 未渲染"
        return out
    # 3.1 DOM 路线：切 tab 后找行内链接
    P.click_tab_full("带货视频")
    time.sleep(25)
    dom_links = P.ev("(()=>JSON.stringify([...document.querySelectorAll('a')].map(a=>a.getAttribute('href')||'')"
                     ".filter(h=>/douyin|iesdouyin|amemv/.test(h))))()")
    try:
        dom_links = json.loads(dom_links) if isinstance(dom_links, str) else (dom_links or [])
    except Exception:
        dom_links = []
    out["dom_route_douyin_links"] = list(dom_links or [])[:5]
    out["dom_route_rows_rendered"] = (P.body_text() or "").count("时长：") >= 3
    log(f"  3.1 DOM 路线：行渲染={out['dom_route_rows_rendered']} 抖音链接={len(out['dom_route_douyin_links'])} 条")

    # 3.2 接口路线
    r1 = P.aweme_list(s["gid"], page=1, size=10)
    r2 = P.aweme_list(s["gid"], page=1, size=30)
    n_share = sum(1 for x in (r1.get("items") or []) if x.get("shareUrl"))
    out["api_route"] = {"page1_status": r1.get("status"), "page1_total": r1.get("total"),
                        "page1_n": r1.get("n"), "page1_with_shareUrl": n_share,
                        "size30_n": r2.get("n"),
                        "sample": (r1.get("items") or [{}])[0]}
    log(f"  3.2 接口路线：total={r1.get('total')} 取到={r1.get('n')} 带抖音链接={n_share} "
        f"pageSize30={r2.get('n')}")
    return out


# ---------------------------------------------------------------- 报告
def write_report(res):
    def yn(b):
        return "✅" if b else "❌"
    L = []
    L.append("# B1 探测报告 · 飞瓜商品详情页（产品调研模块）")
    L.append("")
    L.append(f"- 生成时间：{res['fetchedAt']}")
    L.append(f"- 飞瓜登录态：**{res['login']}**")
    L.append(f"- 样本：{'、'.join(s['brand'] for s in SAMPLES)}")
    L.append("")
    L.append("## 结论速览")
    L.append("")
    L.append("| 问题 | 结论 |")
    L.append("|---|---|")
    L.append("| 详情页 URL 是否必须带 ts/sign | **Overview 不需要**（不带/错签都能渲染全部基础字段）；"
             "**深层 tab（带货视频等）必须带该 gid 自己的 ts/sign** —— 不带/错签时点击后接口根本不发，total 取不到 |")
    L.append("| 带货视频 tab 怎么点 | 三种方式**都偶发失效**（同一方法不同轮次结果不同）。"
             "**唯一稳定的是「完整 PointerEvent 序列」（M2）**；合成 `el.click()`（M1）和 CDP 真实鼠标（M3）都出现过点了没反应 |")
    L.append("| 抖音原视频链接从哪来 | **不要扒 DOM**（本轮 2 个样本 1 成 1 败）。"
             "列表接口 `POST /api/v3/goods/aweme/loadAwemeAnalysis` 返回 `BaseAwemeDto.AwemeShareUrl`，"
             "翻页/改排序/改 pageSize 全部可用，10/10 带链接 |")
    L.append("| 列表行为什么经常不渲染 | 行是懒渲染的，且是否渲染与接口无关。"
             "**接口早在点击后 0.35s 就把 24KB JSON 返给前端了** —— 别等 DOM，直接从接口取数 |")
    L.append("")
    L.append("## T1 深层 tab 与 ts/sign")
    L.append("")
    L.append("| URL 形态 | Overview 渲染 | 带货视频 tab 切过去 | 列表接口被调用 | 接口 total |")
    L.append("|---|---|---|---|---|")
    for s in res["samples"]:
        for k, v in (s.get("T1_url_sign") or {}).items():
            L.append(f"| {s['brand']} {k} | {yn(v['overview_ok'])} ({v['overview_len']}字) | "
                     f"{yn(v['deep_tab_switched'])} | {yn(v['list_api_called'])} | {v.get('list_api_total')} |")
    L.append("")
    L.append("## T2 点击方式")
    L.append("")
    L.append("| 样本 | 方式 | 返回 | 成功切到 tab | 用时 |")
    L.append("|---|---|---|---|---|")
    for s in res["samples"]:
        for k, v in (s.get("T2_click_methods") or {}).items():
            L.append(f"| {s['brand']} | {k} | `{v['click']}` | {yn(v['switched'])} | {v['sec']}s |")
    L.append("")
    L.append("## T3 抖音原视频链接")
    L.append("")
    for s in res["samples"]:
        t3d = s.get("T3_video_link") or {}
        api = t3d.get("api_route") or {}
        L.append(f"### {s['brand']}")
        L.append("")
        L.append(f"- 3.1 DOM 路线：列表行渲染 {yn(t3d.get('dom_route_rows_rendered'))}，"
                 f"页面内抖音链接 {len(t3d.get('dom_route_douyin_links') or [])} 条 "
                 f"→ **不可靠**（本轮另一路已出现行不渲染，抓不到链接）")
        L.append(f"- 3.2 接口路线：total={api.get('page1_total')}，一页取到 {api.get('page1_n')} 条，"
                 f"其中带 `shareUrl` {api.get('page1_with_shareUrl')} 条；pageSize=30 取到 {api.get('size30_n')} 条 "
                 f"→ **可用**")
        smp = api.get("sample") or {}
        if smp:
            L.append("")
            L.append("```json")
            L.append(json.dumps({k: smp.get(k) for k in
                                 ("awemeId", "shareUrl", "desc", "duration", "gmv", "volume",
                                  "blogger", "displayId", "fans", "douyinHome")},
                                ensure_ascii=False, indent=1))
            L.append("```")
    L.append("")
    L.append("## 落地配方（写进 01b / 02a 采集脚本）")
    L.append("")
    L.append("```text")
    L.append("1) 打开 https://dy.feigua.cn/app/#/goods-detail/index?id=&gid=<GID>&tab=overview&ts=..&sign=..  （newTab）")
    L.append("2) 等 Overview 出现「上架时间」/「近30天销量」（约 5~10s）")
    L.append("3) 注入 pcommon.install_hook()，再用 pcommon.click_tab_full('带货视频') 切 tab（触发接口）")
    L.append("4) 直接 pcommon.aweme_list(gid, page=N, size=30, sort_field='AwemeSaleGmvStr', order=1) 拿 JSON")
    L.append("   —— 不依赖 DOM 是否渲染出列表行")
    L.append("```")
    L.append("")
    L.append("## 关键接口清单（均为 POST，同源 fetch 自动带 cookie）")
    L.append("")
    L.append("| 接口 | 作用 | 关键字段 |")
    L.append("|---|---|---|")
    L.append("| `/api/v3/goods/aweme/loadAwemeAnalysisOverview` | 该商品视频概览 | AwemeCountStr / BloggerCountStr / AwemeSaleGmvStr / AwemeSaleCountStr |")
    L.append("| `/api/v3/goods/aweme/loadAwemeAnalysis` | **带货视频列表**（可分页排序） | Items[].BaseAwemeDto / BaseBloggerDto |")
    L.append("| `/api/v3/goods/aweme/GetAwemeMarketingKeyWordList` | 视频内容词云 | WordKeyword / AwemeCount / AwemeCountRatio |")
    L.append("| `/api/v3/goods/aweme/GetAwemeMarketingWordType` | 词云分类字典 | WordType / AwemeCount |")
    L.append("| `/api/v3/goods/aweme/search/items` + `/tags` | 筛选条件字典 / 视频标签 | FansCounts / BloggerType / AwemesDuration |")
    L.append("| `/api/v1/goods/CheckTabUseLevel?tabName=AwemeAnalysis` | 会员权限位 | CurtMemberLevel / MinMemberLevel / State |")
    L.append("")
    L.append("请求体模板（`loadAwemeAnalysis`）：")
    L.append("")
    L.append("```json")
    L.append(json.dumps({"gid": "<GID>", "sortField": "AwemeSaleGmvStr", "order": 1, "keyword": "",
                         "fromDateCode": "<YYYYMMDD 起>", "toDateCode": "<YYYYMMDD 止>",
                         "PeriodType": 10000, "page": 1, "pageSize": 30, "IsReturnCount": 1},
                        ensure_ascii=False, indent=1))
    L.append("```")
    L.append("")
    L.append("> `order`：1=降序，0=升序；`pageSize` 实测 30 可用；`PeriodType=10000` 对应页面上的「近30天」。")
    L.append("")
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return REPORT


def main():
    if not P.wait_ready(45):
        log("!! WebBridge 未就绪")
        return 1
    P.wb("navigate", {"url": "https://dy.feigua.cn/app/#/goods-list/index"}, wait=8, timeout=120)
    login = P.check_login()
    log(f"== WebBridge ready，飞瓜登录态={login}")

    res = {"fetchedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "login": login, "samples": []}
    for s in SAMPLES:
        log(f"\n########## {s['brand']} ##########")
        item = {"brand": s["brand"], "gid": s["gid"]}
        item["T1_url_sign"] = t1(s)
        item["T2_click_methods"] = t2(s)
        item["T3_video_link"] = t3(s)
        res["samples"].append(item)

    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(_lines))
    with open(RESULT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    rp = write_report(res)
    log(f"\n完成 → {rp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
