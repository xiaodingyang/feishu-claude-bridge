"""
飞书机器人 - 直连 Claude Code CLI

用法:
  python bot.py          # 直接运行（需要先创建 .env）
  python cli.py start    # 通过 CLI 启动（推荐）
"""

import json
import subprocess
import threading
import re
import sys
import os

import lark_oapi as lark
from lark_oapi.api.im.v1 import *

from config import load_config

# ============ 全局 ============
client = None
task_lock = threading.Lock()
task_running = False
processed_ids = set()
dedup_lock = threading.Lock()


def log(msg, log_file=None):
    if log_file is None:
        return
    import datetime
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")
        f.flush()


def strip_ansi(text: str) -> str:
    """去除 ANSI 转义码"""
    text = re.sub(r'\x1b\[[0-9;]*m', '', text)
    text = re.sub(r'\x1b\].*?\x07', '', text)
    return text


# ============ Claude Code CLI ============
def call_claude(prompt, cfg):
    cmd = [
        cfg["claude_cli"], "--print",
        "--output-format", "text",
        "--max-turns", str(cfg["max_turns"]),
        "--dangerously-skip-permissions",
        prompt,
    ]
    try:
        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
        r = subprocess.run(
            cmd, capture_output=True,
            timeout=cfg["task_timeout"], cwd=cfg["work_dir"],
            **kwargs,
        )
        out = r.stdout.decode("utf-8", errors="replace").strip()
        out = strip_ansi(out)
        if not out and r.stderr:
            err = r.stderr.decode("utf-8", errors="replace").strip()
            out = f"[stderr] {err[:300]}"
        if not out:
            out = "(无输出)"
        log(f"[claude] reply: {out[:100]}", cfg.get("log_file"))
        max_len = cfg["max_output_length"]
        return out[:max_len] + "\n...(截断)" if len(out) > max_len else out
    except subprocess.TimeoutExpired:
        return f"⏰ 超时 ({cfg['task_timeout']}s)"
    except FileNotFoundError:
        return "❌ 找不到 claude 命令，请检查 CLAUDE_CLI 配置"
    except Exception as e:
        return f"❌ {e}"


# ============ 发消息 ============
def reply_text(receive_id, rid_type, text, log_file=None):
    req = CreateMessageRequest.builder() \
        .receive_id_type(rid_type) \
        .request_body(CreateMessageRequestBody.builder()
                       .receive_id(receive_id)
                       .msg_type("text")
                       .content(json.dumps({"text": text}))
                       .build()).build()
    resp = client.im.v1.message.create(req)
    if not resp.success():
        log(f"[send] 失败: {resp.code} {resp.msg}", log_file)


# ============ 收消息 ============
def on_message(data: lark.im.v1.P2ImMessageReceiveV1) -> None:
    global task_running

    msg = data.event.message
    sender = data.event.sender
    msg_id = msg.message_id

    # 去重
    with dedup_lock:
        if msg_id in processed_ids:
            return
        processed_ids.add(msg_id)
        if len(processed_ids) > 1000:
            processed_ids.clear()

    if sender.sender_type != "user":
        return
    if msg.message_type != "text":
        return

    try:
        text = json.loads(msg.content).get("text", "").strip()
    except Exception:
        return

    text = re.sub(r"@_user_\d+\s*", "", text).strip()
    if not text:
        return

    if msg.chat_type == "p2p":
        rid = sender.sender_id.open_id
        rid_type = "open_id"
    else:
        rid = msg.chat_id
        rid_type = "chat_id"

    lf = _cfg.get("log_file")
    log(f"[msg] {text[:80]}", lf)

    with task_lock:
        if task_running:
            reply_text(rid, rid_type, "⏳ 上一个任务还在跑，稍等...", lf)
            return
        task_running = True

    try:
        reply_text(rid, rid_type, "⏳ 处理中...", lf)
        result = call_claude(text, _cfg)
        reply_text(rid, rid_type, result, lf)
        log(f"[done] {len(result)} 字", lf)
    except Exception as e:
        reply_text(rid, rid_type, f"❌ {e}", lf)
        log(f"[error] {e}", lf)
    finally:
        with task_lock:
            task_running = False


# ============ 启动 ============
_cfg = {}


def run(cfg: dict):
    """启动飞书机器人"""
    global client, _cfg
    _cfg = cfg

    # 写 PID 文件
    pid_file = cfg.get("pid_file")
    if pid_file:
        with open(pid_file, "w") as f:
            f.write(str(os.getpid()))

    lf = cfg.get("log_file")
    log("=" * 40, lf)
    log("飞书机器人启动 (Feishu Claude Code Bridge)", lf)
    log(f"工作目录: {cfg['work_dir']}", lf)
    log(f"Claude CLI: {cfg['claude_cli']}", lf)
    log("=" * 40, lf)

    client = lark.Client.builder() \
        .app_id(cfg["app_id"]).app_secret(cfg["app_secret"]) \
        .log_level(lark.LogLevel.INFO).build()

    handler = lark.EventDispatcherHandler.builder(
        encrypt_key="",
        verification_token="",
    ).register_p2_im_message_receive_v1(on_message).build()

    ws = lark.ws.Client(
        cfg["app_id"], cfg["app_secret"],
        event_handler=handler,
        log_level=lark.LogLevel.INFO,
    )

    log("[启动] 连接飞书...", lf)
    print("🚀 飞书机器人已启动，等待消息...")
    ws.start()


if __name__ == "__main__":
    cfg = load_config()
    run(cfg)
