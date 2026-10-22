@echo off
chcp 936 >nul
setlocal

rem ============================================================
rem  停止后端服务
rem
rem  为什么需要它：启动器模式下双击桌面图标后，壳拉起的后端会
rem  独立留在后台（浏览器要用），壳本身已经退出 —— 所以任务栏里
rem  看不到它。不用软件了想彻底关掉，双击本文件即可。
rem ============================================================

set "FOUND=0"

tasklist /FI "IMAGENAME eq ChemLabBackend.exe" 2>nul | find /I "ChemLabBackend.exe" >nul
if not errorlevel 1 (
    taskkill /F /IM ChemLabBackend.exe >nul 2>&1
    echo 已停止后端服务。
    set "FOUND=1"
)

tasklist /FI "IMAGENAME eq heji-toolbox.exe" 2>nul | find /I "heji-toolbox.exe" >nul
if not errorlevel 1 (
    taskkill /F /IM heji-toolbox.exe >nul 2>&1
    echo 已停止主程序。
    set "FOUND=1"
)

if "%FOUND%"=="0" (
    echo 当前没有在运行的服务。
) else (
    echo.
    echo 提示：浏览器里已打开的页面会显示"后端未就绪"，这是正常的。
)

timeout /t 2 >nul
exit /b 0
