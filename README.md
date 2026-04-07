# Feishu Claude Code Bridge

通过飞书消息操控 Claude Code，让 AI 助手随时在线。

## 它能做什么？

在飞书上发消息 → Claude Code 执行任务 → 结果直接回复到飞书。

支持 Claude Code 的全部能力：读写文件、执行命令、搜索代码、创建项目等。

```
飞书 App → WebSocket 长连接 → bot.py → claude --print CLI → 回复飞书
```

## 快速开始

### 前置条件

- Python 3.10+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) 已安装并登录
- 飞书自建应用（参考下方说明）

### 飞书应用配置

1. 前往 [飞书开放平台](https://open.feishu.cn) 创建自建应用
2. 添加「机器人」能力
3. 获取 `App ID` 和 `App Secret`
4. 权限管理 → 开通以下权限：
   - `im:message` - 获取与发送单聊、群组消息
   - `im:message:send_as_bot` - 以应用身份发送消息
5. 事件订阅 → 添加事件 `im.message.receive_v1`（接收消息）
6. 发布应用

### 安装

```bash
git clone https://github.com/你的用户名/feishu-claude-bridge.git
cd feishu-claude-bridge
pip install -r requirements.txt
cp .env.example .env
```

### 配置

编辑 `.env` 文件：

```env
# 必填 - 飞书应用凭证
FEISHU_APP_ID=cli_xxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxx

# 可选 - Claude CLI 路径（默认自动查找）
CLAUDE_CLI=claude

# 可选 - 工作目录（默认当前目录）
WORK_DIR=.

# 可选 - 超时时间（秒）
TASK_TIMEOUT=180
```

### 运行

```bash
# 前台运行（调试用，可看日志输出）
python cli.py start

# 后台运行（推荐）
python cli.py start -d

# 查看状态
python cli.py status

# 停止
python cli.py stop
```

## 开机自启

```bash
# 注册（需要管理员/sudo 权限）
python cli.py install

# 取消
python cli.py uninstall
```

| 平台 | 方式 |
|------|------|
| Windows | 计划任务（登录时启动 pythonw） |
| macOS | launchd（RunAtLoad） |
| Linux | 手动配置 systemd 或 cron |

## 配置说明

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `FEISHU_APP_ID` | ✅ | - | 飞书应用 App ID |
| `FEISHU_APP_SECRET` | ✅ | - | 飞书应用 App Secret |
| `CLAUDE_CLI` | | `claude` | Claude Code CLI 路径，不在 PATH 时填完整路径 |
| `WORK_DIR` | | `.` | Claude Code 工作目录 |
| `TASK_TIMEOUT` | | `180` | 任务超时（秒） |
| `MAX_OUTPUT_LENGTH` | | `3500` | 最大输出长度（超出截断） |
| `MAX_TURNS` | | `30` | Claude 最大对话轮次 |

## 常见问题

### 找不到 claude 命令

在 `.env` 中设置 `CLAUDE_CLI` 为完整路径：

```env
# Windows
CLAUDE_CLI=C:\Users\你\AppData\Roaming\npm\claude.cmd

# macOS / Linux
CLAUDE_CLI=/usr/local/bin/claude
```

### 飞书发消息没回复

1. 检查机器人是否在运行：`python cli.py status`
2. 查看日志：`cat bot.log`（最后 50 行）
3. 确认飞书应用已发布，且权限和事件订阅配置正确

### 回复超时

调大超时时间：

```env
TASK_TIMEOUT=300
```

### Windows 弹黑窗

使用 `python cli.py start -d` 后台启动，不会弹窗。前台启动用于调试。

### 重复回复消息

确保只运行一个实例。`python cli.py status` 检查是否有多个进程。

## 安全提示

- `.env` 包含密钥，**不要提交到 Git**（已在 .gitignore 中排除）
- `--dangerously-skip-permissions` 会跳过 Claude Code 的权限确认，仅在可信环境使用
- 建议在飞书应用中设置消息可见范围，限制可用人员

## License

MIT
