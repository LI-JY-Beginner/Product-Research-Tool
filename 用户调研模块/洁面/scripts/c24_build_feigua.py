# -*- coding: utf-8 -*-
"""
c24_build_feigua.py — 洁面：把飞瓜原始数据落成 洁面/data/top10.json + audience.json

★ 字段结构严格对齐眼油模块（02_build_outputs.py），这样 03_build_html.py 不用改渲染逻辑：
  top10.json  = {fetchDate, items:[{brand,isSelf,spuCount,talent,video,live,salesTier,score,
                                    spus[{title,gid,sales,talent,video,live}],reason,source,
                                    fetchDate,category}], excluded, criteria}
  audience.json = {fetchDate, rows:[{brand,title,isSelf,summary,femalePct,ageRange,agePct,
                                     regionTop3,regions,gender,prefer,source,fetchDate}],
                   insights:[{text,evidence}], source}
★ 铁律：isSelf 恒为 false —— 所有品牌一视同仁，不做自家/竞品二分。

输入: raw/feigua_goods_洁面_<date>.json (c20)  + raw/feigua_gid_洁面_<date>.json (c22)
      + raw/feigua_profile_洁面_<date>.json (c23)
输出: 洁面/data/top10.json , 洁面/data/audience.json
"""
import json, os, re, sys
from collections import Counter
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import c20_feigua_rank as C   # 复用 is_noise / guess_brand（唯一噪音与品牌口径）

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw")
DATA = os.path.join(BASE, "data")
os.makedirs(DATA, exist_ok=True)
TODAY = datetime.now().strftime("%Y-%m-%d")
CAT = {"L1": "个护家清", "L2": "面部护理", "L3": "洁面"}
SRC_TOP10 = "飞瓜数据·商品榜（个护家清/关键词：洗面奶·洁面，近30天）"
SRC_AU = "飞瓜商品详情页 → 受众画像 Tab（消费者画像）"

# ---------- 工具 ----------
def norm(t):
    return re.sub(r"[【】\[\]（）()「」\s,，。!！]+", "", t or "")


# 详情页「品牌」字段偶尔会被窄栏折行截断（实测 THE WHOO/后 → "The"），这里按标题兜底回正
BRAND_FIX = [
    (lambda b, t: b.strip().upper() in ("THE", "") and "后" in t, "THE WHOO/后"),
]


def fix_brand(b, t):
    for cond, val in BRAND_FIX:
        try:
            if cond(b or "", t or ""):
                return val
        except Exception:
            pass
    return (b or "").strip() or "—"


def num(s):
    """'34.8w' → 348000 ; '71' → 71 ; '2.5w-5w' → 25000（取下界）"""
    s = (s or "").replace(",", "").strip()
    if not s:
        return 0
    s = s.split("-")[0]
    try:
        if s.endswith("w") or s.endswith("W"):
            return int(float(s[:-1]) * 10000)
        return int(float(s))
    except Exception:
        m = re.search(r"[\d.]+", s)
        return int(float(m.group())) if m else 0


def pct(s):
    """'96.72%' → 96.72"""
    try:
        return round(float(str(s).replace("%", "").strip()), 2)
    except Exception:
        return None


def latest(pat):
    fs = sorted([f for f in os.listdir(RAW) if f.startswith(pat)])
    return os.path.join(RAW, fs[-1]) if fs else None


def jload(p):
    return json.load(open(p, encoding="utf-8")) if p and os.path.exists(p) else None


