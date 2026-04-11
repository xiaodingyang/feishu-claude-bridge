@echo off
chcp 65001 >nul
echo ========================================
echo 飞书机器人状态检查
echo ========================================

cd /d "%~dp0"

if exist bot.pid (
    set /p PID=<bot.pid
    echo [进程] PID: %PID%

    tasklist /FI "PID eq %PID%" 2>nul | find /I "python" >nul
    if %errorlevel% equ 0 (
        echo [状态] ✓ 运行中
    ) else (
        echo [状态] ✗ 进程不存在（可能已崩溃）
    )
) else (
    echo [进程] 未找到 PID 文件
    echo [状态] ✗ 未运行
)

echo.
echo [配置]
type .env | findstr /V "SECRET"

echo.
echo [最近日志] (最后 10 行)
powershell -Command "Get-Content bot.log -Tail 10"

echo.
echo ========================================
pause
