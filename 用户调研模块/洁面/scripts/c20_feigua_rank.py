# -*- coding: utf-8 -*-
"""
c20_feigua_rank.py — 飞瓜「商品榜」采集洁面/洗面奶商品池（DOM 解析路线）

★ 这是本轮探测出来的正路（对齐产品调研模块 g31/g32 的成功做法）：
  路由：#/product-rank/index?tab=product        ← goods-library 已 404，别用
  步骤：_helper.js 破遮罩 → 点「个护家清」→ 填关键词 → 点「搜索」→ 解析 innerText
  接口 /api/v3/spu/lib/list 的 Data 是加密串，不可用；但页面会自己解密并渲染，
  所以直接从渲染后的 innerText 解析反而最稳。

用法:
  python c20_feigua_rank.py probe              # 单关键词探路，dump 原始行
  python c20_feigua_rank.py collect            # 全关键词采集，落 raw/
"""
import json, os, re, subprocess, sys, time
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.dirname(os.path.dirname(BASE))
TMP = os.path.join(WORKSPACE, "tmp")
os.makedirs(TMP, exist_ok=True)
RAW = os.path.join(BASE, "raw")
os.makedirs(RAW, exist_ok=True)
WB = "http://127.0.0.1:10086/command"
SESSION = "fg-cleanser-rank"
REQ = os.path.join(TMP, "req_c20.json")
HELPER = os.path.join(BASE, "tmp", "_helper.js")
TODAY = datetime.now().strftime("%Y-%m-%d")

RANK_URL = "https://dy.feigua.cn/app/#/product-rank/index?tab=product"

KEYWORDS = ["洗面奶", "洁面", "氨基酸洗面奶", "洁颜", "洁面乳", "洁面慕斯",
            "洗面奶 控油", "洗面奶 祛痘", "洗面奶 补水", "洗面奶 黑头",
            "洗颜", "男士洁面", "温和洁面", "泡沫洁面", "洗卸合一"]

# 噪音词（只在**标题里没有洁面词**时才算噪音）
# ★ 注意：不能把「卸妆」当噪音 —— 洁面标题里「洗卸合一/卸妆二合一」是正当卖点，
#   直接按词过滤会误杀 6-7 条真洁面商品（实测踩过）。改为「必须含洁面词」正向判定。
NOISE_BY_ABSENCE = True
CLEANSER_WORDS = ["洗面奶", "洁面", "洁颜", "洁面露", "洁面乳", "洁面慕斯", "洗颜", "洗面"]
OTHER_CATE = ["沐浴", "洗发", "沐浴露", "洗发水", "洗手液", "洗洁精", "洗衣液",
              "宠物", "狗狗", "猫粮", "洗碗", "内衣", "地毯", "身体乳", "磨砂膏",
              "牙膏", "漱口", "香皂", "洗全身", "护发"]
# ★ 洗脸巾/洁面巾是「巾」不是洁面产品，但标题里带「洁面」会被正向判定放过 ——
#   实测池子里混进了德佑/尔木萄/云柔巾等 3 条洗脸巾，必须单独排除。
TOWEL_CATE = ["洗脸巾", "洁面巾", "柔巾", "绵柔巾", "洗面巾", "擦脸巾", "云柔巾", "美容巾"]
# ★ 卸妆油/卸妆膏/卸妆水是独立品类，不是洁面。
#   但「洗卸合一 / 卸妆去黑头」是洁面的正当卖点，不能按「卸妆」二字一刀切
#   —— 只排除明确以卸妆为主品类的词（实测误放过了 éLL卸妆油、至本卸妆膏、逐本卸妆油）
REMOVER_CATE = ["卸妆油", "卸妆膏", "卸妆水", "卸妆乳", "卸妆液", "卸妆啫喱", "卸妆霜", "卸妆泥"]


def is_noise(title):
    """先排「巾类 / 卸妆品」误命中；再看标题里既没有洁面词、又带别的品类词 → 噪音"""
    t = title or ""
    if any(w in t for w in TOWEL_CATE):
        return True
    if any(w in t for w in REMOVER_CATE):
        return True
    has_cleanser = any(w in t for w in CLEANSER_WORDS)
    if has_cleanser:
        return False
    return any(w in t for w in OTHER_CATE)


