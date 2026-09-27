# -*- coding: utf-8 -*-
"""
pcommon.py — 产品调研模块公共基座

统一处理 5 个已知的 WebBridge 坑：
  坑1 daemon 单独 start 会被回收  → 由 run_pipeline_product.py 的看门狗负责
  坑2 系统代理把 127.0.0.1 也代理掉 → 引入本模块即清代理
  坑3 Windows 必须 curl.exe + --data-binary → wb() 统一封装
  坑4 采空会覆写 raw              → save_raw() 写前备份 + 条目数校验
  坑5 飞瓜登录态过期              → check_login()
"""
import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../产品调研模块
WORKSPACE = os.path.dirname(BASE)                                     # .../_交接包
TMP = os.path.join(BASE, "tmp")
RAW = os.path.join(BASE, "raw")
DATA = os.path.join(BASE, "data")
CHECK = os.path.join(BASE, "_check")
for _d in (TMP, RAW, DATA, CHECK):
    os.makedirs(_d, exist_ok=True)

WB = "http://127.0.0.1:10086/command"
WB_STATUS = "http://127.0.0.1:10086/status"
SESSION = "feigua-product-research"
REQ_FILE = os.path.join(TMP, "wbq_product.json")   # 复用同一文件，避免频繁建删触发安全删除
TODAY = datetime.now().strftime("%Y-%m-%d")

# ---- 坑2：清代理（本进程内） ----
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
    os.environ.pop(_k, None)

FEIGUA = "https://dy.feigua.cn/app/#/goods-detail/index?id=&gid={gid}&tab={tab}"

# ======================= 品类命名空间（多类目复用同一套脚本） =======================
# 不设 PCATE  → 眼部护理（沿用历史文件名：cards.json / top30.json ...）
# PCATE=face → 面部护理（自动落 cards_face.json / top30_face.json ...）
CATE_NS = (os.environ.get("PCATE") or "").strip()


def dname(name):
    """数据文件名按当前品类命名空间映射：cards.json -> cards_face.json"""
    if not CATE_NS:
        return name
    stem, ext = os.path.splitext(name)
    return "%s_%s%s" % (stem, CATE_NS, ext)


def dpath(name):
    return os.path.join(DATA, dname(name))


# ============================ WebBridge 通道 ============================
def wb(action, args=None, wait=0, timeout=90):
    """调用 WebBridge。坑3：必须 curl.exe + --data-binary @文件"""
    payload = {"action": action, "args": args or {}, "session": SESSION}
    with open(REQ_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    try:
        r = subprocess.run(
            ["curl.exe", "-s", "--noproxy", "*", "-X", "POST", WB,
             "-H", "Content-Type: application/json", "--data-binary", "@" + REQ_FILE],
            capture_output=True, text=True, encoding="utf-8", timeout=timeout)
        out = json.loads(r.stdout)
    except Exception as e:
        return {"ok": False, "err": str(e)}
    if wait:
        time.sleep(wait)
    return out


def wb_ok(action, args=None, wait=0):
    r = wb(action, args, wait)
    return r if r.get("ok") else None


def status():
    import urllib.request
    urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))
    try:
        return json.loads(urllib.request.urlopen(WB_STATUS, timeout=5).read().decode())
    except Exception:
        return {}


def wait_ready(max_sec=40):
    """等 daemon + 扩展都就绪"""
    t0 = time.time()
    while time.time() - t0 < max_sec:
        s = status()
        if s.get("running") and s.get("extension_connected"):
            return True
        time.sleep(2)
    return False


def ev(code, wait=0):
    """执行 JS，返回字符串结果（None 表示失败）"""
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


def snap():
    r = wb("snapshot", {})
    return r.get("data") if r.get("ok") else None


