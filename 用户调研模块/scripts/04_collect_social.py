# -*- coding: utf-8 -*-
"""
04_collect_social.py — B步骤：小红书帖子 + 抖音种草视频采集（挖掘用户购买原因）
依赖登录态：小红书 / 飞瓜，任一过期会跳过该平台并提示重新登录
用法：
  python 04_collect_social.py xhs      # 只抓小红书候选链接
  python 04_collect_social.py feigua   # 只抓飞瓜带货视频
  python 04_collect_social.py all
输出：
  raw/xhs_links_<关键词>.json          小红书候选笔记（标题+点赞+链接）
  用户调研模块/候选笔记确认清单.md      给用户过目的清单（★阻塞点）
  raw/feigua_videos_<gid>.json        飞瓜带货视频（种草视频标题+达人+数据）
"""
import json, os, re, subprocess, sys, time
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 自动定位：.../用户调研模块
WORKSPACE = os.path.dirname(BASE)
TMP = os.path.join(WORKSPACE, "tmp")
os.makedirs(TMP, exist_ok=True)
RAW = os.path.join(BASE, "raw")
WB = "http://127.0.0.1:10086/command"
SESSION = "xhs-user-research"
REQ = os.path.join(TMP, "req_social.json")
TODAY = datetime.now().strftime("%Y-%m-%d")

# 小红书关键词（围绕眼油品类需求/痛点/求安利/吐槽）
XHS_KEYWORDS = [
    ("眼油", "综合"), ("眼油避雷", "吐槽"), ("眼油推荐", "求安利"),
    ("眼部精华油", "综合"), ("眼油测评", "测评"), ("眼周抗老", "需求"),
    ("以油养肤 眼周", "需求"), ("眼油 智商税", "吐槽"),
    ("眼纹 眼油", "需求"), ("黑眼圈 眼油", "需求"),
]
# 噪音标题（与眼部护理无关，需剔除）
NOISE = ["美甲", "甲油胶", "指甲", "带鱼", "护发", "发油", "精油皂", "卸妆", "洗发", "沐浴"]

# 飞瓜带货视频（TOP10 代表商品）
FEIGUA_VIDEOS = {
    "3Z649OBD1oFEBM7YnOjwcJ410p8vmBFjA": ("效妆", "10d4613389633a583b0a8f82309b91fd", "1790244793"),
    "3Z6vd1E3wqFEBVA1oApxtJ9j630mpXHjZ": ("美雀琳", "17502c01b8dc8199e20cd495458504d8", "1790244793"),
    "BZkMxyX1vrSpvERLVmxnH6rleZv4Kdf68": ("白云山", "b4f8fc87866631294bdf55008a1e4b81", "1790244793"),
    "9ZB2e8QR7ls3kzD0gXe8FApVyWpyKRIpn": ("雏菊的天空", "7654e426e2e1bee905da025588d78ef5", "1790244793"),
    "vzA9mr5qLgTmWm6vOY1wu5RndzOxDjsgJ": ("凌博士", "159591adad6959544b393cb53ff517ed", "1790244604"),
    "RKroG1lXyAil3zW3ZOdxIEg2QvXz6XS7p": ("苏彤氏", "9c058b9c78eb598713ecb029fd95362e", "1790244793"),
    "BZkm65p5qwsorkpQoxwosqvWR6QOZMc6n": ("美诗", "ca9fb4643959ab28001cc17c867241a3", "1790244604"),
}


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
        if wait: time.sleep(wait)


def get_text():
    r = wb("evaluate", {"code": "document.body.innerText"})
    if not r.get("ok"): return ""
    try: return json.loads(r["data"]["value"])
    except Exception: return r["data"].get("value", "")


def check_login(txt):
    """登录过期检测"""
    bad = ["重新登录", "登录超限", "已退出登录", "超出登录设备上限", "扫码登录", "手机号登录"]
    for b in bad:
        if b in txt[:600]: return False, b
    return True, ""


