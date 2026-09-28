# -*- coding: utf-8 -*-
"""
run_all.py — 一条命令跑完整条链路（含 WebBridge 看门狗）

用法：
  python run_all.py                          # 用默认类目（cleanser）全跑
  python run_all.py --cat 面膜                # 换类目
  python run_all.py --config D:/x/mask.yaml   # 直接指定配置文件
  python run_all.py --only 10,11,20,21,30     # 只跑指定步骤
  python run_all.py --from 13                 # 从第 13 步开始（前面的已有数据）
  python run_all.py --limit 20                # 本批最多处理 20 条（快速试跑）
  python run_all.py --dry-run                 # 只打印将执行什么，不真跑

★ 这个脚本存在的唯一原因：本机 WebBridge 守护进程会在每次调用后被回收，
  必须有个常驻看门狗在旁边盯着、发现死了就拉起来。
  直接用 00/10/13 等单步脚本跳过本脚本，守护进程可能随时死掉导致静默采到 0 条。

★ 子进程会清掉 HTTP_PROXY 等代理变量 —— 本机系统代理会劫持 127.0.0.1，
  不清掉的话所有 WebBridge 调用都会连不上。
"""
import os
import subprocess
import sys
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, HERE)


def _find_python():
    """按优先级找解释器：环境变量 → 默认路径 → 当前解释器 → 系统 python。

    ★ 换机器时不用改代码：默认路径不存在会自动退到 `python`。
      想指定就设环境变量 XHS_PYTHON。
    """
    env = os.environ.get("XHS_PYTHON")
    if env and os.path.exists(env):
        return env
    default = r"C:\Users\17831\.workbuddy\binaries\python\versions\3.13.12\python.exe"
    if os.path.exists(default):
        return default
    cur = sys.executable
    if cur and os.path.exists(cur):
        return cur
    return "python"


def _find_daemon():
    """同理，找不到就返回 None，看门狗会跳过（不影响纯本地步骤）"""
    env = os.environ.get("XHS_DAEMON")
    if env and os.path.exists(env):
        return env
    default = r"C:\Users\17831\.kimi-webbridge\bin\kimi-webbridge.exe"
    if os.path.exists(default):
        return default
    for cand in (r"C:\Users\%s\.kimi-webbridge\bin\kimi-webbridge.exe" % os.environ.get("USERNAME", ""),
                 os.path.expanduser(r"~/.kimi-webbridge/bin/kimi-webbridge.exe")):
        if os.path.exists(cand):
            return cand
    return None


PYTHON = _find_python()
DAEMON = _find_daemon()

STATUS_URL = "http://127.0.0.1:10086/status"

# ---- 链路定义：(步骤号, 脚本文件, 是否需要浏览器/登录态) ----
STEPS = [
    ("00", "00_preflight.py", True),
    ("10", "10_collect_links.py", True),
    ("11", "11_clean_links.py", False),
    ("12", "12_pick_notes.py", False),
    ("13", "13_scrape_notes.py", True),
    ("14", "14_deep_comments.py", True),
    ("20", "20_filter.py", False),
    ("21", "21_analyze.py", False),
    ("30", "30_build_doc.py", False),
]

_STOP = False


def daemon_alive():
    urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))
    try:
        import json
        d = json.loads(urllib.request.urlopen(STATUS_URL, timeout=4).read().decode())
        return bool(d.get("running")), bool(d.get("extension_connected"))
    except Exception:
        return False, False


def watchdog():
    """常驻看门狗：守护进程死掉就拉起来"""
    while not _STOP:
        running, _ = daemon_alive()
        if not running:
            try:
                subprocess.run([DAEMON, "start"], capture_output=True, timeout=30)
            except Exception:
                pass
        time.sleep(5)


def parse_args(argv):
    cat = config = only = start_from = None
    limit = None
    dry = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--cat" and i + 1 < len(argv):
            cat = argv[i + 1]; i += 2
        elif a == "--config" and i + 1 < len(argv):
            config = argv[i + 1]; i += 2
        elif a == "--only" and i + 1 < len(argv):
            only = [x.strip() for x in argv[i + 1].split(",") if x.strip()]; i += 2
        elif a == "--from" and i + 1 < len(argv):
            start_from = argv[i + 1].strip(); i += 2
        elif a == "--limit" and i + 1 < len(argv):
            limit = argv[i + 1]; i += 2
        elif a == "--dry-run":
            dry = True; i += 1
        else:
            i += 1
    return cat, config, only, start_from, limit, dry


