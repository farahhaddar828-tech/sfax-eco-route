"""Provider-agnostic LLM layer: Claude, OpenAI GPT, xAI Grok, Ollama (local) or none.

Switch with one env var:  LLM_PROVIDER=claude|openai|grok|ollama|none
  * openai, grok and ollama all speak the OpenAI Chat Completions format
    (Grok at api.x.ai/v1, Ollama at <host>/v1), so they share one client.
  * Claude uses the Anthropic Messages API (different tool-call format).
  * none = deterministic rule-based fallback, so the app, tests and CI work
    with no key and no GPU.

No vendor SDK is required — plain HTTP via httpx keeps the image small and
makes the request/response shapes visible.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import httpx

from ..config import get_settings

log = logging.getLogger(__name__)

ToolFn = Callable[..., Awaitable[Any] | Any]


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict          # JSON schema
    fn: ToolFn

    async def call(self, args: dict) -> str:
        try:
            res = self.fn(**args)
            if hasattr(res, "__await__"):
                res = await res
            return json.dumps(res, ensure_ascii=False, default=str)[:6000]
        except Exception as e:  # noqa: BLE001 - surface tool errors to the model
            return json.dumps({"error": str(e)})


@dataclass
class AgentResult:
    text: str
    tool_trace: list[dict]
    provider: str
    model: str


DEFAULT_MODELS = {
    "claude": "claude-haiku-5-5",      # cheapest Claude tier; override with LLM_MODEL
    "openai": "gpt-4o-mini",
    "grok": "grok-3-mini",
    "ollama": "qwen2.5:7b",            # good French + tool calling on a laptop GPU/CPU
}


class LLM:
    def __init__(self, provider: str | None = None, model: str | None = None):
        s = get_settings()
        self.provider = (provider or s.llm_provider or "none").lower()
        self.model = model or s.llm_model or DEFAULT_MODELS.get(self.provider, "")
        self.s = s

    # ------------------------------------------------------------------ public
    async def run_agent(self, system: str, history: list[dict], tools: list[Tool],
                        max_steps: int = 5) -> AgentResult:
        if self.provider == "claude":
            return await self._run_anthropic(system, history, tools, max_steps)
        if self.provider in ("openai", "grok", "ollama"):
            return await self._run_openai_compat(system, history, tools, max_steps)
        raise RuntimeError("no LLM provider configured")

    async def complete_json(self, system: str, prompt: str) -> dict:
        res = await self.run_agent(system + "\nRéponds uniquement avec un objet JSON valide.",
                                   [{"role": "user", "content": prompt}], tools=[], max_steps=1)
        txt = res.text.strip()
        start, end = txt.find("{"), txt.rfind("}")
        return json.loads(txt[start:end + 1])

    @property
    def enabled(self) -> bool:
        return self.provider in ("claude", "openai", "grok", "ollama")

    # ---------------------------------------------------- OpenAI-compatible
    def _oa_endpoint(self) -> tuple[str, dict]:
        if self.provider == "openai":
            return "https://api.openai.com/v1", {"Authorization": f"Bearer {self.s.openai_api_key}"}
        if self.provider == "grok":
            return "https://api.x.ai/v1", {"Authorization": f"Bearer {self.s.xai_api_key}"}
        return self.s.ollama_base_url.rstrip("/") + "/v1", {}

    async def _run_openai_compat(self, system, history, tools, max_steps) -> AgentResult:
        base, headers = self._oa_endpoint()
        msgs: list[dict] = [{"role": "system", "content": system}, *history]
        spec = [{"type": "function", "function": {"name": t.name, "description": t.description,
                                                  "parameters": t.parameters}} for t in tools]
        by_name = {t.name: t for t in tools}
        trace: list[dict] = []
        async with httpx.AsyncClient(timeout=120) as c:
            for _ in range(max_steps):
                body: dict = {"model": self.model, "messages": msgs, "temperature": 0.3}
                if spec:
                    body["tools"] = spec
                r = await c.post(f"{base}/chat/completions", headers=headers, json=body)
                r.raise_for_status()
                msg = r.json()["choices"][0]["message"]
                calls = msg.get("tool_calls") or []
                if not calls:
                    return AgentResult(msg.get("content") or "", trace, self.provider, self.model)
                msgs.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
                for call in calls:
                    fn = call["function"]
                    args = fn.get("arguments") or "{}"
                    args = json.loads(args) if isinstance(args, str) else args
                    out = await by_name[fn["name"]].call(args) if fn["name"] in by_name else '{"error":"unknown tool"}'
                    trace.append({"tool": fn["name"], "args": args})
                    msgs.append({"role": "tool", "tool_call_id": call.get("id", fn["name"]), "content": out})
        return AgentResult("Je n'ai pas pu terminer l'analyse, réessayez.", trace, self.provider, self.model)

    # ---------------------------------------------------------- Anthropic
    async def _run_anthropic(self, system, history, tools, max_steps) -> AgentResult:
        headers = {"x-api-key": self.s.anthropic_api_key, "anthropic-version": "2023-06-01",
                   "content-type": "application/json"}
        msgs = [dict(m) for m in history]
        spec = [{"name": t.name, "description": t.description, "input_schema": t.parameters} for t in tools]
        by_name = {t.name: t for t in tools}
        trace: list[dict] = []
        async with httpx.AsyncClient(timeout=120) as c:
            for _ in range(max_steps):
                body: dict = {"model": self.model, "max_tokens": 1200, "system": system, "messages": msgs}
                if spec:
                    body["tools"] = spec
                r = await c.post("https://api.anthropic.com/v1/messages", headers=headers, json=body)
                r.raise_for_status()
                data = r.json()
                blocks = data["content"]
                uses = [b for b in blocks if b["type"] == "tool_use"]
                if not uses:
                    text = "".join(b.get("text", "") for b in blocks if b["type"] == "text")
                    return AgentResult(text, trace, self.provider, self.model)
                msgs.append({"role": "assistant", "content": blocks})
                results = []
                for u in uses:
                    out = await by_name[u["name"]].call(u["input"]) if u["name"] in by_name else '{"error":"unknown tool"}'
                    trace.append({"tool": u["name"], "args": u["input"]})
                    results.append({"type": "tool_result", "tool_use_id": u["id"], "content": out})
                msgs.append({"role": "user", "content": results})
        return AgentResult("Je n'ai pas pu terminer l'analyse, réessayez.", trace, self.provider, self.model)
