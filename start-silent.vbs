' Feishu Claude Code Bridge - Windows 静默启动
' 使用方法: 将下面的路径替换为你的实际路径，双击运行或在计划任务中引用

Set WshShell = CreateObject("WScript.Shell")
WshShell.Run """PYTHONW_PATH"" ""BOT_PATH""", 0, False

' 替换说明:
'   PYTHONW_PATH → pythonw.exe 的完整路径，例如:
'     C:\Users\你的用户名\AppData\Local\Programs\Python\Python313\pythonw.exe
'   BOT_PATH → bot.py 的完整路径，例如:
'     C:\Users\你的用户名\feishu-claude-bridge\bot.py
'
' 推荐使用 cli.py install 自动配置:
'   python cli.py install
