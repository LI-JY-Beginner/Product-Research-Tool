#!/bin/bash
# 美妆数据看板 · 一键启动
# 双击运行（或在终端 bash 启动工作台.command）
# 作用：启动本地服务并自动打开工作台页面

cd "$(dirname "$0")/web" || exit 1

PY="/Users/mac/.workbuddy/binaries/python/versions/3.13.12/bin/python3"
PORT=8899

# 若已在跑则不重复启动
if /usr/bin/curl -s -m 3 -o /dev/null "http://127.0.0.1:$PORT/index.html"; then
  echo "服务已在运行：http://127.0.0.1:$PORT/index.html"
else
  echo "启动本地服务（端口 $PORT）…"
  "$PY" -m http.server "$PORT" >/dev/null 2>&1 &
  sleep 2
fi

echo "打开工作台…"
open "http://127.0.0.1:$PORT/index.html"
echo ""
echo "提示：本窗口/服务保持运行即可。关闭方法：在活动监视器结束 http.server，或运行 pkill -f 'http.server $PORT'"