def collect_xhs():
    print("=== 小红书候选链接采集 ===")
    out, expired = [], False
    for kw, tag in XHS_KEYWORDS:
        url = f"https://www.xiaohongshu.com/search_result?keyword={kw.replace(' ', '%20')}&type=51"
        wb("navigate", {"url": url}, wait=6)
        wb("evaluate", {"code": "window.scrollTo(0,1500)"}, wait=2)
        txt = get_text()
        ok, why = check_login(txt)
        if not ok:
            print(f"  ⚠️ 小红书登录过期（{why}），请在浏览器重新扫码登录后重跑")
            expired = True
            break
        r = wb("evaluate", {"code": (
            "(() => { var o=[]; document.querySelectorAll('a[href]').forEach(function(a){"
            "var h=a.getAttribute('href')||''; if(h.indexOf('xsec_token')<0) return;"
            "var t=(a.innerText||'').trim(); var sec=a.closest('section')||a.parentElement.parentElement;"
            "var st=(sec&&sec.innerText||''); var m=st.match(/([\\d.]+)w?\\s*\\n?\\s*(赞|点赞)/);"
            "o.push({title:t.slice(0,60), url:h, likes:(m?m[1]:'')}); });"
            "var seen={}; return JSON.stringify(o.filter(function(x){ if(!x.title||seen[x.url])return false; seen[x.url]=1; return true; }).slice(0,30)); })()"
        )})
        try:
            items = json.loads(r["data"]["value"])
        except Exception:
            items = []
        for it in items:
            it["keyword"], it["tag"], it["fetchDate"] = kw, tag, TODAY
            it["isNoise"] = any(n in it["title"] for n in NOISE)
        out += items
        print(f"  [{kw}] {len(items)} 条")
    fp = os.path.join(RAW, f"xhs_links_{TODAY.replace('-','')}.json")
    json.dump({"fetchedAt": TODAY, "count": len(out), "links": out},
              open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"  → {fp}（{len(out)} 条）")
    return out, expired


def build_candidate_md(links):
    """生成给用户过目的候选清单"""
    seen, uniq = set(), []
    for l in links:
        if l["url"] in seen or l.get("isNoise"): continue
        seen.add(l["url"]); uniq.append(l)
    uniq.sort(key=lambda x: -(float(x.get("likes") or 0)))
    md = ["# 小红书候选笔记清单（请乾颖确认）", "",
          f"> 采集时间：{TODAY} ｜ 共 {len(uniq)} 条候选 ｜ 用途：挖掘用户购买原因（高频需求 TOP5）",
          "> 请回复「删几号 / 加几号」，确认后我再批量采集正文+评论", "",
          "| 序号 | 标题 | 点赞 | 类型 | 关键词 |", "|---|---|---|---|---|"]
    for i, l in enumerate(uniq, 1):
        md.append(f"| {i} | {l['title'][:44]} | {l.get('likes') or '—'} | {l['tag']} | {l['keyword']} |")
    md += ["", "## 已自动剔除（噪音）", ""]
    for l in links:
        if l.get("isNoise"): md.append(f"- {l['title'][:40]}（关键词：{l['keyword']}）")
    fp = os.path.join(BASE, "候选笔记确认清单.md")
    open(fp, "w", encoding="utf-8").write("\n".join(md))
    print(f"  → {fp}（{len(uniq)} 条候选）")
    return uniq


def collect_feigua_videos():
    print("=== 飞瓜带货视频（抖音种草视频）采集 ===")
    results = {}
    for gid, (brand, sign, ts) in FEIGUA_VIDEOS.items():
        url = (f"https://dy.feigua.cn/app/#/goods-detail/index?id=&gid={gid}"
               f"&tab=video&ts={ts}&sign={sign}")
        wb("navigate", {"url": url}, wait=7)
        txt = get_text()
        ok, why = check_login(txt)
        if not ok:
            print(f"  ⚠️ 飞瓜登录过期（{why}），请重新登录后重跑")
            return results, True
        vids = []
        # 视频行：标题 + 达人 + 点赞/评论/转发 + 发布时间
        for m in re.finditer(r"([^\n]{8,80})\n([^\n]{2,20})\n([\d.]+w?)\s*\n?\s*([\d.]+w?)?\s*\n?\s*(\d{4}-\d{2}-\d{2})", txt):
            vids.append({"title": m.group(1).strip()[:70], "talent": m.group(2).strip(),
                         "like": m.group(3), "comment": m.group(4) or "", "date": m.group(5)})
            if len(vids) >= 20: break
        if not vids:
            # 退而求其次：抓页面里所有含日期的行
            for m in re.finditer(r"([^\n]{10,90})\s*\n\s*(\d{4}-\d{2}-\d{2})", txt):
                vids.append({"title": m.group(1).strip()[:70], "talent": "", "like": "", "comment": "", "date": m.group(2)})
                if len(vids) >= 20: break
        results[gid] = {"brand": brand, "videos": vids}
        fp = os.path.join(RAW, f"feigua_videos_{gid[:12]}.json")
        json.dump({"gid": gid, "brand": brand, "fetchDate": TODAY, "videos": vids},
                  open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"  [{brand}] {len(vids)} 条视频")
    return results, False


def main():
    os.makedirs(RAW, exist_ok=True)
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("xhs", "all"):
        links, exp = collect_xhs()
        if links and not exp: build_candidate_md(links)
    if mode in ("feigua", "all"):
        collect_feigua_videos()

if __name__ == "__main__":
    main()
