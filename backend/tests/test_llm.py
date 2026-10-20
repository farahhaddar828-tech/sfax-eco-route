"""Exercise both tool-calling protocols against a mocked HTTP server."""
import asyncio
import json

import httpx
import pytest

from app.ai import llm as llm_mod
from app.ai.llm import LLM, Tool


def _patch(monkeypatch, handler):
    real = httpx.AsyncClient
    monkeypatch.setattr(llm_mod.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(handler), **kw))


def _tool():
    calls = []
    return Tool("emergency_numbers", "nums", {"type": "object", "properties": {}},
                lambda: calls.append(1) or {"Police": "197"}), calls


@pytest.mark.parametrize("provider,host", [("openai", "api.openai.com"), ("grok", "api.x.ai"),
                                           ("ollama", "ollama")])
def test_openai_compatible_tool_loop(monkeypatch, provider, host):
    seen = []

    def handler(req: httpx.Request):
        body = json.loads(req.content)
        seen.append((req.url.host, body))
        if len(seen) == 1:
            return httpx.Response(200, json={"choices": [{"message": {"content": None, "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "emergency_numbers", "arguments": "{}"}}]}}]})
        assert body["messages"][-1] == {"role": "tool", "tool_call_id": "c1", "content": '{"Police": "197"}'}
        return httpx.Response(200, json={"choices": [{"message": {"content": "Appelez le 197."}}]})

    _patch(monkeypatch, handler)
    tool, calls = _tool()
    res = asyncio.run(LLM(provider).run_agent("sys", [{"role": "user", "content": "police?"}], [tool]))
    assert res.text == "Appelez le 197." and calls == [1]
    assert seen[0][0] == host and seen[0][1]["tools"][0]["function"]["name"] == "emergency_numbers"


def test_anthropic_tool_loop(monkeypatch):
    seen = []

    def handler(req: httpx.Request):
        body = json.loads(req.content)
        seen.append(body)
        assert req.headers["anthropic-version"]
        if len(seen) == 1:
            assert body["tools"][0]["input_schema"]["type"] == "object"
            return httpx.Response(200, json={"content": [
                {"type": "tool_use", "id": "t1", "name": "emergency_numbers", "input": {}}]})
        assert body["messages"][-1]["content"][0] == {"type": "tool_result", "tool_use_id": "t1",
                                                      "content": '{"Police": "197"}'}
        return httpx.Response(200, json={"content": [{"type": "text", "text": "Appelez le 197."}]})

    _patch(monkeypatch, handler)
    tool, calls = _tool()
    res = asyncio.run(LLM("claude").run_agent("sys", [{"role": "user", "content": "police?"}], [tool]))
    assert res.text == "Appelez le 197." and res.tool_trace[0]["tool"] == "emergency_numbers"
