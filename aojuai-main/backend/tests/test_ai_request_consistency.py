"""顶层设计:所有模型请求 reasoning/tools/scope 单一来源与 golden 一致性。"""
import json

import httpx
import pytest

from app.core.ai_client_factory import (
    AI_REASONING_EFFORT_WHITELIST,
    ai_cache_scope,
    build_ai_client,
)


def test_factory_importable_in_clean_interpreter():
    """core 层公共工厂必须可独立导入(不拖起 app.domain 全量初始化)。"""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-c", "import app.core.ai_client_factory as f; assert f.ai_cache_scope('x', 1)"],
        capture_output=True, text=True, cwd=".",
    )
    assert result.returncode == 0, result.stderr[-800:]


def test_ai_cache_scope_single_authority():
    assert ai_cache_scope("assistant", 1) == "aoju-assistant-tenant-1"
    assert ai_cache_scope("ppt", "7") == "aoju-ppt-tenant-7"
    assert ai_cache_scope("PPT_Master", 2) == "aoju-ppt-master-tenant-2"


def test_reasoning_whitelist_rejects_garbage():
    for bad in ("default", "", None):
        client = build_ai_client(base_url="https://gw/v1", api_key="k", model="m", reasoning_effort=bad)
        assert client.reasoning_effort is None, bad
    client = build_ai_client(base_url="https://gw/v1", api_key="k", model="m", reasoning_effort="banana")
    assert client.reasoning_effort is None
    # 迁移决策:env 值 "auto" 显式归 None(历史上会把字面量发给上游)
    import os
    os.environ["AOJU_AI_REASONING_EFFORT"] = "auto"
    try:
        client = build_ai_client(base_url="https://gw/v1", api_key="k", model="m", reasoning_effort="auto")
        assert client.reasoning_effort is None
    finally:
        os.environ.pop("AOJU_AI_REASONING_EFFORT", None)
    for good in AI_REASONING_EFFORT_WHITELIST:
        client = build_ai_client(base_url="https://gw/v1", api_key="k", model="m", reasoning_effort=good)
        assert client.reasoning_effort == good


class FakeStreamResponse:
    def __init__(self, lines):
        self._lines = lines
        self.status_code = 200

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def aread(self):
        return b"{}"


class FakeStreamCM:
    def __init__(self, response):
        self._r = response

    async def __aenter__(self):
        return self._r

    async def __aexit__(self, *args):
        return None


@pytest.mark.asyncio
async def test_golden_payload_conformance_assistant_vs_ppt(monkeypatch):
    """同模型同 factory:assistant 与 ppt 客户端的出网 payload 除声明差异
    (cache scope 值、tools)外必须逐字段一致(用户纪律:公共函数,零漂移)。"""
    captured = []

    def fake_stream(self, method, url, **kwargs):
        captured.append(dict(kwargs.get("json") or {}))
        lines = [
            'data: {"type": "response.output_text.delta", "delta": "OK"}',
            'data: {"type": "response.completed", "response": {"status": "completed", "usage": {"input_tokens": 10, "output_tokens": 2}}}',
        ]
        return FakeStreamCM(FakeStreamResponse(lines))

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)

    def make(domain, tools=None):
        return build_ai_client(
            base_url="https://gw.example/v1", api_key="k", model="gpt-5.6-sol",
            api_mode="responses", reasoning_effort="none",
            cache_scope=ai_cache_scope(domain, 1), tools=tools,
        )

    assistant_client = make("assistant", tools=[{"type": "web_search"}])
    ppt_client = make("ppt")
    messages = [{"role": "system", "content": "S" * 50}, {"role": "user", "content": "U"}]
    await assistant_client.chat_with_usage(messages, stream=True, request_max_attempts=1)
    await ppt_client.chat_with_usage(messages, stream=True, request_max_attempts=1)
    a, b = captured[0], captured[1]

    declared_diffs = {"user", "prompt_cache_key", "tools"}
    keys_a, keys_b = set(a.keys()) - declared_diffs, set(b.keys()) - declared_diffs
    assert keys_a == keys_b, (keys_a, keys_b)
    for key in keys_a:
        assert a[key] == b[key], (key, a[key], b[key])
    assert a["user"] == "aoju-assistant-tenant-1" and b["user"] == "aoju-ppt-tenant-1"
    assert a["prompt_cache_key"] == a["user"] and b["prompt_cache_key"] == b["user"]


def test_request_fingerprint_shape():
    client = build_ai_client(
        base_url="https://gw/v1", api_key="k", model="m", api_mode="responses",
        reasoning_effort="none", cache_scope=ai_cache_scope("ppt", 1),
        tools=[{"type": "web_search"}, {"type": "function", "name": "f"}],
    )
    fp = client.request_fingerprint()
    assert fp["fpApiMode"] == "responses" and fp["fpReasoning"] == "none"
    assert fp["fpCacheKeyHash"] and len(fp["fpCacheKeyHash"]) == 10
    assert fp["fpTools"] == ["function:f", "web_search"]
