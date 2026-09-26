#!/usr/bin/env python3
"""编排入口：一键跑 采集 → 计算 → 视图模型 → 提示打开前端。

用法：
  python3 run.py                # 全链路（需 Kimi 扩展已连接罗盘登录态）
  python3 run.py --skip-collect # 用已有 raw 数据重算（调试前端用）
  python3 run.py --no-llm       # 跳过 LLM 调用
"""
import os, sys, json, datetime, argparse, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collector import config

PY = sys.executable


def _date_window():
    today = datetime.date.today()
    end = today - datetime.timedelta(days=2)  # 罗盘当天数据未出
    begin = end - datetime.timedelta(days=6)
    return end.strftime("%Y/%m/%d"), begin.strftime("%Y/%m/%d")


def collect(date_str, begin, end):
    """采集：商品榜 + 类目概览。"""
    from collector.compass import product_rank, category_overview
    r1 = product_rank.run(date_str, begin, end)
    print("[run] product_rank:", json.dumps(r1, ensure_ascii=False))
    if not r1.get("ok"):
        return False
    r2 = category_overview.run(end, begin, end)
    print("[run] category_overview:", json.dumps(r2, ensure_ascii=False))
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-collect", action="store_true", help="用已有 raw 数据重算")
    ap.add_argument("--no-llm", action="store_true", help="跳过 LLM 调用")
    args = ap.parse_args()

    end, begin = _date_window()
    date_str = end.replace("/", "-")

    if not args.skip_collect:
        print("[run] 1/2 采集罗盘数据（窗口 %s ~ %s）…" % (begin, end))
        if not collect(end, begin, end):
            print("[run] 采集失败，终止。可用 --skip-collect 基于已有数据调试。")
            sys.exit(1)
    else:
        print("[run] 跳过采集，用已有 raw 数据")

    print("[run] 2/2 计算 + 组装视图模型…")
    cmd = [PY, os.path.join("data-mart", "build_view.py")]
    if args.no_llm:
        cmd.append("--no-llm")
    r = subprocess.run(cmd, cwd=os.path.dirname(os.path.abspath(__file__)))
    if r.returncode != 0:
        sys.exit(r.returncode)

    web = os.path.join(config.BASE_DIR, "web", "index.html")
    print("\n[run] 完成。打开前端：\n  open '%s'" % web)


if __name__ == "__main__":
    main()
