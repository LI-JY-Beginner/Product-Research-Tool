@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo   小红书评论采集工具包
echo ============================================================
echo.
echo   第 1 步：改配置（config 文件夹里选一个类目：
echo            cleanser=洁面  eyeoil=眼油  _template=新类目）
echo   第 2 步：确认浏览器已登录小红书
echo   第 3 步：回车开始跑
echo.
echo   常用命令：
echo     开始采集.bat              跑默认类目（洁面）全流程
echo     开始采集.bat cleanser     指定类目
echo     开始采集.bat 20          只跑第 20 步（过滤）
echo     开始采集.bat --from 20   从第 20 步开始跑
echo     开始采集.bat --dry-run   只看看会跑什么，不真跑
echo.
echo ============================================================
set /p CAT=请输入类目名（直接回车=cleanser）：
if "%CAT%"=="" set CAT=cleanser

set PY=C:\Users\17831\.workbuddy\binaries\python\versions\3.13.12\python.exe
if not exist "%PY%" set PY=python

echo.
echo 正在运行：%CAT%
"%PY%" scripts\run_all.py --cat %CAT%
echo.
echo ============================================================
echo   跑完了。产出在配置里 project.outputDir 指定的目录：
echo     raw\xhs_output\      每篇笔记的原始 JSON
echo     data\                清洗与统计结果
echo     *评论汇总_日期.md/html  汇总文档
echo ============================================================
pause
