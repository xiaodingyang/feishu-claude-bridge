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
import time
import logging
import uuid
import anthropic
from logging.handlers import RotatingFileHandler
from pathlib import Path

import lark_oapi as lark
from lark_oapi.api.im.v1 import *

from config import load_config

# ============ 全局 ============
client = None
task_lock = threading.Lock()
task_running = False
processed_ids = set()
dedup_lock = threading.Lock()
logger = None
health_check_thread = None
reconnect_attempts = 0
MAX_RECONNECT_ATTEMPTS = 10

# 会话管理
user_sessions = {}  # {user_id: {"session_id": str, "history": [{"role": str, "content": str}]}}
sessions_lock = threading.Lock()
sessions_file = None
MAX_HISTORY_TURNS = 10  # 最多保留 10 轮对话


def setup_logger(log_file):
    """设置日志轮转（最大 10MB，保留 5 个备份）"""
    global logger
    logger = logging.getLogger("feishu_bot")
    logger.setLevel(logging.INFO)

    # 轮转处理器：10MB 一个文件，保留 5 个
    handler = RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5, encoding="utf-8"
    )
    formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s',
                                   datefmt='%H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # 同时输出到控制台
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    return logger


def log(msg, level="info"):
    """兼容旧的 log 函数"""
    if logger is None:
        return
    if level == "error":
        logger.error(msg)
    elif level == "warning":
        logger.warning(msg)
    else:
        logger.info(msg)


def strip_ansi(text: str) -> str:
    """去除 ANSI 转义码"""
    text = re.sub(r'\x1b\[[0-9;]*m', '', text)
    text = re.sub(r'\x1b\].*?\x07', '', text)
    return text


