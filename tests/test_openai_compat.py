"""
Tests for the OpenAI-compatible backend (vLLM on AMD ROCm).

No server is needed: httpx.MockTransport stands in for vLLM, and each test
asserts on both sides of the translation — the request body the adapter sends
and the Anthropic-shaped response the AI layer reads back.
"""

import json

import anthropic
import httpx
import pytest

from ai.openai_compat import OpenAICompatClient

_TOOL = {
    "name": "extract_design_spec",
    "description": "Extract a design spec.",
    "input_schema": {"type": "object", "properties": {"intent": {"type": "string"}}},
}


def _client(handler) -> OpenAICompatClient:
    return OpenAICompatClient(
        base_url="http://vllm.test/v1",
        transport=httpx.MockTransport(handler),
    )


def _completion(message: dict, finish_reason: str = "stop") -> dict:
    return {
        "model": "Qwen/Qwen2.5-7B-Instruct",
        "choices": [{"message": message, "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 7},
    }


def test_forced_tool_call_round_trip():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_completion({
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {"name": "extract_design_spec", "arguments": '{"intent": "blink an LED"}'},
            }],
        }, finish_reason="tool_calls"))

    response = _client(handler).messages.create(
        model="Qwen/Qwen2.5-7B-Instruct",
        max_tokens=512,
        system="You are a circuit designer.",
        tools=[_TOOL],
        tool_choice={"type": "tool", "name": "extract_design_spec"},
        messages=[{"role": "user", "content": "blink an LED"}],
    )

    assert seen["path"] == "/v1/chat/completions"
    body = seen["body"]
    assert body["messages"][0] == {"role": "system", "content": "You are a circuit designer."}
    assert body["tools"][0]["function"]["parameters"] == _TOOL["input_schema"]
    assert body["tool_choice"] == {"type": "function", "function": {"name": "extract_design_spec"}}

    assert response.content[0].input == {"intent": "blink an LED"}
    assert response.stop_reason == "tool_use"


def test_text_response_and_truncation_maps_to_max_tokens():
    def handler(request):
        return httpx.Response(200, json=_completion({"role": "assistant", "content": "R3 sets LED current."}, "length"))

    response = _client(handler).messages.create(
        model="m", max_tokens=10, messages=[{"role": "user", "content": "explain"}],
    )
    assert response.content[0].text == "R3 sets LED current."
    # circuit_reasoner.py fails fast on this rather than retrying a truncated call
    assert response.stop_reason == "max_tokens"


def test_retry_correction_turns_become_tool_messages():
    """The reasoner's correction pair (tool_use + tool_result) must survive translation."""
    seen: dict = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_completion({"role": "assistant", "content": "ok"}))

    _client(handler).messages.create(
        model="m",
        max_tokens=10,
        messages=[
            {"role": "user", "content": "design it"},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "corr", "name": "generate_circuit_ir", "input": {"a": 1}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "corr", "content": "Fix field x"},
            ]},
        ],
    )

    msgs = seen["body"]["messages"]
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["tool_calls"][0]["function"] == {"name": "generate_circuit_ir", "arguments": '{"a": 1}'}
    assert msgs[2] == {"role": "tool", "tool_call_id": "corr", "content": "Fix field x"}


def test_http_error_raises_anthropic_api_error():
    def handler(request):
        return httpx.Response(500, text="model not loaded")

    with pytest.raises(anthropic.APIStatusError):
        _client(handler).messages.create(model="m", max_tokens=10, messages=[{"role": "user", "content": "x"}])


def test_timeout_raises_anthropic_timeout_error():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(anthropic.APITimeoutError):
        _client(handler).messages.create(model="m", max_tokens=10, messages=[{"role": "user", "content": "x"}])


def test_malformed_tool_arguments_raise_json_error():
    """The reasoner's retry loop catches JSONDecodeError and re-prompts."""
    def handler(request):
        return httpx.Response(200, json=_completion({
            "role": "assistant",
            "tool_calls": [{"id": "c", "function": {"name": "t", "arguments": "{not json"}}],
        }, "tool_calls"))

    with pytest.raises(json.JSONDecodeError):
        _client(handler).messages.create(model="m", max_tokens=10, messages=[{"role": "user", "content": "x"}])
