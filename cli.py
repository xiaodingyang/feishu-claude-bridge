"""
CLI 入口 - 管理 Feishu Claude Code Bridge

用法:
  python cli.py start        # 前台启动
  python cli.py start -d     # 后台启动
  python cli.py stop         # 停止
  python cli.py status       # 查看状态
  python cli.py install      # 注册开机自启
  python cli.py uninstall    # 取消开机自启
"""

import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
BOT_SCRIPT = BASE_DIR / "bot.py"
PID_FILE = BASE_DIR / "bot.pid"
TASK_NAME = "FeishuClaudeBridge"


def read_pid() -> int | None:
    """读取 PID 文件"""
    try:
        return int(PID_FILE.read_text().strip())
    except (FileNotFoundError, ValueError):
        return None


def is_running(pid: int) -> bool:
    """检查进程是否存活"""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def cmd_start(args):
    """启动机器人"""
    pid = read_pid()
    if pid and is_running(pid):
        print(f"⚠️  机器人已在运行 (PID {pid})")
        return

    if args.detach:
        _start_detached()
    else:
        _start_foreground()


def _start_foreground():
    """前台启动（直接运行 bot.py）"""
    from config import load_config
    from bot import run
    cfg = load_config()
    print("📋 配置:")
    from config import print_config
    print_config(cfg)
    print()
    run(cfg)


def _start_detached():
    """后台启动"""
    if sys.platform == "win32":
        pythonw = sys.executable.replace("python.exe", "pythonw.exe")
        if not os.path.exists(pythonw):
            print(f"❌ 找不到 pythonw: {pythonw}")
            sys.exit(1)
        subprocess.Popen(
            [pythonw, str(BOT_SCRIPT)],
            creationflags=0x08000000,
            cwd=str(BASE_DIR),
        )
        print("✅ 机器人已在后台启动")
    else:
        # macOS / Linux: 后台运行，输出到 bot.log
        log_file = BASE_DIR / "bot.log"
        with open(log_file, "a") as f:
            proc = subprocess.Popen(
                [sys.executable, str(BOT_SCRIPT)],
                stdout=f, stderr=f,
                start_new_session=True,
                cwd=str(BASE_DIR),
            )
        # 写 PID 文件（bot.py 也会写，但这里先写以备立即 stop）
        PID_FILE.write_text(str(proc.pid))
        print(f"✅ 机器人已在后台启动 (PID {proc.pid})")


def cmd_stop(args):
    """停止机器人"""
    pid = read_pid()
    if not pid:
        print("⚠️  未找到运行中的机器人")
        return
    if not is_running(pid):
        print("⚠️  进程已不存在，清理 PID 文件")
        PID_FILE.unlink(missing_ok=True)
        return

    try:
        if sys.platform == "win32":
            os.system(f"taskkill /F /PID {pid}")
        else:
            os.kill(pid, signal.SIGTERM)
        print(f"✅ 已停止机器人 (PID {pid})")
    except Exception as e:
        print(f"❌ 停止失败: {e}")
    finally:
        PID_FILE.unlink(missing_ok=True)


def cmd_status(args):
    """查看状态"""
    pid = read_pid()
    if pid and is_running(pid):
        print(f"✅ 机器人运行中 (PID {pid})")
    else:
        print("⏹  机器人未运行")
        if pid:
            print("   (PID 文件存在但进程已死，可忽略)")
            PID_FILE.unlink(missing_ok=True)


def cmd_install(args):
    """注册开机自启"""
    if sys.platform == "win32":
        pythonw = sys.executable.replace("python.exe", "pythonw.exe")
        cmd_str = f'"{pythonw}" "{BOT_SCRIPT}"'
        try:
            subprocess.run(
                ["schtasks", "/Create", "/TN", TASK_NAME,
                 "/TR", cmd_str, "/SC", "ONLOGON",
                 "/RL", "HIGHEST", "/F"],
                capture_output=True, text=True,
                creationflags=0x08000000,
            )
            print(f"✅ 已注册 Windows 计划任务: {TASK_NAME}")
        except subprocess.CalledProcessError as e:
            # 可能需要管理员权限
            print(f"❌ 注册失败，请以管理员身份运行:")
            print(f"   schtasks /Create /TN {TASK_NAME} /TR \"{cmd_str}\" /SC ONLOGON /RL HIGHEST /F")
    elif sys.platform == "darwin":
        plist_src = BASE_DIR / "com.feishu.claude.bridge.plist"
        if not plist_src.exists():
            print("❌ 找不到 macOS launchd 模板")
            return
        # 替换路径
        content = plist_src.read_text()
        content = content.replace("/FULL/PATH/TO/python3", sys.executable)
        content = content.replace("/FULL/PATH/TO/bot.py", str(BOT_SCRIPT))
        content = content.replace("/FULL/PATH/TO/bot.log", str(BASE_DIR / "bot.log"))
        plist_dst = Path.home() / "Library" / "LaunchAgents" / "com.feishu.claude.bridge.plist"
        plist_dst.write_text(content)
        os.system(f"launchctl load {plist_dst}")
        print(f"✅ 已注册 macOS launchd: {plist_dst}")
    else:
        print("⚠️  Linux 自动启动请手动配置 systemd 或 cron")


def cmd_uninstall(args):
    """取消开机自启"""
    if sys.platform == "win32":
        subprocess.run(
            ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
            capture_output=True,
            creationflags=0x08000000,
        )
        print(f"✅ 已删除 Windows 计划任务: {TASK_NAME}")
    elif sys.platform == "darwin":
        plist_dst = Path.home() / "Library" / "LaunchAgents" / "com.feishu.claude.bridge.plist"
        if plist_dst.exists():
            os.system(f"launchctl unload {plist_dst}")
            plist_dst.unlink()
            print("✅ 已删除 macOS launchd 配置")
        else:
            print("⚠️  未找到 launchd 配置")


def main():
    parser = argparse.ArgumentParser(
        description="Feishu Claude Code Bridge - 飞书机器人管理工具",
    )
    sub = parser.add_subparsers(dest="command")

    # start
    p_start = sub.add_parser("start", help="启动机器人")
    p_start.add_argument("-d", "--detach", action="store_true", help="后台运行")

    # stop
    sub.add_parser("stop", help="停止机器人")

    # status
    sub.add_parser("status", help="查看运行状态")

    # install / uninstall
    sub.add_parser("install", help="注册开机自启")
    sub.add_parser("uninstall", help="取消开机自启")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    commands = {
        "start": cmd_start,
        "stop": cmd_stop,
        "status": cmd_status,
        "install": cmd_install,
        "uninstall": cmd_uninstall,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