def click_ref(ref):
    """坑：用 WebBridge 原生 click（派发完整事件序列），而不是 evaluate 里的 el.click()。
    这是历史「点了 tab 不渲染」的高概率根因 —— Vue 监听 pointerdown/mousedown，合成 click 不响应。"""
    return wb("click", {"selector": ref})


def click_text(text, exact=False):
    """兜底：按可见文本点击（仍走真实 DOM click，返回是否找到）"""
    esc = text.replace("'", "\\'")
    code = ("(() => { var els=[...document.querySelectorAll('div,span,a,li,button')]"
            ".filter(function(e){var t=(e.innerText||'').trim();"
            "return %s t.indexOf('%s')===0 && t.length<24 && e.children.length<=3;});"
            "if(!els.length) return 'nf'; var e=els[els.length-1];"
            "['pointerdown','mousedown','pointerup','mouseup','click'].forEach(function(t){"
            "e.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window}));});"
            "return 'ok:'+e.innerText.trim(); })()" % ("t==='%s' &&" % esc if exact else "", esc))
    return ev(code)


def drag_click(x, y):
    """最兜底：CDP 真实鼠标点击（isTrusted=true）"""
    for m, p in (("mousePressed", {"x": x, "y": y, "button": "left", "clickCount": 1}),
                 ("mouseReleased", {"x": x, "y": y, "button": "left", "clickCount": 1})):
        wb("cdp", {"method": "Input.dispatchMouseEvent",
                   "params": dict(p, type=m, buttons=1)}, timeout=30)


def poll_until(js_cond, tries=12, gap=2.0, label=""):
    """轮询等待（替代固定 sleep 5s —— 列表可能 5-15s 才回）"""
    for i in range(tries):
        v = ev(js_cond)
        if v:
            return True
        time.sleep(gap)
    if label:
        print(f"    [poll] {label} 超时（{tries}x{gap}s）", flush=True)
    return False


