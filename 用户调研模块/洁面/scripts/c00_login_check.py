# -*- coding: utf-8 -*-
"""c00_login_check.py — 检查小红书 / 飞瓜登录态（cdp 取 cookie，不用 document.cookie）"""
import json, os, subprocess, time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.dirname(os.path.dirname(BASE))
TMP = os.path.join(WORKSPACE, "tmp")
os.makedirs(TMP, exist_ok=True)
WB = "http://127.0.0.1:10086/command"
SESSION = "xhs-cleanser-research"
REQ = os.path.join(TMP, "req_c00.json")


def wb(action, args=None, wait=0, session=SESSION):
    with open(REQ, "w", encoding="utf-8") as f:
        json.dump({"action": action, "args": args or {}, "session": session}, f, ensure_ascii=False)
    try:
        r = subprocess.run(["curl.exe", "-s", "-X", "POST", WB, "-H", "Content-Type: application/json",
                            "--data-binary", "@" + REQ], capture_output=True, text=True,
                           encoding="utf-8", timeout=90)
        return json.loads(r.stdout)
    except Exception as e:
        return {"ok": False, "err": str(e)}
    finally:
        if wait:
            time.sleep(wait)


def cookies(url):
    r = wb("cdp", {"method": "Network.getCookies", "params": {"urls": [url]}})
    try:
        return r["data"]["result"]["cookies"]
    except Exception:
        return []


def check_xhs():
    wb("navigate", {"url": "https://www.xiaohongshu.com/explore"}, wait=5)
    cs = cookies("https://www.xiaohongshu.com")
    names = {c["name"]: c["value"] for c in cs}
    has = "web_session" in names or "id_token" in names
    print(f"[小红书] cookie 数量 {len(cs)}｜web_session: {'有' if 'web_session' in names else '无'}｜id_token: {'有' if 'id_token' in names else '无'}", flush=True)
    # 页面层面确认
    r = wb("evaluate", {"code": "(()=>{var t=document.body.innerText||'';return JSON.stringify({len:t.length, head:t.slice(0,200)})})()"})
    try:
        d = json.loads(r["data"]["value"])
        head = d["head"].replace("\n", " ")[:120]
        bad = [b for b in ["重新登录", "扫码登录", "手机号登录", "登录超限"] if b in head]
        print(f"[小红书] 页面首屏：{head}", flush=True)
        print(f"[小红书] 判定：{'需重新登录' if bad else '已登录'}", flush=True)
    except Exception as e:
        print("[小红书] 页面读取失败", e, flush=True)
    return has


def check_feigua():
    wb("navigate", {"url": "https://dy.feigua.cn/app/#/goods-library/index"}, wait=7, session="fg-check")
    cs = cookies("https://dy.feigua.cn")
    names = {c["name"]: c["value"] for c in cs}
    print(f"[飞瓜] cookie 数量 {len(cs)}｜关键名：{[n for n in names if 'FEIGUA' in n.upper() or 'token' in n.lower()][:6]}", flush=True)
    r = wb("evaluate", {"code": "(()=>{var t=document.body.innerText||'';return JSON.stringify({head:t.slice(0,300)})})()"}, session="fg-check")
    try:
        d = json.loads(r["data"]["value"])
        head = d["head"].replace("\n", " ")[:180]
        bad = [b for b in ["重新登录", "扫码登录", "手机号登录", "请登录", "登录超时"] if b in head]
        print(f"[飞瓜] 页面首屏：{head}", flush=True)
        print(f"[飞瓜] 判定：{'需重新登录' if bad else '已登录'}", flush=True)
    except Exception as e:
        print("[飞瓜] 页面读取失败", e, flush=True)


if __name__ == "__main__":
    check_xhs()
    check_feigua()