# ============ 会话管理 ============
def load_sessions():
    """加载会话映射"""
    global user_sessions
    if sessions_file and os.path.exists(sessions_file):
        try:
            with open(sessions_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 兼容旧格式（只有 session_id 字符串）
            for user_id, value in data.items():
                if isinstance(value, str):
                    user_sessions[user_id] = {
                        "session_id": value,
                        "history": []
                    }
                else:
                    user_sessions[user_id] = value
            log(f"[session] 加载 {len(user_sessions)} 个会话")
        except Exception as e:
            log(f"[session] 加载失败: {e}", "warning")
            user_sessions = {}


def save_sessions():
    """保存会话映射"""
    if sessions_file:
        try:
            with open(sessions_file, 'w', encoding='utf-8') as f:
                json.dump(user_sessions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log(f"[session] 保存失败: {e}", "error")


def get_or_create_session(user_id: str) -> dict:
    """获取或创建用户的会话数据"""
    with sessions_lock:
        if user_id not in user_sessions:
            session_id = str(uuid.uuid4())
            user_sessions[user_id] = {
                "session_id": session_id,
                "history": []
            }
            save_sessions()
            log(f"[session] 新建会话: {user_id[:8]}... -> {session_id[:8]}...")
        return user_sessions[user_id]


def reset_session(user_id: str) -> dict:
    """重置用户会话"""
    with sessions_lock:
        session_id = str(uuid.uuid4())
        user_sessions[user_id] = {
            "session_id": session_id,
            "history": []
        }
        save_sessions()
        log(f"[session] 重置会话: {user_id[:8]}... -> {session_id[:8]}...")
        return user_sessions[user_id]


def add_to_history(user_id: str, role: str, content: str):
    """添加消息到对话历史"""
    with sessions_lock:
        if user_id in user_sessions:
            history = user_sessions[user_id]["history"]
            history.append({"role": role, "content": content})
            # 限制历史长度
            if len(history) > MAX_HISTORY_TURNS * 2:  # 每轮包含 user + assistant
                user_sessions[user_id]["history"] = history[-(MAX_HISTORY_TURNS * 2):]
            save_sessions()


def build_prompt_with_history(user_id: str, current_message: str) -> str:
    """构建带有历史上下文的提示词"""
    if user_id not in user_sessions:
        return current_message
    
    history = user_sessions[user_id]["history"]
    if not history:
        return current_message
    
    # 构建上下文提示（更明确的格式）
    context_parts = [
        "=== 对话上下文 ===",
        "以下是我们刚才的对话，请基于这些上下文回答新问题：\n"
    ]
    
    for msg in history:
        if msg["role"] == "user":
            context_parts.append(f"User: {msg['content']}")
        else:
            context_parts.append(f"Assistant: {msg['content']}")
    
    context_parts.append("\n=== 新消息 ===")
    context_parts.append(f"User: {current_message}")
    context_parts.append("\nAssistant:")
    
    return "\n".join(context_parts)


# ============ Claude Code CLI ============
def call_claude(messages, cfg):
    """使用 Anthropic API 调用 Claude（支持真正的多轮对话）"""
    try:
        client = anthropic.Anthropic(
            api_key=cfg.get("anthropic_api_key"),
            base_url=cfg.get("anthropic_base_url", "https://api.anthropic.com")
        )

        response = client.messages.create(
            model=cfg.get("anthropic_model", "claude-opus-4-6"),
            max_tokens=4096,
            messages=messages
        )

        result = response.content[0].text
        log(f"[claude-api] reply: {result[:100]}")

        max_len = cfg["max_output_length"]
        if len(result) > max_len:
            return result[:max_len - 10] + "\n...(截断)"
        return result

    except Exception as e:
        log(f"[claude-api] 错误: {e}", "error")
        return f"❌ API 调用失败: {str(e)}"


# ============ 发消息 ============
def reply_text(receive_id, rid_type, text):
    req = CreateMessageRequest.builder() \
        .receive_id_type(rid_type) \
        .request_body(CreateMessageRequestBody.builder()
                       .receive_id(receive_id)
                       .msg_type("text")
                       .content(json.dumps({"text": text}))
                       .build()).build()
    resp = client.im.v1.message.create(req)
    if not resp.success():
        log(f"[send] 失败: {resp.code} {resp.msg}", "error")
        return None
    return resp.data.message_id if resp.data else None


def delete_message(message_id):
    """删除消息"""
    from lark_oapi.api.im.v1 import DeleteMessageRequest
    req = DeleteMessageRequest.builder().message_id(message_id).build()
    resp = client.im.v1.message.delete(req)
    if not resp.success():
        log(f"[delete] 失败: {resp.code} {resp.msg}", "error")


# ============ 收消息 ============
def on_message(data: lark.im.v1.P2ImMessageReceiveV1) -> None:
    global task_running

    try:
        msg = data.event.message
        sender = data.event.sender
        msg_id = msg.message_id
    except Exception as e:
        log(f"[error] 解析消息失败: {e}", "error")
        return

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

    # 获取用户 ID（用于会话管理）
    user_id = sender.sender_id.open_id

    log(f"[msg] {text[:80]}")

    # 检查特殊命令
    if text.lower() in ["/new", "/reset", "/clear", "重置", "重新开始", "清除会话"]:
        reset_session(user_id)
        reply_text(rid, rid_type, "✅ 已重置会话，开始新的对话")
        return

    with task_lock:
        if task_running:
            reply_text(rid, rid_type, "上一个任务还在跑，稍等...")
            return
        task_running = True

    processing_msg_id = None
    try:
        # 获取或创建会话数据
        get_or_create_session(user_id)

        # 发送"处理中..."并保存 message_id
        processing_msg_id = reply_text(rid, rid_type, "🤔 让我想想...")

        # 构建消息数组（API 格式）
        messages = []
        if user_id in user_sessions:
            messages = user_sessions[user_id]["history"].copy()

        # 添加当前消息
        messages.append({"role": "user", "content": text})

        # 调用 Claude API
        result = call_claude(messages, _cfg)

        # 保存对话历史
        add_to_history(user_id, "user", text)
        add_to_history(user_id, "assistant", result)

        # 发送结果
        reply_text(rid, rid_type, result)

        log(f"[done] {len(result)} 字")
    except Exception as e:
        reply_text(rid, rid_type, f"报错了: {e}")
        log(f"[error] {e}", "error")
    finally:
        with task_lock:
            task_running = False


# ============ 健康检查 ============
def health_check_loop(cfg):
    """定期检查机器人状态"""
    while True:
        try:
            time.sleep(300)  # 每 5 分钟检查一次
            log("[health] 心跳检查")

            # 检查 PID 文件
            pid_file = cfg.get("pid_file")
            if pid_file and os.path.exists(pid_file):
                with open(pid_file, "r") as f:
                    pid = f.read().strip()
                    if pid != str(os.getpid()):
                        log(f"[health] 警告: PID 不匹配 (文件:{pid} 当前:{os.getpid()})", "warning")
        except Exception as e:
            log(f"[health] 检查异常: {e}", "error")


# ============ 启动 ============
_cfg = {}


def run(cfg: dict):
    """启动飞书机器人（带重连机制）"""
    global client, _cfg, health_check_thread, reconnect_attempts, sessions_file
    _cfg = cfg

    # 设置日志
    setup_logger(cfg.get("log_file", "bot.log"))

    # 设置会话文件路径
    sessions_file = os.path.join(os.path.dirname(cfg.get("log_file", "bot.log")), "sessions.json")
    load_sessions()

    # 写 PID 文件
    pid_file = cfg.get("pid_file")
    if pid_file:
        with open(pid_file, "w") as f:
            f.write(str(os.getpid()))

    log("=" * 40)
    log("飞书机器人启动 (Feishu Claude Code Bridge)")
    log(f"工作目录: {cfg['work_dir']}")
    log(f"Claude CLI: {cfg['claude_cli']}")
    log(f"任务超时: {cfg['task_timeout']}s")
    log(f"最大输出: {cfg['max_output_length']} 字符")
    log(f"会话文件: {sessions_file}")
    log("=" * 40)

    # 启动健康检查线程
    if health_check_thread is None:
        health_check_thread = threading.Thread(target=health_check_loop, args=(cfg,), daemon=True)
        health_check_thread.start()
        log("[health] 健康检查线程已启动")

    while reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
        try:
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

            log(f"[启动] 连接飞书... (尝试 {reconnect_attempts + 1}/{MAX_RECONNECT_ATTEMPTS})")
            if sys.stdout:
                try:
                    print("飞书机器人已启动，等待消息...")
                except Exception:
                    pass

            # 重置重连计数
            reconnect_attempts = 0

            # 阻塞运行
            ws.start()

        except KeyboardInterrupt:
            log("[退出] 用户中断")
            break
        except Exception as e:
            reconnect_attempts += 1
            log(f"[error] WebSocket 异常: {e}", "error")

            if reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
                wait_time = min(30, 5 * reconnect_attempts)  # 指数退避，最多 30 秒
                log(f"[重连] {wait_time} 秒后重试... ({reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS})", "warning")
                time.sleep(wait_time)
            else:
                log(f"[error] 达到最大重连次数 ({MAX_RECONNECT_ATTEMPTS})，退出", "error")
                break

    log("[退出] 飞书机器人已停止")


if __name__ == "__main__":
    cfg = load_config()
    run(cfg)