def wb(action, args=None, wait=0, timeout=120):
    with open(REQ, "w", encoding="utf-8") as f:
        json.dump({"action": action, "args": args or {}, "session": SESSION}, f, ensure_ascii=False)
    try:
        r = subprocess.run(["curl.exe", "-s", "--noproxy", "*", "-X", "POST", WB,
                            "-H", "Content-Type: application/json", "--data-binary", "@" + REQ],
                           capture_output=True, text=True, encoding="utf-8", timeout=timeout)
        return json.loads(r.stdout)
    except Exception as e:
        return {"ok": False, "err": str(e)}
    finally:
        if wait:
            time.sleep(wait)


def ev(code, wait=0):
    r = wb("evaluate", {"code": code}, wait=wait)
    if not r.get("ok"):
        return None
    try:
        return json.loads(r["data"]["value"])
    except Exception:
        return r["data"].get("value")


def body_text():
    t = ev("document.body.innerText")
    return t if isinstance(t, str) else ""


def js_helper():
    with open(HELPER, encoding="utf-8") as f:
        return f.read()


def open_rank():
    wb("navigate", {"url": RANK_URL}, wait=9)
    time.sleep(4)
    ev(js_helper())
    ev("window.__killMask()")
    return body_text()


CLICK_SEARCH = """(function(){
  var bs=[].slice.call(document.querySelectorAll('button')).filter(function(b){
    var r=b.getBoundingClientRect();
    return (b.innerText||'').trim()==='搜索' && r.y>300 && r.width>0;});
  if(!bs.length) return 'no-btn';
  return window.__clickEl(bs[bs.length-1]);
})()"""


def search(kw):
    """类目 + 关键词搜索，返回渲染后的 innerText"""
    ev("window.__killMask()")
    r1 = ev("window.__clickText('个护家清')")
    time.sleep(2.5)
    ev("window.__killMask()")
    r2 = ev("window.__fillInput(%s,'请输入商品关键词搜索')" % json.dumps(kw, ensure_ascii=False))
    time.sleep(2)
    r3 = ev(CLICK_SEARCH)
    time.sleep(10)
    ev("window.__killMask()")
    # 等列表渲染
    for i in range(12):
        t = body_text()
        if "近30天销售趋势" in t or "上架时间" in t:
            break
        time.sleep(2.5)
    return body_text(), (r1, r2, r3)


NUM = r"[0-9]+(?:\.[0-9]+)?w?\+?(?:\s*-\s*[0-9]+(?:\.[0-9]+)?w?)?"
GID_RE = re.compile(r"gid=([A-Za-z0-9]{20,})")


def parse_seg(txt):
    """解析商品榜 innerText → 行记录"""
    cut = txt.find("近30天销售趋势")
    if cut < 0:
        cut = txt.find("上架时间")
    if cut < 0:
        return []
    seg = txt[cut + 6:]
    lines = [x.strip() for x in seg.split("\n")]
    lines = [x for x in lines if x]
    rows, i = [], 0
    while i < len(lines):
        L = lines[i]
        if re.fullmatch(r"\d{1,3}", L):
            title = lines[i + 1] if i + 1 < len(lines) else ""
            if not title or re.fullmatch(r"\d{1,3}", title):
                i += 1
                continue
            tail, j = [], i + 2
            while j < len(lines) and len(tail) < 12:
                if re.fullmatch(r"\d{1,3}", lines[j]) and j + 1 < len(lines) and len(lines[j + 1]) > 8:
                    break
                tail.append(lines[j]); j += 1
            rows.append({"rank": int(L), "title": title, "tail": tail})
            i = j
            continue
        i += 1
    return rows


# 商品榜表头实测（c20b 探测）：
#   商品 | 销售额 | 销量 | 带货视频 | 带货直播 | 带货达人 | 上架时间 | 近30天销售趋势
# 行为：
#   序号 标题 | 价格 | [佣金率 x%] [好评率 x%] | 销售额档 | 销量档 | 带货视频 | 带货直播 | 带货达人 | [上架时间]
TAIL_KEYS = ["videoCount", "liveCount", "talentCount"]


