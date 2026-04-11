@echo off
chcp 65001 >nul
echo ========================================
echo 重启飞书机器人
echo ========================================

cd /d "%~dp0"

echo [1/3] 停止旧进程...
if exist bot.pid (
    set /p PID=<bot.pid
    taskkill /PID %PID% /F >nul 2>&1
    if %errorlevel% equ 0 (
        echo   已停止进程 %PID%
    ) else (
        echo   进程 %PID% 不存在或已停止
    )
    del bot.pid
) else (
    echo   未找到 PID 文件
)

timeout /t 2 /nobreak >nul

echo [2/3] 启动新进程...
start /b pythonw bot.py

timeout /t 2 /nobreak >nul

echo [3/3] 检查状态...
if exist bot.pid (
    set /p NEW_PID=<bot.pid
    echo   ✓ 新进程已启动 (PID: %NEW_PID%)
    echo   ✓ 日志文件: bot.log
) else (
    echo   ✗ 启动失败，请检查 bot.log
)

echo ========================================
echo 完成！
pause
