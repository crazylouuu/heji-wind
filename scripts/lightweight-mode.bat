@echo off
chcp 936 >nul
setlocal

rem ============================================================
rem  轻量模式：只启动后端 + 用浏览器打开（不开 Tauri 窗口）
rem
rem  适用：只用「实验记录 / 化合物库 / 看板 / 模板 / 标签 / 备份」
rem        这些合迹 ChemELN 功能，不需要工具箱那 12 个页面。
rem
rem  不适用：要用 SOP 库 / 投料表 / 计算器 / 溶剂库 / 纯化 / 安全
rem          这些功能只存在于工具箱界面里，8765 上没有。
rem ============================================================

set "BE=%LOCALAPPDATA%\合记 ChemLab\resources\backend\ChemLabBackend.exe"
set "URL=http://127.0.0.1:8765"

netstat -ano | findstr "127.0.0.1:8765" | findstr LISTENING >nul 2>&1
if not errorlevel 1 (
    echo 后端已在运行，直接打开浏览器...
    goto open
)

if not exist "%BE%" (
    echo.
    echo [错误] 未找到后端程序：
    echo        %BE%
    echo.
    echo 请先安装「合记 ChemLab」，或用完整模式（桌面图标）。
    echo.
    pause
    exit /b 1
)

echo 正在启动后端（首次启动约需 7 到 25 秒）...
start "" "%BE%" --port 8765

set /a n=0
:wait
timeout /t 1 >nul
set /a n+=1
netstat -ano | findstr "127.0.0.1:8765" | findstr LISTENING >nul 2>&1
if not errorlevel 1 goto open
if %n% lss 40 goto wait

echo.
echo [错误] 启动超时（40 秒）。请查看日志：
echo        %APPDATA%\ChemLab\logs\backend.log
echo.
pause
exit /b 1

:open
echo 已就绪，正在打开浏览器...
start "" "%URL%"
rem 后端在后台独立运行，关掉本窗口不会影响它
rem 用完请在任务管理器结束 ChemLabBackend.exe
timeout /t 3 >nul
exit /b 0