# ============================ 安全落盘（坑4） ============================
def _bak_dir():
    d = os.path.join(RAW, "_bak_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    os.makedirs(d, exist_ok=True)
    return d


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def count_of(obj, list_path=None):
    """取条目数，用于落盘前的防呆校验"""
    if obj is None:
        return 0
    if isinstance(obj, list):
        return len(obj)
    for k in ("items", "videos", "details", "goods", "skus", "reviews", "count"):
        if k in obj and isinstance(obj[k], (list, int)):
            return len(obj[k]) if isinstance(obj[k], list) else obj[k]
    return len(obj)


def save_raw(basename, payload, min_ratio=0.8, min_abs=1):
    """坑4：写 raw 前先备份；若新结果明显少于旧结果 → 拒写并改存 _reject_，报警。
    返回 True 表示已写入正式文件。"""
    path = os.path.join(RAW, basename)
    old = load_json(path)
    old_n = count_of(old)
    new_n = count_of(payload)
    if new_n < min_abs or (old_n and new_n < old_n * min_ratio):
        rej = os.path.join(RAW, "_reject_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
        os.makedirs(rej, exist_ok=True)
        with open(os.path.join(rej, basename), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        print(f"    !! 拒写 {basename}：新 {new_n} 条 < 旧 {old_n} 条（已转存 {os.path.basename(rej)}/）", flush=True)
        return False
    if old is not None:
        shutil.copy2(path, os.path.join(_bak_dir(), basename))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    return True


# ============================ 登录态（坑5） ============================
def check_login():
    """用 cdp Network.getCookies 判飞瓜登录态（不用 document.cookie —— 有 httpOnly）。
    ⚠️ 实测有效 cookie 名是 `FEIGUADY2`（.feigua.cn，httpOnly）；
       早期版本猜的 customerId/feigua_token/sessionid 全部不存在 → 会误报 expired。"""
    r = wb("cdp", {"method": "Network.getCookies", "params": {"urls": ["https://dy.feigua.cn"]}}, timeout=30)
    if not r.get("ok"):
        return "unknown"
    try:
        cookies = r["data"]["result"]["cookies"] if "result" in r["data"] else r["data"]["cookies"]
        names = {c.get("name", "") for c in cookies}
        vals = {c.get("name", ""): (c.get("value") or "") for c in cookies}
        if vals.get("FEIGUADY2"):
            return "normal"
        # 次选：任何一眼能认的登录标识
        if names & {"customerId", "feigua_token", "sessionid", "Authorization", "FEIGUA"}:
            return "normal"
        return "expired"
    except Exception:
        return "unknown"


# ============================ 文本解析小工具 ============================
def num(s):
    """'100w+' -> 1000000 ; '2.5w-5w' -> 25000-50000 ; '12.3%' -> 12.3"""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip().replace(",", "").replace("¥", "").replace("￥", "")
    m = re.match(r"^([\d.]+)\s*w\+?$", s, re.I)
    if m:
        return float(m.group(1)) * 10000
    m = re.match(r"^([\d.]+)\s*[万w]$", s, re.I)
    if m:
        return float(m.group(1)) * 10000
    try:
        return float(re.sub(r"[^\d.]", "", s) or 0)
    except Exception:
        return None


def tier_mid(tier):
    """销售额档位 -> 中位数（用于排序）。
    '100w+' -> 1,000,000 ; '10w-25w' -> 175,000 ; '50w-100w' -> 750,000"""
    if not tier:
        return 0
    s = str(tier).strip().lower().replace(",", "")
    m = re.match(r"^([\d.]+)\s*[w万]\s*\+$", s)
    if m:
        return float(m.group(1)) * 10000
    # ★ 混合单位坑：'5000-1w' 左端没单位=5000，右端 1w=10000，不能统一 ×10000
    m = re.match(r"^([\d.]+)\s*([w万]?)\s*[-~]\s*([\d.]+)\s*([w万]?)$", s)
    if m:
        a = float(m.group(1)) * (10000 if m.group(2) else 1)
        b = float(m.group(3)) * (10000 if m.group(4) else 1)
        return (a + b) / 2
    m = re.match(r"^([\d.]+)\s*[w万]$", s)
    if m:
        return float(m.group(1)) * 10000
    return num(s) or 0


def norm_title(t):
    """标题核心词归一：去品牌词、促销词、括号、符号，用于同品去重"""
    if not t:
        return ""
    t = re.sub(r"[【】\[\]（）()「」\"'’\s]", "", str(t))
    t = re.sub(r"(官方正品|旗舰店|正品|同款|直播专享|限时|拍一发[二三四]|买一送[一二三]|"
               r"下单立减|福利款|抖音同款|达人推荐|新款|升级版)", "", t)
    return t


def jaccard(a, b):
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)

# ============================ 接口层取数（★B1 探测的核心结论） ============================
# 「带货视频」列表行的 DOM 经常不渲染，但接口早就返回了完整 JSON。
# 与其等 DOM，不如：① 在页面注入 fetch/XHR 拦截器看真实请求；② 直接在页面内重放接口拿 JSON。
HOOK_JS = r"""
(function(){
  if(window.__hooked) return 'already';
  window.__hooked = true;
  window.__cap = [];
  function rec(o){ try{ window.__cap.push(o); if(window.__cap.length>300) window.__cap.shift(); }catch(e){} }
  var _f = window.fetch;
  window.fetch = function(){
    var a=arguments, u=(typeof a[0]==='string')?a[0]:((a[0]&&a[0].url)||'');
    var opt=a[1]||{}, rb=opt.body?String(opt.body).slice(0,3000):'';
    var st=Date.now();
    return _f.apply(this,a).then(function(r){
      try{ r.clone().text().then(function(tx){ rec({t:'fetch',url:u,method:opt.method||'GET',reqBody:rb,
        status:r.status,ms:Date.now()-st,len:(tx||'').length,body:(tx||'').slice(0,60000)}); })['catch'](function(){}); }catch(e){}
      return r;
    });
  };
  var _o=XMLHttpRequest.prototype.open, _s=XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open=function(m,u){ this.__u=u; this.__m=m; return _o.apply(this,arguments); };
  XMLHttpRequest.prototype.send=function(d){
    var self=this, st=Date.now(), rb=d?String(d).slice(0,3000):'';
    this.addEventListener('load', function(){
      var tx=''; try{ tx=(typeof self.responseText==='string')?self.responseText:''; }catch(e){}
      rec({t:'xhr',url:self.__u,method:self.__m,reqBody:rb,status:self.status,ms:Date.now()-st,
           len:tx.length,body:tx.slice(0,60000)});
    });
    return _s.apply(this,arguments);
  };
  return 'hooked';
})()
"""

REPLAY_AWEME_JS = r"""
(async function(P){
  var r=await fetch('/api/v3/goods/aweme/loadAwemeAnalysis?_='+Date.now()+Math.floor(Math.random()*999),
    {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(P.body)});
  var j=await r.json(), D=j.Data||{};
  var items=(D.Items||[]).map(function(x){
    var a=x.BaseAwemeDto||{}, b=x.BaseBloggerDto||{};
    return {
      awemeId:a.AwemeId,
      shareUrl:a.AwemeShareUrl,          // ★ 抖音原视频链接
      detailUrl:a.AwemeDetailUrl,        // 飞瓜视频详情（带 ts/sign）
      cover:a.AwemeCoverUrl,
      desc:a.AwemeDesc,                  // ★ 口播/标题文案
      duration:a.DurationStr,
      pubTime:a.AwemePubTime,
      gmv:x.AwemeSaleGmvStr, volume:x.AwemeSaleCountStr,
      like:x.LikeCountStr, comment:x.CommentCountStr, share:x.ShareCountStr,
      play:x.PlayCountStr, collect:x.CollectCountStr,
      interaction:x.InteractionCountStr, interactionRate:x.InteractionRateStr, gpm:x.GPM,
      blogger:b.BloggerName, displayId:b.DisplayId, fans:b.Fans, fansNum:b.FansNum,
      bloggerType:b.AccoutCertText, tag:b.Tag, province:b.ProvinceName,
      douyinHome:b.DouyinHomePageUrl, avatar:b.BloggerAvatar
    };
  });
  return JSON.stringify({status:r.status, code:j.Code, msg:j.Msg, total:D.Total, n:items.length, items:items});
})(__P__)
"""


def install_hook():
    """注入 fetch/XHR 拦截器（必须在触发目标交互之前调用）"""
    return ev(HOOK_JS)


def cap(kw=None):
    """取捕获到的请求；kw 用于按 URL 关键字过滤"""
    raw = ev("JSON.stringify(window.__cap||[])")
    try:
        items = json.loads(raw) if isinstance(raw, str) else (raw or [])
    except Exception:
        items = []
    if kw:
        items = [x for x in items if kw in (x.get("url") or "")]
    return items


def cap_json(kw):
    """取命中的第一个请求并解析其 JSON 响应"""
    for it in cap(kw):
        try:
            return json.loads(it["body"])
        except Exception:
            continue
    return None


def _dcode(offset_days):
    return (datetime.now() - timedelta(days=offset_days)).strftime("%Y%m%d")


def aweme_list(gid, page=1, size=10, sort_field="AwemeSaleGmvStr", order=1,
               from_date=None, to_date=None, keyword="", period=10000):
    """★ 直接在页面内重放「带货视频」列表接口。
    前提：当前标签页已在 dy.feigua.cn 域名下（同源，自动带 cookie）。
    sort_field: AwemeSaleGmvStr(销售额) / AwemeSaleCountStr(销量) / LikeCountStr ...
    order: 1=降序, 0=升序
    返回 dict(items, total, n, status) —— DOM 渲染与否完全不影响取数。"""
    body = {"gid": gid, "sortField": sort_field, "order": order, "keyword": keyword,
            "fromDateCode": from_date or _dcode(29), "toDateCode": to_date or _dcode(0),
            "PeriodType": period, "page": page, "pageSize": size, "IsReturnCount": 1}
    code = REPLAY_AWEME_JS.replace("__P__", json.dumps({"body": body}, ensure_ascii=False))
    r = ev(code, wait=0)
    try:
        return json.loads(r) if isinstance(r, str) else r
    except Exception:
        return {"status": -1, "n": 0, "items": [], "raw": str(r)[:400]}


def click_tab_full(label):
    """★攻克「点了 tab 不渲染」：必须派发完整指针事件序列（含 PointerEvent + clientX/Y）。
    历史脚本只用 el.click()（合成事件），Vue 的 pointerdown 监听不响应 —— 这是根因。"""
    code = ("(()=>{var es=[...document.querySelectorAll('[role=tab],[class*=tab-item],[class*=tabItem],div,span,a,li')]"
            ".filter(function(e){return (e.innerText||'').trim()==='__L__' && e.offsetParent!==null && e.children.length<=2;});"
            "if(!es.length)return 'nf';var e=es[0];var r=e.getBoundingClientRect();"
            "var x=Math.round(r.left+r.width/2),y=Math.round(r.top+r.height/2);"
            "var o={bubbles:true,cancelable:true,view:window,clientX:x,clientY:y,screenX:x,screenY:y,"
            "pointerId:1,pointerType:'mouse',isPrimary:true,button:0,buttons:1};"
            "e.dispatchEvent(new PointerEvent('pointerdown',o));e.dispatchEvent(new MouseEvent('mousedown',o));"
            "e.dispatchEvent(new PointerEvent('pointerup',Object.assign({},o,{buttons:0})));"
            "e.dispatchEvent(new MouseEvent('mouseup',Object.assign({},o,{buttons:0})));"
            "e.dispatchEvent(new MouseEvent('click',Object.assign({},o,{buttons:0})));"
            "return 'ok:'+e.innerText.trim()+':'+x+','+y;})()").replace("__L__", label)
    return ev(code)


def click_text_full(label, tries=3, wait=4):
    """点 tab/按钮并轮询等渲染"""
    for i in range(tries):
        r = click_tab_full(label)
        time.sleep(wait)
        if r and str(r).startswith("ok"):
            return r
    return r


def active_tab():
    return ev("(()=>{var a=[...document.querySelectorAll('[role=tab]')].filter(e=>e.getAttribute('aria-selected')==='true');"
              "return a.map(e=>e.innerText.trim()).join('|')})()")

def scroll_all(times=6, gap=2.5):
    """滚动页面与所有内部滚动容器，触发懒加载/虚拟列表渲染"""
    for _ in range(times):
        ev("(()=>{var s=[document.scrollingElement,...document.querySelectorAll('*')]"
           ".filter(e=>e.scrollHeight>e.clientHeight+200);s.forEach(e=>{e.scrollTop=e.scrollHeight;});"
           "window.scrollTo(0,document.body.scrollHeight);return s.length})()")
        time.sleep(gap)

def wait_page(marker, tries=20, gap=4.0, renav=None):
    """等页面内容真正渲染（固定 sleep 不可靠）。marker 可以是字符串或字符串列表。
    renav 给定时，超时会重新 navigate 后再等一轮。"""
    marks = [marker] if isinstance(marker, str) else marker
    def hit():
        t = body_text()
        return t if (t and any(m in t for m in marks)) else None
    for _ in range(tries):
        r = hit()
        if r: return r
        time.sleep(gap)
    if renav:
        print("    [wait_page] 超时，重新导航重试", flush=True)
        wb("navigate", {"url": renav}, wait=8, timeout=120)
        for _ in range(tries):
            r = hit()
            if r: return r
            time.sleep(gap)
    return None


def open_goods(gid, sign, wait_ready=True):
    """打开商品详情（overview），返回渲染后的文本"""
    url = FEIGUA.format(gid=gid, tab="overview") + "&" + sign
    wb("navigate", {"url": url}, wait=6, timeout=120)
    if not wait_ready:
        return body_text()
    return wait_page(["上架时间", "近30天销量"], renav=url)


def ensure_video_tab(max_click=4):
    """切到「带货视频」并等内容渲染（含列表行）。返回 (文本, 状态)"""
    for i in range(max_click):
        click_tab_full("带货视频")
        t = wait_page("视频列表", tries=8, gap=3.0)
        if t:
            t2 = wait_page("时长：", tries=10, gap=3.0)
            return (t2 or t, "rows" if t2 else "list-only")
        print(f"    [ensure_video_tab] 第 {i+1} 次点击未渲染，重试", flush=True)
        time.sleep(4)
    return (None, "fail")

DATE_RE = re.compile(r"^\d{4}/\d{2}/\d{2} \d{2}:\d{2}$")


def parse_video_rows(txt):
    """从「带货视频」列表的 innerText 解析行。
    行结构（相邻行）：
      标题 / 发布时间 / 时长：X / 达人 / 粉丝数：X / 空 / 销售额档 / 空 / 销量档 / 空 / 点赞 / 评论
    """
    if not txt:
        return []
    # 定位到列表表头之后
    head = txt.find("视频/发布时间")
    if head < 0:
        head = txt.find("视频列表")
    sec = txt[head:] if head > 0 else txt
    lines = [l.rstrip() for l in sec.split("\n")]
    idxs = [i for i, l in enumerate(lines) if DATE_RE.match(l.strip())]
    rows = []
    for i in idxs:
        title = lines[i - 1].strip() if i > 0 else ""
        # 向后取非空行序列
        tail = []
        j = i + 1
        while j < len(lines) and len(tail) < 9:
            v = lines[j].strip()
            if v:
                tail.append(v)
            if len(tail) == 8:
                break
            j += 1
            if DATE_RE.match(lines[j].strip()) if j < len(lines) else False:
                break
        d = {"title": title, "publishAt": lines[i].strip()}
        if not tail or not tail[0].startswith("时长"):
            continue
        d["duration"] = tail[0].replace("时长：", "").strip()
        d["author"] = tail[1] if len(tail) > 1 else ""
        d["fans"] = (tail[2] if len(tail) > 2 else "").replace("粉丝数：", "").strip()
        rest = [x for x in tail[3:] if x]
        d["salesTier"] = rest[0] if len(rest) > 0 else ""
        d["salesVolume"] = rest[1] if len(rest) > 1 else ""
        d["like"] = rest[2] if len(rest) > 2 else ""
        d["comment"] = rest[3] if len(rest) > 3 else ""
        d["salesNum"] = tier_mid(d["salesTier"])
        rows.append(d)
    return rows


def parse_wordcloud_v(txt, limit=60):
    """解析「视频内容词云」：序号 / 关键词 / 带货视频数 / 占比"""
    if not txt:
        return []
    i = txt.find("视频内容词云")
    if i < 0:
        return []
    body = txt[i:i + 12000]
    out = []
    for mm in re.finditer(r"(?:^|\n)(\d{1,3})\s*\n\s*([^\n]{1,16}?)\s*\n\s*([\d.,]+)\s*\n\s*([\d.]+)%", body):
        w = mm.group(2).strip()
        if w in ("排序", "关键词", "带货视频", "占比", "排序关键词"):
            continue
        out.append({"rank": int(mm.group(1)), "word": w, "count": mm.group(3), "pct": float(mm.group(4))})
        if len(out) >= limit:
            break
    return out


def click_sort_header(label):
    """点列表表头做排序（如「视频销售额」），返回点击结果"""
    return click_tab_full(label)

