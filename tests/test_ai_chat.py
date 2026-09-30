"""`ai_chat` 模块的单元测试。

这些测试全部**离线**运行：不访问网络，也不需要 `DEEPSEEK_API_KEY`。

关键手法是「依赖注入 + Mock」：`stream_reply` 把 client 作为参数接收，
测试时传入 `MagicMock` 顶替真实客户端，于是网络这一层被完全隔离。
"""

import json
from unittest.mock import MagicMock

import pytest

from ai_chat import (
    MAX_HISTORY,
    MODEL,
    SYSTEM_PROMPT,
    get_client,
    load_history,
    save_history,
    stream_reply,
    trim_history,
)


def make_fake_client(pieces):
    """构造假客户端：create() 返回与 pieces 一一对应的 chunk 列表。"""
    chunks = [
        MagicMock(choices=[MagicMock(delta=MagicMock(content=piece))])
        for piece in pieces
    ]
    client = MagicMock()
    client.chat.completions.create.return_value = chunks
    return client


# --------------------------------------------------------------- get_client

def test_get_client_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        get_client()


# ------------------------------------------------------------- load_history

def test_load_history_returns_default_when_file_missing(tmp_path):
    messages = load_history(tmp_path / "not_exist.json")

    assert messages == [{"role": "system", "content": SYSTEM_PROMPT}]


def test_load_history_restores_saved_messages(tmp_path):
    path = tmp_path / "history.json"
    saved = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好，有什么可以帮你？"},
    ]
    path.write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")

    assert load_history(path) == saved


def test_load_history_falls_back_on_corrupted_json(tmp_path):
    path = tmp_path / "history.json"
    path.write_text("{ 这不是合法 JSON", encoding="utf-8")

    assert load_history(path) == [{"role": "system", "content": SYSTEM_PROMPT}]


def test_load_history_falls_back_when_json_is_not_a_list(tmp_path):
    path = tmp_path / "history.json"
    path.write_text(json.dumps({"role": "system"}), encoding="utf-8")

    assert load_history(path) == [{"role": "system", "content": SYSTEM_PROMPT}]


def test_load_history_falls_back_on_empty_list(tmp_path):
    path = tmp_path / "history.json"
    path.write_text("[]", encoding="utf-8")

    assert load_history(path) == [{"role": "system", "content": SYSTEM_PROMPT}]


# ------------------------------------------------------------- trim_history

def test_trim_history_keeps_system_and_recent_turns():
    messages = [{"role": "system", "content": "s"}] + [
        {"role": "user", "content": str(i)} for i in range(10)
    ]

    trimmed = trim_history(messages, limit=3)

    assert trimmed[0] == {"role": "system", "content": "s"}
    assert [m["content"] for m in trimmed[1:]] == ["7", "8", "9"]


def test_trim_history_without_system_message():
    messages = [{"role": "user", "content": str(i)} for i in range(5)]

    assert [m["content"] for m in trim_history(messages, limit=2)] == ["3", "4"]


def test_trim_history_handles_empty_list():
    assert trim_history([]) == []


def test_trim_history_keeps_everything_when_under_limit():
    messages = [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "hi"},
    ]

    assert trim_history(messages, limit=10) == messages


# ------------------------------------------------------------- save_history

def test_save_history_writes_trimmed_content(tmp_path):
    path = tmp_path / "history.json"
    messages = [{"role": "system", "content": "s"}] + [
        {"role": "user", "content": str(i)} for i in range(MAX_HISTORY + 5)
    ]

    trimmed = save_history(path, messages)

    assert len(trimmed) == MAX_HISTORY + 1
    assert json.loads(path.read_text(encoding="utf-8")) == trimmed


def test_save_history_roundtrip_keeps_chinese_readable(tmp_path):
    path = tmp_path / "history.json"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "中文内容不应被转义"},
    ]

    save_history(path, messages)

    assert load_history(path) == messages
    assert "中文内容不应被转义" in path.read_text(encoding="utf-8")


# ------------------------------------------------------------ stream_reply

def test_stream_reply_yields_pieces_in_order():
    client = make_fake_client(["你", "好", "！"])

    assert list(stream_reply([], client=client)) == ["你", "好", "！"]


def test_stream_reply_skips_empty_pieces():
    client = make_fake_client(["a", None, "", "b"])

    assert list(stream_reply([], client=client)) == ["a", "b"]


def test_stream_reply_requests_streaming_with_expected_model():
    client = make_fake_client(["x"])

    list(stream_reply([{"role": "user", "content": "hi"}], client=client))

    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == MODEL
    assert kwargs["stream"] is True
    assert kwargs["messages"] == [{"role": "user", "content": "hi"}]


def test_stream_reply_is_lazy():
    """未消费生成器时不应发起请求——这正是 main() 里 try 范围要包住整个循环的原因。"""
    client = make_fake_client(["x"])

    stream_reply([], client=client)

    client.chat.completions.create.assert_not_called()
