"""支持多轮记忆 + 流式输出的命令行 AI 聊天程序。"""

import os
import json
from openai import OpenAI

# DeepSeek 官方模型名：deepseek-chat（通用）/ deepseek-reasoner（推理）
MODEL = "deepseek-chat"
BASE_URL = "https://api.deepseek.com"
SYSTEM_PROMPT = (
    "你是 Python 入门教练。请用中文回答，控制在三句话以内；"
    "解释代码问题时，先指出原因，再给最小修正。"
)
MAX_HISTORY = 40  # 保留的最近历史条数，防止上下文无限增长


def get_client():
    """延迟创建客户端。

    刻意不放在模块顶层：否则一旦缺少 API Key，连 `import ai_chat` 都会
    抛异常，导致本模块无法被测试（CI 环境没有密钥，只有假客户端）。
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError(
            "未设置 DEEPSEEK_API_KEY 环境变量。\n"
            '  PowerShell: $env:DEEPSEEK_API_KEY = "你的-api-key"'
        )
    return OpenAI(api_key=api_key, base_url=BASE_URL)


def load_history(path):
    """读取历史；文件不存在或损坏时返回默认 system 消息。"""
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as history_file:
                messages = json.load(history_file)
            if isinstance(messages, list) and messages:
                print(f"已恢复 {len(messages) - 1} 条历史消息")
                return messages
        except (json.JSONDecodeError, OSError) as error:
            print(f"历史记录读取失败，将重新开始：{error}")
    return [{"role": "system", "content": SYSTEM_PROMPT}]


def trim_history(messages, limit=MAX_HISTORY):
    """保留首条 system 消息 + 最近 limit 条对话，防止上下文无限增长。"""
    if not messages:
        return []
    if messages[0].get("role") == "system":
        return [messages[0]] + messages[1:][-limit:]
    return messages[-limit:]


def save_history(path, messages):
    """裁剪后写入磁盘，返回实际保存的内容。"""
    trimmed = trim_history(messages)
    with open(path, "w", encoding="utf-8") as history_file:
        json.dump(trimmed, history_file, ensure_ascii=False, indent=2)
    return trimmed


def stream_reply(messages, client=None):
    """向后端发起流式请求，逐个产出文本片段（生成器）。

    client 通过参数注入，测试时可传假客户端，无需真实网络与密钥。
    打印交给调用方，让「取数据」与「显示」解耦，便于复用。
    """
    client = client or get_client()
    stream = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def main():
    script_directory = os.path.dirname(os.path.abspath(__file__))
    history_file_path = os.path.join(script_directory, "chat_history.json")
    messages = load_history(history_file_path)

    while True:
        try:
            question = input("你：")
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if question.strip().lower() in {"exit", "quit"}:
            break
        if not question.strip():
            continue

        messages.append({"role": "user", "content": question})

        try:
            # 生成器是惰性的：真正的网络请求发生在第一次迭代时，
            # 所以 try 必须包住整个消费过程，而不是只包住调用本身。
            print("AI：", end="", flush=True)
            chunks = []
            for piece in stream_reply(messages):
                chunks.append(piece)
                print(piece, end="", flush=True)
            print()
        except Exception as error:
            print(f"\nAPI 请求失败：{error}")
            messages.pop()  # 移除失败的用户消息，避免污染历史
            continue

        answer = "".join(chunks)
        if not answer:
            print("（回复为空，已忽略）")
            messages.pop()
            continue

        messages.append({"role": "assistant", "content": answer})

    messages = save_history(history_file_path, messages)
    print(f"对话已保存到 {history_file_path}")


if __name__ == "__main__":
    main()