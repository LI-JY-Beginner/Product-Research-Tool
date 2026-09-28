# -*- coding: utf-8 -*-
"""
00_preflight.py — 跑之前的体检：守护进程 + 扩展连接 + 小红书登录态

只看两件事：
  1) Kimi WebBridge 守护进程活着、浏览器扩展连上了
  2) 小红书是登录状态

★ 判定登录态别用 document.cookie —— web_session / id_token 是 httpOnly，
  JS 读不到，会得出「未登录」的错误结论。必须用 cdp Network.getCookies。

用法: python 00_preflight.py [--cat cleanser]
退出码: 0=全部就绪  2=有问题（可重跑，先按提示处理）
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xcommon as X


def main():
    opt, _ = X.cli("采集前体检")
    cfg = X.load_cfg(explicit=opt.config, cat=opt.cat)
    print(f"类目：{cfg.project.name}（配置 {cfg._config_path}）", flush=True)
    print(f"产出目录：{cfg._out}", flush=True)
    print("-" * 60, flush=True)

    ok = True

    # 1) 守护进程
    running, connected = X.wb_alive()
    print(f"[1/2] WebBridge 守护进程 running={running}｜扩展 extension_connected={connected}", flush=True)
    if not running:
        print("      ✗ 守护进程没起来。看门狗会自动拉起，直接跑 run_all.py 即可；", flush=True)
        print("        如果是用本脚本单独体检，请先运行 run_all.py（它会带看门狗）。", flush=True)
        ok = False
    elif not connected:
        print("      ✗ 守护进程正常，但浏览器扩展没连上。请打开 Edge，确认 Kimi 浏览器扩展已启用。", flush=True)
        ok = False

    # 2) 登录态
    wb = X.WB(cfg._session, cfg._tmp)
    wb("navigate", {"url": "https://www.xiaohongshu.com/explore"}, wait=5)
    r = wb("cdp", {"method": "Network.getCookies",
                   "params": {"urls": ["https://www.xiaohongshu.com"]}})
    names = {}
    try:
        for c in (r.get("data", {}).get("result", {}) or {}).get("cookies", []):
            names[c["name"]] = c["value"]
    except Exception:
        pass
    has = "web_session" in names or "id_token" in names
    print(f"[2/2] 小红书 cookie {len(names)} 个｜web_session={'有' if 'web_session' in names else '无'}"
          f"｜id_token={'有' if 'id_token' in names else '无'}", flush=True)
    txt = wb.eval_text("document.body.innerText") or ""
    good, why = X.login_ok(txt)
    head = X.norm(txt)[:100]
    print(f"      页面首屏：{head}", flush=True)
    if has and good:
        print("      ✓ 判定：已登录", flush=True)
    else:
        print(f"      ✗ 判定：需要重新登录（cookie={has} / 页面={why or '正常'}）", flush=True)
        print("        请在本机浏览器打开 https://www.xiaohongshu.com 扫码登录后重跑。", flush=True)
        ok = False

    print("-" * 60, flush=True)
    print("结论：" + ("✓ 可以开跑" if ok else "✗ 先处理上面的问题"), flush=True)
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
