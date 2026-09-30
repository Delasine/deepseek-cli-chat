"""支持多轮记忆 + 流式输出的命令行 AI 聊天程序。"""

import os
import json
from openai import OpenAI

# DeepSeek 官方模型名：deepseek-chat（通用）/ deepseek-reasoner（推理）
MODEL = "deepseek-chat"
SYSTEM_PROMPT = (
    "你是 Python 入门教练。请用中文回答，控制在三句话以内；"
    "解释代码问题时，先指出原因，再给最小修正。"
)
MAX_HISTORY = 40  # 保留的最近历史条数，防止上下文无限增长

client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com",
)


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


def save_history(path, messages):
    """保存历史，只保留 system + 最近 MAX_HISTORY 条。"""
    trimmed = [messages[0]] + messages[1:][-MAX_HISTORY:]
    with open(path, "w", encoding="utf-8") as history_file:
        json.dump(trimmed, history_file, ensure_ascii=False, indent=2)
    return trimmed


def stream_reply(messages):
    """流式请求并实时打印增量内容，返回完整回答。"""
    stream = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        stream=True,
    )
    print("AI：", end="", flush=True)
    chunks = []
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            chunks.append(delta)
            print(delta, end="", flush=True)
    print()
    return "".join(chunks)


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
            answer = stream_reply(messages)
        except Exception as error:
            print(f"\nAPI 请求失败：{error}")
            messages.pop()  # 移除失败的用户消息，避免污染历史
            continue

        messages.append({"role": "assistant", "content": answer})

    messages = save_history(history_file_path, messages)
    print(f"对话已保存到 {history_file_path}")


if __name__ == "__main__":
    main()