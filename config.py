"""
配置管理 - 从 .env 文件读取配置
"""

import os
import sys
import shutil
from pathlib import Path

from dotenv import load_dotenv

# 项目根目录（bot.py 所在目录）
BASE_DIR = Path(__file__).resolve().parent


def resolve_claude_cli(raw: str) -> str:
    """跨平台查找 claude CLI 路径"""
    if os.path.isabs(raw):
        return raw
    found = shutil.which(raw)
    if found:
        return found
    if sys.platform == "win32":
        found = shutil.which(raw + ".cmd")
        if found:
            return found
    return raw


def load_config() -> dict:
    """读取并校验配置，返回字典"""
    # 加载 .env
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        print(f"⚠️  未找到 .env 文件，请复制 .env.example 为 .env 并填写配置")
        print(f"   cp .env.example .env")
        sys.exit(1)

    app_id = os.getenv("FEISHU_APP_ID", "")
    app_secret = os.getenv("FEISHU_APP_SECRET", "")

    if not app_id or "your_app_id" in app_id:
        print("❌ 请在 .env 中设置 FEISHU_APP_ID")
        sys.exit(1)
    if not app_secret or "your_app_secret" in app_secret:
        print("❌ 请在 .env 中设置 FEISHU_APP_SECRET")
        sys.exit(1)

    claude_cli = resolve_claude_cli(os.getenv("CLAUDE_CLI", "claude"))
    work_dir = os.path.abspath(os.getenv("WORK_DIR", "."))

    cfg = {
        "app_id": app_id,
        "app_secret": app_secret,
        "claude_cli": claude_cli,
        "work_dir": work_dir,
        "task_timeout": int(os.getenv("TASK_TIMEOUT", "180")),
        "max_output_length": int(os.getenv("MAX_OUTPUT_LENGTH", "3500")),
        "max_turns": int(os.getenv("MAX_TURNS", "30")),
        "log_file": str(BASE_DIR / "bot.log"),
        "pid_file": str(BASE_DIR / "bot.pid"),
        # Anthropic API 配置
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", "sk-d18945d49fc81d53aa9b4d0370807b53078a5fb1927dbe416155dc54dbd056e8"),
        "anthropic_base_url": os.getenv("ANTHROPIC_BASE_URL", "https://cc-vibe.com"),
        "anthropic_model": os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6"),
    }

    return cfg


def print_config(cfg: dict):
    """打印配置摘要（隐藏密钥）"""
    print(f"  APP_ID:        {cfg['app_id'][:8]}...")
    print(f"  CLAUDE_CLI:    {cfg['claude_cli']}")
    print(f"  WORK_DIR:      {cfg['work_dir']}")
    print(f"  TASK_TIMEOUT:  {cfg['task_timeout']}s")
    print(f"  MAX_OUTPUT:    {cfg['max_output_length']}")
    print(f"  MAX_TURNS:     {cfg['max_turns']}")
