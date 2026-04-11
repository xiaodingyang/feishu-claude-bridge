"""
重启飞书机器人脚本
"""
import os
import sys
import time
import subprocess

# 设置 UTF-8 输出
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def main():
    print("=" * 40)
    print("重启飞书机器人")
    print("=" * 40)

    # 读取 PID
    pid_file = "bot.pid"
    if os.path.exists(pid_file):
        with open(pid_file, "r") as f:
            old_pid = f.read().strip()
        print(f"[1/3] 停止旧进程 (PID: {old_pid})...")

        # 尝试优雅停止
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/PID", old_pid, "/F"],
                             capture_output=True, timeout=5)
            else:
                subprocess.run(["kill", old_pid],
                             capture_output=True, timeout=5)
            print(f"  ✓ 已停止进程 {old_pid}")
        except Exception as e:
            print(f"  ⚠ 停止失败: {e}")

        # 删除旧 PID 文件
        try:
            os.remove(pid_file)
        except:
            pass
    else:
        print("[1/3] 未找到旧进程")

    time.sleep(2)

    print("[2/3] 启动新进程...")
    try:
        if sys.platform == "win32":
            # Windows 使用 pythonw 后台运行
            subprocess.Popen(
                ["pythonw", "bot.py"],
                cwd=os.path.dirname(__file__) or ".",
                creationflags=0x08000000  # CREATE_NO_WINDOW
            )
        else:
            # Unix 使用 nohup
            subprocess.Popen(
                ["nohup", "python3", "bot.py", "&"],
                cwd=os.path.dirname(__file__) or ".",
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        print("  ✓ 启动命令已执行")
    except Exception as e:
        print(f"  ✗ 启动失败: {e}")
        return

    time.sleep(3)

    print("[3/3] 检查状态...")
    if os.path.exists(pid_file):
        with open(pid_file, "r") as f:
            new_pid = f.read().strip()
        print(f"  ✓ 新进程已启动 (PID: {new_pid})")
        print(f"  ✓ 日志文件: bot.log")
    else:
        print("  ⚠ 未找到 PID 文件，请检查 bot.log")

    print("=" * 40)
    print("完成！")

if __name__ == "__main__":
    main()
