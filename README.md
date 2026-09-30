# AI Chat CLI

一个基于 DeepSeek API 的命令行 AI 聊天程序，支持 **多轮对话记忆** 与 **流式输出**。

## 功能特性

- 🔄 **多轮对话记忆**：上下文持久化到 `chat_history.json`，重启后自动恢复
- ⌨️ **流式输出**：边生成边打印，打字机效果，响应体感更快
- ✂️ **历史裁剪**：仅保留最近 `MAX_HISTORY` 条消息，避免上下文无限增长、控制 token 成本
- 🛡️ **健壮性**：历史文件损坏自动降级、API 失败自动回滚消息、`Ctrl+C` 优雅退出并保存
- ⚙️ **可配置**：模型、System Prompt、历史长度均为顶部常量，改起来方便

## 项目结构

```
ai-chat/
├── ai_chat.py          # 主程序
├── requirements.txt    # 依赖
├── .gitignore          # 忽略本地对话记录与缓存
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
py -m pip install -r requirements.txt
```

### 2. 配置 API Key

本项目通过环境变量读取密钥，**不要把密钥写进代码**。

PowerShell（当前会话）：

```powershell
$env:DEEPSEEK_API_KEY = "你的-api-key"
```

如需永久生效：

```powershell
[Environment]::SetEnvironmentVariable("DEEPSEEK_API_KEY", "你的-api-key", "User")
```

### 3. 运行

```bash
py ai_chat.py
```

输入问题回车即可，输入 `exit` 或 `quit` 退出（`Ctrl+C` 也可）。

## 核心实现说明

| 设计点 | 做法 | 原因 |
|---|---|---|
| 流式输出 | `stream=True` + 逐 chunk 打印 `delta.content` | 降低首字延迟，改善交互体验 |
| 上下文管理 | 保存时裁剪为 `system + 最近 N 条` | 防止历史无限增长导致超长/超费 |
| 失败回滚 | 请求异常时 `messages.pop()` | 避免失败的用户消息污染后续对话 |
| 优雅退出 | 捕获 `EOFError` / `KeyboardInterrupt` | 保证退出前一定落盘保存 |

## 后续计划

- [ ] 加入 RAG，支持基于本地文档问答并给出引用来源
- [ ] 加入工具调用（函数调用 / Agent）
- [ ] 加入回答质量评估脚本

## License

MIT