def main(argv):
    global _STOP
    cat, config, only, start_from, limit, dry = parse_args(argv)

    # 选步骤
    steps = STEPS
    if only:
        steps = [s for s in STEPS if s[0] in only]
    elif start_from:
        hit = False
        sel = []
        for s in STEPS:
            if s[0] == start_from:
                hit = True
            if hit:
                sel.append(s)
        steps = sel or STEPS

    print("=" * 68, flush=True)
    print("小红书评论采集工具包 · 一键跑批", flush=True)
    print(f"  类目配置：{config or ('config/' + (cat or 'cleanser') + '.yaml')}", flush=True)
    print(f"  步骤：{' → '.join(s[0] for s in steps)}", flush=True)
    print(f"  本批上限：{limit or '不限'}", flush=True)
    print("=" * 68, flush=True)

    if dry:
        for num, f, need_wb in steps:
            print(f"  将运行 {f}" + ("（需要浏览器登录态）" if need_wb else ""), flush=True)
        return 0

    # 子进程环境：清掉代理（本机系统代理会劫持 127.0.0.1）
    env = os.environ.copy()
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        env.pop(k, None)

    need_browser = any(s[2] for s in steps)
    if need_browser and not DAEMON:
        print("⚠️ 没找到 kimi-webbridge.exe，看门狗不启用。", flush=True)
        print("   需要抓网页的步骤（00/10/13/14）会失败；纯本地步骤不受影响。", flush=True)
        print("   解决：设环境变量 XHS_DAEMON 指向它，或改 scripts/run_all.py 顶部的 DAEMON。", flush=True)
    if need_browser and DAEMON:
        t = threading.Thread(target=watchdog, daemon=True)
        t.start()
        print("[看门狗] 已启动，正在等守护进程 + 浏览器扩展就绪…", flush=True)
        for _ in range(15):
            running, connected = daemon_alive()
            if running and connected:
                break
            time.sleep(2)
        running, connected = daemon_alive()
        print(f"[看门狗] running={running}｜extension_connected={connected}", flush=True)
        if not connected:
            print("         ⚠️ 浏览器扩展没连上。请打开 Edge 确认 Kimi 浏览器扩展已启用。", flush=True)
            print("            采链接/抓笔记两步会失败，其余步骤不受影响。", flush=True)

    base_cmd = [PYTHON, ""]
    common = []
    if config:
        common += ["--config", config]
    elif cat:
        common += ["--cat", cat]
    if limit:
        common += ["--limit", str(limit)]

    failures = []
    for num, f, need_wb in steps:
        path = os.path.join(HERE, f)
        if not os.path.exists(path):
            print(f"\n!! 跳过 {f}（文件不存在）", flush=True)
            continue
        print(f"\n{'=' * 24} 步骤 {num} · {f} {'=' * 24}", flush=True)
        t0 = time.time()
        try:
            r = subprocess.run([PYTHON, path] + common, cwd=PKG, env=env,
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=7200)
            out = (r.stdout or "") + (("\n[STDERR]\n" + r.stderr) if r.stderr.strip() else "")
            print(out[-6000:], flush=True)
            print(f"---- 退出码 {r.returncode}｜耗时 {time.time() - t0:.0f}s ----", flush=True)
            # 00 体检返回 2 = 有问题但不致命；采集类返回 2 = 登录过期
            if r.returncode not in (0, 2):
                failures.append((num, f, r.returncode))
                print("!! 本步失败，后续依赖它的步骤可能拿不到数据", flush=True)
        except subprocess.TimeoutExpired:
            print(f"!! 超时（2 小时），已跳过 {f}", flush=True)
            failures.append((num, f, "timeout"))
        except Exception as e:
            print(f"!! 运行异常：{e}", flush=True)
            failures.append((num, f, str(e)))

    _STOP = True
    print(f"\n{'=' * 68}", flush=True)
    if failures:
        print("跑批结束，但有失败步骤：", flush=True)
        for num, f, code in failures:
            print(f"  ✗ 步骤 {num} {f}（{code}）", flush=True)
    else:
        print("跑批全部完成 ✓", flush=True)
    print("=" * 68, flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    finally:
        _STOP = True