# ========== 产出1：TOP10 品牌玩家 ==========
def build_top10():
    """★ 指标来源优先级：商品详情页概览（稳定渲染）> 商品榜列表解析（懒渲染易错位）
    两者都按品牌聚合，打分口径与眼油模块一致：达人0.4 + 视频0.35 + 直播0.25"""
    pf = jload(latest("feigua_profile_洁面_"))
    gp = jload(latest("feigua_goods_洁面_"))
    gd = jload(latest("feigua_gid_洁面_"))
    if not pf and not gp:
        print("× 缺 feigua_profile_洁面_*.json 与 feigua_goods_洁面_*.json（先跑 c20/c23）")
        return None

    # gid 回填：按归一化标题匹配（商品榜列表 → gid）
    gmap = {}
    if gd:
        for g in gd["goods"]:
            if g.get("gid") and g.get("title"):
                gmap[norm(g.get("title"))[:38]] = g["gid"]

    agg = {}
    excluded = []

    def put(brand, title, gid, sales, talent, video, live):
        b = fix_brand(brand, title)
        a = agg.setdefault(b, {"brand": b, "spus": [], "talent": 0, "video": 0, "live": 0,
                               "salesTier": set(), "isSelf": False})
        a["spus"].append({"title": (title or "")[:46], "gid": gid, "sales": sales or "—",
                          "talent": talent, "video": video, "live": live})
        a["talent"] += num(talent)
        a["video"] += num(video)
        a["live"] += num(live)
        if sales:
            a["salesTier"].add(sales)

    n_det = 0
    if pf:
        for gid, d in pf.items():
            if d.get("noData"):
                continue
            title = d.get("title") or ""
            if C.is_noise(title):
                excluded.append({"name": title[:40], "reason": "品类噪音：非洁面产品（详情页复核为洗脸巾/香皂等）"})
                continue
            ov = d.get("ov") or {}
            put(d.get("brand"), title, gid, ov.get("销售额"),
                ov.get("带货达人"), ov.get("带货视频"), ov.get("带货直播"))
            n_det += 1

    # ★ 商品榜列表**不参与** TOP10 打分：实测它与详情页差异极大
    #   （例：BUV 榜单解析出「带货视频 34.8w」，详情页真实值是 3.2w —— 榜单列错位把播放量/浏览量算进来了）。
    #   列表只作为「商品池规模」的证据写进 source，不进指标。
    n_list = 0
    if not pf and gp:            # 仅当详情页数据完全缺失时才降级用榜单
        tier_ok = re.compile(r"^\d+(\.\d+)?w(\+|-|$)")
        for g in gp["goods"]:
            title = g.get("title") or ""
            if C.is_noise(title):
                excluded.append({"name": title[:40], "reason": "品类噪音：非洁面产品（关键词误命中）"})
                continue
            st = g.get("salesTier") or ""
            if not tier_ok.match(st):
                continue
            put(g.get("brand"), title, gmap.get(norm(title)[:38], ""), st,
                g.get("talentCount"), g.get("videoCount"), g.get("liveCount"))
            n_list += 1

    pool_n = len([g for g in (gp or {}).get("goods", []) if not C.is_noise(g.get("title") or "")]) if gp else 0
    src = SRC_TOP10 + ("；商品池共 %d 个洁面商品（榜单扫描），其 TOP30 进详情页取准确指标" % pool_n if pool_n else "")
    items = []
    for b, a in agg.items():
        score = a["talent"] * 0.4 + a["video"] * 0.35 + a["live"] * 0.25
        items.append({
            "brand": b, "isSelf": False, "spuCount": len(a["spus"]),
            "talent": a["talent"], "video": a["video"], "live": a["live"],
            "salesTier": sorted(a["salesTier"], key=lambda s: -len(s))[:1] or ["—"],
            "score": round(score, 1), "spus": a["spus"][:4],
            "reason": f"达人{a['talent']} + 视频{a['video']} + 直播{a['live']}",
            "source": src, "fetchDate": TODAY, "category": CAT,
        })
    items.sort(key=lambda x: -x["score"])

    out = {"fetchDate": TODAY, "items": items[:10], "excluded": excluded,
           "criteria": ("飞书工作流 3.1：月销>500万 或 近3月增速>50%；排除非洁面品类误命中（洗脸巾 / 卸妆油 / 香皂等）。"
                        "指标一律取飞瓜商品详情页「商品数据」段（销售额 / 销量 / 带货视频 / 带货直播 / 带货达人），"
                        "不用商品榜列表的 innerText 解析值（懒渲染易错位）"),
           "stats": {"detailSpus": n_det, "listSpus": n_list, "brandCandidates": len(items), "poolSize": pool_n}}
    json.dump(out, open(os.path.join(DATA, "top10.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"✓ top10.json：{len(items[:10])} 个品牌（候选 {len(items)}；"
          f"来源 详情页{n_det} + 榜单降级{n_list}；商品池 {pool_n}；剔除噪音 {len(excluded)}）")
    for x in items[:10]:
        print(f"   {x['score']:>9}  {x['brand']:<10} SPU{x['spuCount']} 达人{x['talent']} "
              f"视频{x['video']} 直播{x['live']} {x['salesTier'][0]}")
    return out


# ========== 产出2：受众画像 ==========
def _pick(arr, key=None):
    return arr or []


def build_audience():
    pf = jload(latest("feigua_profile_洁面_"))
    if not pf:
        print("× 缺 feigua_profile_洁面_*.json（先跑 c23）")
        return None
    rows, dropped = [], 0
    for gid, d in pf.items():
        title = d.get("title") or ""
        if C.is_noise(title):      # 卸妆油/洗脸巾等误命中不进画像
            dropped += 1
            continue
        a = d.get("audience") or {}
        if not a:
            continue
        gender = [{"gender": x["n"], "pct": pct(x["r"])} for x in (a.get("Gender") or []) if x.get("n")]
        fem = next((x["pct"] for x in gender if x["gender"] == "女性"), None)
        ages = [(x["n"], pct(x["r"])) for x in (a.get("Age") or []) if x.get("n")]
        ages_ok = [(n, p) for n, p in ages if p is not None]
        age_top = max(ages_ok, key=lambda t: t[1]) if ages_ok else (None, None)
        # ★ 飞瓜画像字段实测叫 Province / Hobbys（不是 Region / Interest），两个名字都兜住
        reg_src = a.get("Province") or a.get("Region") or []
        regs = [{"region": x["n"], "pct": pct(x["r"])} for x in reg_src[:10] if x.get("n")]
        hob_src = a.get("Hobbys") or a.get("Interest") or []
        inter = [x["n"] for x in hob_src[:3] if x.get("n")]

        s_fem = f"女性最多，占{fem}%" if fem is not None else "性别分布未返回"
        s_age = f"年龄集中分布在{age_top[0]}，占比{age_top[1]}%" if age_top[0] else ""
        top3 = [r["region"] for r in regs[:3]]
        s_reg = ("地域集中在" + "、".join(top3) + "，占比"
                 + str(round(sum(r["pct"] for r in regs[:3] if r["pct"] is not None), 2)) + "%") if top3 else ""
        summary = "；".join([x for x in (s_fem, s_age, s_reg) if x]) + "；"

        rows.append({
            "brand": fix_brand(d.get("brand"), d.get("title")),
            "title": (d.get("title") or "")[:40],
            "isSelf": False,
            "summary": summary,
            "femalePct": fem,
            "ageRange": age_top[0], "agePct": age_top[1],
            "regionTop3": top3, "regions": regs, "gender": gender,
            "prefer": ("喜欢" + "、".join(inter) + "视频居多") if inter else "",
            "nReviews": d.get("n_reviews"), "rateBad": d.get("rate_bad"),
            "source": f"飞瓜商品详情页·受众画像（gid={gid[:12]}）",
            "fetchDate": d.get("fetchDate", TODAY),
        })
    rows.sort(key=lambda x: -(x["femalePct"] or 0))

    ins = []
    fem = [r["femalePct"] for r in rows if r["femalePct"] is not None]
    if fem:
        ins.append({"text": f"品类女性占比均值 {sum(fem)/len(fem):.1f}%"
                            f"（区间 {min(fem):.1f}% ~ {max(fem):.1f}%，{len(fem)} 个商品）",
                    "evidence": "飞瓜受众画像·性别分布（各商品详情页）"})
    ages = [r["ageRange"] for r in rows if r["ageRange"]]
    if ages:
        top = "、".join(f"{k}（{v} 个商品）" for k, v in Counter(ages).most_common(3))
        ins.append({"text": f"主力人群年龄段分布：{top}",
                    "evidence": "飞瓜受众画像·年龄分布（各商品详情页）"})
    regs = Counter()
    for r in rows:
        for x in (r.get("regions") or [])[:5]:
            regs[x["region"]] += 1
    if regs:
        ins.append({"text": "高频地域 TOP5：" + "、".join(f"{k}（{v} 个商品）" for k, v in regs.most_common(5)),
                    "evidence": "飞瓜受众画像·地域分布（各商品详情页）"})
    hobs = Counter()
    for gid, d in pf.items():
        if C.is_noise(d.get("title") or ""):
            continue
        a = d.get("audience") or {}
        for x in (a.get("Hobbys") or a.get("Interest") or [])[:5]:
            if x.get("n"):
                hobs[x["n"]] += 1
    if hobs:
        ins.append({"text": "高频内容偏好 TOP5：" + "、".join(f"{k}（{v} 个商品）" for k, v in hobs.most_common(5)),
                    "evidence": "飞瓜受众画像·视频喜好（各商品详情页）"})
    bads = [r["rateBad"] for r in rows if r.get("rateBad") is not None]
    if bads:
        ins.append({"text": f"商品评价差评率均值 {sum(bads)/len(bads):.2f}%"
                            f"（区间 {min(bads):.2f}% ~ {max(bads):.2f}%，{len(bads)} 个商品）",
                    "evidence": "飞瓜商品详情页·商品评价（好评/中评/差评计数）"})

    out = {"fetchDate": TODAY, "rows": rows, "insights": ins, "source": SRC_AU}
    json.dump(out, open(os.path.join(DATA, "audience.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"✓ audience.json：{len(rows)} 个商品画像，{len(ins)} 条洞察（剔除卸妆/巾类 {dropped} 个）")
    for r in rows[:12]:
        print(f"   {str(r['femalePct']):>6}% {r['ageRange'] or '-':<8} {r['brand']:<10} "
              f"{(r['title'] or '')[:26]} 差评率{r.get('rateBad')}")
    for i in ins:
        print("   ·", i["text"])
    return out


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "top10"):
        build_top10()
    if which in ("all", "audience"):
        build_audience()