def parse_fields(tail):
    """tail 形如 ['价格','佣金率 5%','好评率 94.00%','100w+','2.5w-5w','34.8w','71','10','46']
    → 销售额档 / 销量档 / 带货视频 / 带货直播 / 带货达人 / 好评率 / 佣金率"""
    out = {"goodRate": "", "commission": "", "salesTier": "", "salesVolumeTier": "",
           "videoCount": "", "liveCount": "", "talentCount": "", "listedAt": ""}
    joined = " ".join(tail)
    m = re.search(r"好评率\s*([\d.]+)%", joined)
    if m:
        out["goodRate"] = m.group(1) + "%"
    m = re.search(r"佣金率\s*([\d.]+)%", joined)
    if m:
        out["commission"] = m.group(1) + "%"
    out["listedAt"] = next((x for x in tail if re.fullmatch(r"\d{4}/\d{1,2}/\d{1,2}", x)), "")
    # 去掉「价格 / 佣金率 x% / 好评率 x% / 上架时间」这些非指标项
    nums = [x for x in tail
            if not x.startswith("价格") and not x.startswith("佣金率")
            and not x.startswith("好评率") and not re.fullmatch(r"\d{4}/\d{1,2}/\d{1,2}", x)]
    if nums:
        out["salesTier"] = nums[0]
    if len(nums) > 1:
        out["salesVolumeTier"] = nums[1]
    for k, v in zip(TAIL_KEYS, nums[2:]):
        out[k] = v
    return out


def parse_total(txt):
    m = re.search(r"共\s*([\d,]+)\s*条", txt)
    return int(m.group(1).replace(",", "")) if m else None


def click_page(p):
    """点分页器上的页码"""
    js = """(function(){
      var li=[].slice.call(document.querySelectorAll('.el-pager li,.el-pagination li,li.number'))
        .filter(function(x){return (x.innerText||'').trim()==='%d' && x.getBoundingClientRect().width>0;});
      if(!li.length) return 'nf';
      return window.__clickEl(li[li.length-1]);
    })()""" % p
    return ev(js)


def goto_page(p):
    r = click_page(p)
    time.sleep(8)
    ev("window.__killMask()")
    for i in range(8):
        t = body_text()
        if "近30天销售趋势" in t:
            return t
        time.sleep(2)
    return body_text()


def probe():
    """单关键词探路，dump 原始行与字段映射"""
    t = open_rank()
    print("初始 len:", len(t), flush=True)
    t2, acts = search("洗面奶")
    print("搜索后 len:", len(t2), flush=True)
    print("动作:", acts, flush=True)
    print("共 N 条:", parse_total(t2), flush=True)
    rows = parse_seg(t2)
    print("\n解析行数:", len(rows), flush=True)
    for r in rows[:5]:
        f = parse_fields(r["tail"])
        print(f"  {r['rank']:>3} | {r['title'][:55]}", flush=True)
        print(f"       → {json.dumps(f, ensure_ascii=False)}", flush=True)
    open(os.path.join(TMP, "c20_probe_body.txt"), "w", encoding="utf-8").write(t2)
    print("\n原始体已存 tmp/c20_probe_body.txt", flush=True)


