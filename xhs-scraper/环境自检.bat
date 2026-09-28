@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo   环境自检（第一次用请先跑这个）
echo ============================================================
echo.

set PY=C:\Users\17831\.workbuddy\binaries\python\versions\3.13.12\python.exe
if not exist "%PY%" (
  echo [1/3] 没找到内置 Python，改用系统 python
  set PY=python
) else (
  echo [1/3] Python 路径 OK
)
"%PY%" --version
if errorlevel 1 (
  echo   !! Python 不可用，请先安装 Python 3.9+
  pause & exit /b 1
)

echo.
echo [2/3] 检查依赖 pyyaml
"%PY%" -c "import yaml; print('  pyyaml 已装，版本', yaml.__version__)"
if errorlevel 1 (
  echo   正在安装 pyyaml...
  "%PY%" -m pip install --only-binary=:all: pyyaml
  if errorlevel 1 (
    echo   !! 安装失败，请手动执行：
    echo      %PY% -m pip install --only-binary=:all: pyyaml
    pause & exit /b 1
  )
)

echo.
echo [3/3] 检查 WebBridge 守护进程
"%PY%" scripts\00_preflight.py --cat cleanser
if errorlevel 1 (
  echo.
  echo   !! 有环境问题。常见原因：
  echo      1）Kimi WebBridge 没装 / 守护进程没起 —— 看下面「依赖」一节
  echo      2）Edge 浏览器没打开，或 Kimi 浏览器扩展没启用
  echo      3）小红书没登录 —— 在浏览器里扫码登录后重试
)

echo.
echo ============================================================
pause
