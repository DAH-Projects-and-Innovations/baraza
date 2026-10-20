import json
import logging

import httpx
import pytest

from app.llm.client import LLMClient, LLMSettings
from app.llm.errors import (
    ContextTooLongError, LLMAuthError, LLMServerError, LLMTimeoutError,
    ModelUnreachableError, OutputTruncatedError, QuotaExceededError,
)

OK = {"choices": [{"message": {"content": "bonjour"}, "finish_reason": "stop"}]}
MSGS = [{"role": "user", "content": "SECRET-PROMPT"}]


def make_client(handler, **kw):
    sleeps: list[float] = []

    async def fake_sleep(d):
        sleeps.append(d)

    settings = LLMSettings(base_url="http://llm.test/v1", model="m", jitter=False, **kw)
    client = LLMClient(settings, transport=httpx.MockTransport(handler), sleep=fake_sleep)
    return client, sleeps


async def test_success():
    client, sleeps = make_client(lambda r: httpx.Response(200, json=OK))
    assert await client.complete(MSGS) == "bonjour"
    assert sleeps == []


async def test_payload_has_max_tokens_and_json_mode():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, json=OK)

    client, _ = make_client(handler, max_output_tokens=123)
    await client.complete(MSGS, json_mode=True)
    assert seen["max_tokens"] == 123
    assert seen["response_format"] == {"type": "json_object"}


async def test_retry_429_then_success_with_exponential_backoff():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(429) if len(calls) < 3 else httpx.Response(200, json=OK)

    client, sleeps = make_client(handler)
    assert await client.complete(MSGS) == "bonjour"
    assert sleeps == [1.0, 2.0]


async def test_retry_after_header_is_respected():
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "7"})
        return httpx.Response(200, json=OK)

    client, sleeps = make_client(handler)
    await client.complete(MSGS)
    assert sleeps == [7.0]


async def test_5xx_exhausts_retries():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503)

    client, sleeps = make_client(handler, max_retries=2)
    with pytest.raises(LLMServerError):
        await client.complete(MSGS)
    assert len(calls) == 3 and len(sleeps) == 2


async def test_timeout_is_retried_then_mapped():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    client, _ = make_client(handler, max_retries=1)
    with pytest.raises(LLMTimeoutError):
        await client.complete(MSGS)


async def test_unreachable_model():
    def handler(request):
        raise httpx.ConnectError("down", request=request)

    client, _ = make_client(handler, max_retries=1)
    with pytest.raises(ModelUnreachableError):
        await client.complete(MSGS)


async def test_context_too_long_not_retried():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(400, json={"error": {"code": "context_length_exceeded"}})

    client, sleeps = make_client(handler)
    with pytest.raises(ContextTooLongError):
        await client.complete(MSGS)
    assert len(calls) == 1 and sleeps == []


async def test_insufficient_quota_not_retried():
    client, sleeps = make_client(
        lambda r: httpx.Response(429, json={"error": {"code": "insufficient_quota"}})
    )
    with pytest.raises(QuotaExceededError):
        await client.complete(MSGS)
    assert sleeps == []


async def test_rate_limit_persistent_becomes_quota_error():
    client, _ = make_client(lambda r: httpx.Response(429), max_retries=1)
    with pytest.raises(QuotaExceededError):
        await client.complete(MSGS)


async def test_auth_error_not_retried():
    client, sleeps = make_client(lambda r: httpx.Response(401))
    with pytest.raises(LLMAuthError):
        await client.complete(MSGS)
    assert sleeps == []


async def test_truncated_output():
    body = {"choices": [{"message": {"content": "{"}, "finish_reason": "length"}]}
    client, _ = make_client(lambda r: httpx.Response(200, json=body))
    with pytest.raises(OutputTruncatedError):
        await client.complete(MSGS)


async def test_prompts_and_responses_never_logged_by_default(caplog):
    caplog.set_level(logging.DEBUG)
    client, _ = make_client(lambda r: httpx.Response(200, json=OK))
    await client.complete(MSGS)
    assert "SECRET-PROMPT" not in caplog.text and "bonjour" not in caplog.text


async def test_debug_flag_enables_content_logging(caplog):
    caplog.set_level(logging.DEBUG)
    client, _ = make_client(lambda r: httpx.Response(200, json=OK), debug_log_content=True)
    await client.complete(MSGS)
    assert "SECRET-PROMPT" in caplog.text


# ---------------- #82 : choix du format de sortie ----------------

SCHEMA = {"type": "object", "properties": {"a": {"type": "string"}}}


def format_recorder(reject=()):
    """Faux serveur qui note le response_format reçu et refuse ceux listés dans `reject`."""
    seen = []

    def handler(request):
        rf = json.loads(request.content).get("response_format")
        kind = rf["type"] if rf else "none"
        seen.append(kind)
        if kind in reject:
            return httpx.Response(400, json={"error": {"message": f"response_format {kind} is not supported"}})
        return httpx.Response(200, json=OK)

    return handler, seen


async def test_auto_prefers_json_schema_when_supported():
    handler, seen = format_recorder()
    client, _ = make_client(handler)
    await client.complete(MSGS, json_mode=True, json_schema=SCHEMA)
    assert seen == ["json_schema"] and client.last_response_format == "json_schema"


async def test_schema_payload_contains_the_schema():
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json=OK)

    client, _ = make_client(handler)
    await client.complete(MSGS, json_mode=True, json_schema=SCHEMA)
    assert bodies[0]["response_format"]["json_schema"]["schema"] == SCHEMA


async def test_fallback_to_json_object_when_schema_rejected():
    handler, seen = format_recorder(reject=("json_schema",))
    client, sleeps = make_client(handler)
    assert await client.complete(MSGS, json_mode=True, json_schema=SCHEMA) == "bonjour"
    assert seen == ["json_schema", "json_object"] and sleeps == []   # pas de retry inutile
    assert client.last_response_format == "json_object"


async def test_refusal_is_remembered_for_next_calls():
    handler, seen = format_recorder(reject=("json_schema",))
    client, _ = make_client(handler)
    await client.complete(MSGS, json_mode=True, json_schema=SCHEMA)
    await client.complete(MSGS, json_mode=True, json_schema=SCHEMA)
    assert seen == ["json_schema", "json_object", "json_object"]


async def test_fallback_to_plain_prompt_when_nothing_supported():
    handler, seen = format_recorder(reject=("json_schema", "json_object"))
    client, _ = make_client(handler)
    await client.complete(MSGS, json_mode=True, json_schema=SCHEMA)
    assert seen == ["json_schema", "json_object", "none"]


async def test_forced_mode_does_not_fall_back():
    from app.llm.errors import ResponseFormatUnsupportedError

    handler, seen = format_recorder(reject=("json_object",))
    client, _ = make_client(handler, structured_output="json_object")
    with pytest.raises(ResponseFormatUnsupportedError):
        await client.complete(MSGS, json_mode=True, json_schema=SCHEMA)
    assert seen == ["json_object"]


async def test_none_mode_sends_no_response_format():
    handler, seen = format_recorder()
    client, _ = make_client(handler, structured_output="none")
    await client.complete(MSGS, json_mode=True, json_schema=SCHEMA)
    assert seen == ["none"]


async def test_context_error_is_not_mistaken_for_format_error():
    handler = lambda r: httpx.Response(400, json={"error": {"message": "context_length_exceeded for response_format call"}})
    client, _ = make_client(handler)
    with pytest.raises(ContextTooLongError):
        await client.complete(MSGS, json_mode=True, json_schema=SCHEMA)
