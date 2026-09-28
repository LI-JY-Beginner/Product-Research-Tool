# -*- coding: utf-8 -*-
"""
xcommon.py — 小红书评论采集工具包 · 公共基座

所有脚本都从这里拿三样东西：
  1) CFG   ：读好的配置（config/<类目>.yaml）
  2) wb()  ：调用 Kimi WebBridge 的 HTTP 客户端
  3) 一堆文本工具（标题清洗 / 评论解析 / 时间归一）

配置读取优先级：
  命令行 --config <路径>  >  环境变量 XHS_CONFIG  >  config/<类目>.yaml  >  config/cleanser.yaml

任何脚本都可以被单独运行（`python 10_collect_links.py --cat cleanser`），
也可以被 run_all.py 串起来跑。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

# ---------------------------------------------------------------- 路径

HERE = os.path.dirname(os.path.abspath(__file__))          # .../xhs-scraper/scripts
PKG = os.path.dirname(HERE)                                # .../xhs-scraper
CONFIG_DIR = os.path.join(PKG, "config")
DEFAULT_CAT = "cleanser"

WB_URL = "http://127.0.0.1:10086/command"
WB_STATUS = "http://127.0.0.1:10086/status"


# ---------------------------------------------------------------- 配置

class Cfg(dict):
    """带点号取值的配置对象：CFG.step.links.roles → dict"""

    def __getattr__(self, k):
        try:
            v = self[k]
        except KeyError:
            raise AttributeError(k)
        return Cfg(v) if isinstance(v, dict) else v

    def getpath(self, dotted, default=None):
        cur = self
        for part in dotted.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur


def _find_config(cat=None, explicit=None):
    if explicit:
        return explicit if os.path.isabs(explicit) else os.path.join(os.getcwd(), explicit)
    env = os.environ.get("XHS_CONFIG")
    if env:
        return env
    name = (cat or DEFAULT_CAT) + ".yaml"
    return os.path.join(CONFIG_DIR, name)


def load_cfg(explicit=None, cat=None):
    """读入配置并补齐派生字段（路径、日期、SESSION 名）"""
    from datetime import datetime

    path = _find_config(cat=cat, explicit=explicit)
    if not os.path.exists(path):
        avail = [f for f in os.listdir(CONFIG_DIR) if f.endswith(".yaml")] if os.path.isdir(CONFIG_DIR) else []
        raise SystemExit(f"[配置错误] 找不到配置文件：{path}\n"
                         f"           config/ 下现有：{avail}\n"
                         f"           用法：--cat <名称>  或  --config <路径>")
    try:
        import yaml
    except ImportError:
        raise SystemExit("[依赖缺失] 需要 pyyaml。安装：python -m pip install --only-binary=:all: pyyaml")
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    c = Cfg(raw)
    today = datetime.now().strftime("%Y-%m-%d")
    stamp = today.replace("-", "")
    c["_config_path"] = path
    c["_cat_key"] = os.path.splitext(os.path.basename(path))[0]
    c["_today"] = today
    c["_stamp"] = stamp
    c["_session"] = c.get("project", {}).get("session") or f"xhs-{c['_cat_key']}"

    outdir = c.get("project", {}).get("outputDir")
    if not outdir:
        raise SystemExit(f"[配置错误] {path} 缺少 project.outputDir（产出目录）")
    outdir = os.path.expanduser(str(outdir))
    # ★ 相对路径一律相对「工具包根目录」解析，不跟着调用时的 cwd 跑，
    #   否则单步跑（python scripts/xx.py）时产出会落到别的地方去。
    if not os.path.isabs(outdir):
        outdir = os.path.normpath(os.path.join(PKG, outdir))
    c["_out"] = outdir
    c["_raw"] = os.path.join(outdir, "raw")
    c["_data"] = os.path.join(outdir, "data")
    c["_notes"] = os.path.join(outdir, "raw", "xhs_output")
    c["_tmp"] = os.path.join(outdir, "tmp")
    for d in (c["_out"], c["_raw"], c["_data"], c["_notes"], c["_tmp"]):
        os.makedirs(d, exist_ok=True)
    return c


def cli(desc="小红书评论采集工具包"):
    """统一命令行：--cat / --config / --limit / 位置参数透传"""
    ap = argparse.ArgumentParser(description=desc)
    ap.add_argument("--cat", default=None, help="类目配置名（config/<名>.yaml），默认 " + DEFAULT_CAT)
    ap.add_argument("--config", default=None, help="直接指定配置文件路径（优先级最高）")
    ap.add_argument("--limit", type=int, default=None, help="本次最多处理多少条")
    known, rest = ap.parse_known_args()
    return known, rest


# ---------------------------------------------------------------- WebBridge

class WB:
    """Kimi WebBridge 客户端。用 curl.exe 发请求（本机环境实测最稳）。

    注意：本机系统代理会劫持 127.0.0.1，所以调用前必须把代理环境变量清掉，
    这一动作由 run_all.py / 看门狗统一负责，脚本内不再重复处理。
    """

    def __init__(self, session, tmpdir):
        self.session = session
        self.req = os.path.join(tmpdir, "req.json")

    def __call__(self, action, args=None, wait=0, timeout=90):
        payload = {"action": action, "args": args or {}, "session": self.session}
        with open(self.req, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        try:
            r = subprocess.run(["curl.exe", "-s", "-X", "POST", WB_URL,
                                "-H", "Content-Type: application/json",
                                "--data-binary", "@" + self.req],
                               capture_output=True, text=True, encoding="utf-8", timeout=timeout)
            return json.loads(r.stdout)
        except Exception as e:
            return {"ok": False, "err": str(e)}
        finally:
            if wait:
                time.sleep(wait)

    def eval_json(self, code, wait=0, timeout=90):
        """跑一段 JS，返回解析后的对象；失败返回 None"""
        r = self("evaluate", {"code": code}, wait=wait, timeout=timeout)
        if not r.get("ok"):
            return None
        raw = (r.get("data") or {}).get("value", "")
        if isinstance(raw, (dict, list)):
            return raw
        try:
            return json.loads(raw)
        except Exception:
            return None

    def eval_text(self, code="document.body.innerText"):
        r = self("evaluate", {"code": code})
        if not r.get("ok"):
            return ""
        v = (r.get("data") or {}).get("value", "")
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return v
        return str(v)


def wb_alive():
    """守护进程活着吗（不含扩展连接判定）"""
    import urllib.request
    urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))
    try:
        d = json.loads(urllib.request.urlopen(WB_STATUS, timeout=4).read().decode())
        return bool(d.get("running")), bool(d.get("extension_connected"))
    except Exception:
        return False, False


# ---------------------------------------------------------------- 登录态

LOGIN_BAD = ["重新登录", "登录超限", "已退出登录", "超出登录设备上限", "扫码登录", "手机号登录", "请登录", "登录已失效"]


def login_ok(text, window=600):
    """页面文本判定登录态。注意：document.cookie 看不到 httpOnly 的 web_session，
    真·判定请配合 cdp Network.getCookies，见 00_preflight.py。"""
    head = (text or "")[:window]
    for b in LOGIN_BAD:
        if b in head:
            return False, b
    return True, ""


# ---------------------------------------------------------------- 文本工具

TIME_LINE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}[\u4e00-\u9fa5]{0,8}|\d+分钟前|\d+小时前|\d+天前"
    r"|\d+月\d+日|昨天|前天|刚刚|编辑于[^\n]{0,12})$")

TITLE_TIME_PAT = re.compile(
    r"^(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}|\d+分钟前|\d+小时前|\d+天前|\d+月\d+日|昨天|刚刚)$")

# ★ 小红书搜索结果里的笔记链接是 /search_result/<nid>，
#   不是 /explore/<nid>。正则漏了 search_result 会导致候选全军覆没且不报错。
NOTE_URL_RE = re.compile(r"(?:search_result|explore|discovery/item)/([0-9a-f]{16,32})")
TOKEN_RE = re.compile(r"xsec_token=([^&]+)")


def norm(t):
    return re.sub(r"\s+", " ", (t or "")).strip()


def clean_title(raw, hit_re, noise=()):
    """从搜索结果卡片的整块文本里剥出标题。

    卡片文本形如「标题\\n作者昵称\\n3 天前\\n1.2万」，
    作者昵称通常很短，所以取去掉时间行后最长的一段。返回 None 表示这条不合格。
    """
    parts = [p.strip() for p in (raw or "").split("\n") if p.strip()]
    keep = [p for p in parts if not TITLE_TIME_PAT.match(p)]
    if not keep:
        return None
    t = max(keep, key=len)
    if len(t) < 6:                       # 过短 = 作者昵称，不是标题
        return None
    if hit_re and not hit_re.search(t):
        return None
    if any(n in t for n in noise):
        return None
    return t


def parse_comment_block(block):
    """把一条评论块的 innerText 拆成 {nickname, content, time}。

    结构：昵称\\n正文（可能多行）\\n时间行\\n[点赞数][回复]
    """
    lines = [l.strip() for l in (block or "").split("\n") if l.strip()]
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
    content = norm(content)
    if len(content) < 3:
        return None
    return {"nickname": nick, "content": content[:300], "time": t}


def note_id_from_url(url):
    m = NOTE_URL_RE.search(url or "")
    return m.group(1) if m else ""


def token_from_url(url):
    m = TOKEN_RE.search(url or "")
    return m.group(1) if m else ""


def is_author_profile(url):
    """搜索结果里混着作者主页链接，必须丢掉"""
    return "/user/profile/" in (url or "")


def build_note_url(nid, token, source="pc_search"):
    """统一走 /explore/ 打开笔记（带 xsec_token），实测比 /search_result/ 稳"""
    return f"https://www.xiaohongshu.com/explore/{nid}?xsec_token={token}&xsec_source={source}"


def jdump(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def jload(path, default=None):
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def log(*a):
    print(*a, flush=True)
