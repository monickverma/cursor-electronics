"""OpenAI-compatible backend for open models — used to run Circuit OS on AMD GPUs.

vLLM on ROCm (AMD Developer Cloud, AMD Instinct) serves any Hugging Face model
behind an OpenAI-compatible /v1/chat/completions endpoint. This module exposes
that endpoint through the small slice of the Anthropic SDK surface the AI layer
actually uses:

    client.messages.create(model, max_tokens, system, tools, tool_choice, messages)
    response.content[0].input | .text
    response.stop_reason

so intent_parser, circuit_reasoner, patcher and explainer run unchanged against
either provider. The One Rule still holds: a forced tool_choice becomes a named
function call, which vLLM enforces with guided decoding, so the model can only
emit JSON matching the tool's input_schema — and that JSON still goes through
Pydantic and the rule engine before any compiler sees it.

Errors are re-raised as the anthropic exception types the routes already catch
(APITimeoutError → 504, APIError → 503), so no call site needs a second branch.
"""

import json
from dataclasses import dataclass
from typing import Any, Optional

import anthropic
import httpx

# OpenAI finish_reason → Anthropic stop_reason. circuit_reasoner.py relies on
# "max_tokens" to detect a truncated tool call instead of retrying it.
_STOP_REASONS = {
    "length": "max_tokens",
    "tool_calls": "tool_use",
    "stop": "end_turn",
}


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict
    type: str = "tool_use"


@dataclass
class TextBlock:
    text: str
    type: str = "text"


@dataclass
class Usage:
    input_tokens: int
    output_tokens: int


@dataclass
class Message:
    content: list
    stop_reason: str
    model: str
    usage: Usage


def _to_openai_tools(tools: list[dict]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t["input_schema"],
            },
        }
        for t in tools
    ]


def _to_openai_tool_choice(tool_choice: dict) -> Any:
    kind = tool_choice.get("type")
    if kind == "tool":
        return {"type": "function", "function": {"name": tool_choice["name"]}}
    if kind == "any":
        return "required"
    return "auto"


def _to_openai_messages(system: Optional[str], messages: list[dict]) -> list[dict]:
    """Flatten Anthropic content blocks into OpenAI chat messages.

    Anthropic packs tool calls and tool results into content blocks; OpenAI
    wants tool calls on the assistant message and each result as its own
    role="tool" message. The retry loop in circuit_reasoner.py produces exactly
    that pair, so it has to survive the translation intact.
    """
    out: list[dict] = []
    if system:
        out.append({"role": "system", "content": system})

    for msg in messages:
        role, content = msg["role"], msg["content"]
        if isinstance(content, str):
            out.append({"role": role, "content": content})
            continue

        texts: list[str] = []
        tool_calls: list[dict] = []
        tool_results: list[dict] = []
        for block in content:
            kind = block.get("type")
            if kind == "text":
                texts.append(block["text"])
            elif kind == "tool_use":
                tool_calls.append({
                    "id": block["id"],
                    "type": "function",
                    "function": {"name": block["name"], "arguments": json.dumps(block["input"])},
                })
            elif kind == "tool_result":
                result = block.get("content", "")
                if not isinstance(result, str):
                    result = json.dumps(result)
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": block["tool_use_id"],
                    "content": result,
                })

        if role == "assistant":
            entry: dict = {"role": "assistant", "content": "\n".join(texts) or None}
            if tool_calls:
                entry["tool_calls"] = tool_calls
            out.append(entry)
        else:
            out.extend(tool_results)
            if texts:
                out.append({"role": "user", "content": "\n".join(texts)})
    return out


def _to_message(data: dict, model: str) -> Message:
    choice = data["choices"][0]
    msg = choice.get("message") or {}
    blocks: list = []

    for call in msg.get("tool_calls") or []:
        fn = call["function"]
        args = fn.get("arguments") or "{}"
        # A malformed argument string raises json.JSONDecodeError, which the
        # reasoner's retry loop already treats as a correctable model error.
        parsed = json.loads(args) if isinstance(args, str) else args
        blocks.append(ToolUseBlock(id=call.get("id") or "call_0", name=fn["name"], input=parsed))

    if not blocks:
        blocks.append(TextBlock(text=msg.get("content") or ""))

    usage = data.get("usage") or {}
    return Message(
        content=blocks,
        stop_reason=_STOP_REASONS.get(choice.get("finish_reason"), "end_turn"),
        model=data.get("model", model),
        usage=Usage(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)),
    )


class _Messages:
    def __init__(self, http: httpx.Client):
        self._http = http

    def create(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict],
        system: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        tool_choice: Optional[dict] = None,
        temperature: float = 0.0,
    ) -> Message:
        payload: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": _to_openai_messages(system, messages),
        }
        if tools:
            payload["tools"] = _to_openai_tools(tools)
            if tool_choice:
                payload["tool_choice"] = _to_openai_tool_choice(tool_choice)

        try:
            resp = self._http.post("/chat/completions", json=payload)
            resp.raise_for_status()
        except httpx.TimeoutException as exc:
            raise anthropic.APITimeoutError(request=exc.request) from exc
        except httpx.HTTPStatusError as exc:
            raise anthropic.APIStatusError(
                f"OpenAI-compatible server returned {exc.response.status_code}: {exc.response.text[:500]}",
                response=exc.response,
                body=None,
            ) from exc
        except httpx.HTTPError as exc:
            raise anthropic.APIConnectionError(message=str(exc), request=exc.request) from exc

        return _to_message(resp.json(), model)


class OpenAICompatClient:
    """Drop-in for anthropic.Anthropic, backed by an OpenAI-compatible server."""

    def __init__(
        self,
        base_url: str,
        api_key: str = "EMPTY",
        timeout: float = 45.0,
        max_retries: int = 1,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key or 'EMPTY'}"},
            timeout=timeout,
            transport=transport or httpx.HTTPTransport(retries=max_retries),
        )
        self.messages = _Messages(self._http)