def collect():
    """多关键词 × 多页，汇总去重"""
    open_rank()
    all_rows, by_title = [], {}
    for i, kw in enumerate(KEYWORDS, 1):
        print(f"\n[{i}/{len(KEYWORDS)}] 搜「{kw}」", flush=True)
        t, acts = search(kw)
        total = parse_total(t)
        rows = parse_seg(t)
        print(f"  {acts[0] if acts else ''} | 共 {total} 条 / 本页解析 {len(rows)} 行", flush=True)
        page = 1
        while True:
            for r in rows:
                f = parse_fields(r["tail"])
                rec = {"title": r["title"], "brand": guess_brand(r["title"]),
                       "rank": r["rank"], "keyword": kw, "fetchDate": TODAY,
                       "isNoise": is_noise(r["title"]), **f}
                key = re.sub(r"[【】\[\]（）()「」\s]", "", r["title"])[:40]
                if key not in by_title:
                    by_title[key] = rec
                    all_rows.append(rec)
            if total and page * 10 >= total:
                break
            if page >= 5:
                break
            page += 1
            t = goto_page(page)
            rows2 = parse_seg(t)
            if not rows2:
                break
            rows = rows2
        print(f"  累计 {len(all_rows)} 条", flush=True)

    fp = os.path.join(RAW, f"feigua_goods_洁面_{TODAY.replace('-','')}.json")
    json.dump({"fetchedAt": TODAY, "keywords": KEYWORDS, "count": len(all_rows),
               "category": {"L1": "个护家清", "L2": "面部护理", "L3": "洁面"},
               "period": "近30天", "goods": all_rows},
              open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n[collect done] {fp}（{len(all_rows)} 条，剔除噪音 {sum(1 for x in all_rows if x['isNoise'])} 条）", flush=True)
    return all_rows


# 从标题里猜品牌（常见洁面品牌词典）
BRANDS = ["BUV", "RNW", "eiio", "奕沃", "自然堂", "C咖", "CEMOY", "澳诗茉", "韩束", "海洋至尊",
          "芙丽芳丝", "珂润", "适乐肤", "丝塔芙", "理肤泉", "CeraVe", "旁氏", "曼秀雷敦", "妮维雅",
          "欧莱雅", "玉兰油", "OLAY", "珀莱雅", "谷雨", "溪木源", "至本", "半亩花田", "悦芙媞",
          "德妃", "果本", "温碧泉", "百雀羚", "相宜本草", "御泥坊", "丸美", "韩后", "一叶子",
          "珂拉琪", "完美日记", "花西子", "植物医生", "WIS", "片仔癀", "白云山", "修正", "仁和",
          "京润珍珠", "满婷", "满婷", "郁美净", "大宝", "隆力奇", "小迷糊", "润百颜", "夸迪",
          "米蓓尔", "可复美", "可丽金", "颐莲", "优时颜", "HBN", "逐本", "观夏", "气味图书馆",
          # 2026-09-28 洁面池实测补充
          "éLL", "海龟爸爸", "红卫", "橘后", "草安堂", "安修泽", "毕生之研", "三式",
          "THE WHOO", "后", "肌肤未来", "AOEO", "植然方适", "雪玲妃", "阿芙", "透真",
          "高姿", "韩熹", "朵拉朵尚", "玛莉安", "采词", "倩碧", "SK-II", "雅诗兰黛", "兰蔻"]


def guess_brand(title):
    """从标题猜品牌：先查词典；再剥掉促销前缀后取首个英文/中文词块"""
    for b in BRANDS:
        if b in title:
            return b
    t = title
    # 一层层剥掉【xx】/【xx xx】促销前缀
    for _ in range(3):
        t2 = re.sub(r"^[【\[][^】\]]{0,16}[】\]]\s*", "", t).strip()
        if t2 == t:
            break
        t = t2
    # 英文/数字品牌（含带音标的如 éLL）
    m = re.match(r"^([A-Za-zÀ-ÿ][A-Za-z0-9À-ÿ\.\-]{1,14})(?![a-z])", t)
    if m:
        return m.group(1)
    # 中文品牌：取到第一个非品牌后缀词之前
    STOP = ("洗面奶", "洁面", "洁颜", "洗颜", "洗面", "男士", "女士", "官方", "正品",
            "三合一", "二合一", "控油", "保湿", "深层", "舒缓", "温和", "氨基酸")
    m = re.match(r"^([\u4e00-\u9fa5A-Za-z0-9]{2,10})", t)
    if m:
        cand = m.group(1)
        for s in STOP:
            i = cand.find(s)
            if i > 0:
                cand = cand[:i]
        if 2 <= len(cand) <= 8:
            return cand
    return "—"


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "probe"
    if mode == "probe":
        probe()
    elif mode == "collect":
        collect()
