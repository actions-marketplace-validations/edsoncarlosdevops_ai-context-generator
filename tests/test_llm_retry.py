import pytest
from openai import APIConnectionError, APIStatusError, RateLimitError

from ai_context_generator.llm_client import LLMClient, LLMError


def _client(**kwargs) -> LLMClient:
    return LLMClient("sk-test", "test-model", "https://example.invalid/v1", **kwargs)


class _Request:
    """Minimal stand-in for the SDK's request object.

    The tests deliberately avoid importing the HTTP library directly: the openai
    SDK has swapped it before (httpx → httpx2) and these tests only care about
    this client's own retry and error-classification logic.
    """

    method = "POST"
    url = "https://example.invalid/v1"


class _Response:
    def __init__(self, status_code: int):
        self.status_code = status_code
        self.request = _Request()
        self.headers: dict[str, str] = {}


def _status_error(status: int) -> APIStatusError:
    return APIStatusError("boom", response=_Response(status), body=None)  # type: ignore[arg-type]


def _connection_error() -> APIConnectionError:
    return APIConnectionError(request=_Request())  # type: ignore[arg-type]


class _Choice:
    def __init__(self, content: str | None, finish_reason: str = "stop"):
        self.message = type("M", (), {"content": content})()
        self.finish_reason = finish_reason


class _Completion:
    def __init__(self, content: str | None, finish_reason: str = "stop", usage=None):
        self.choices = [_Choice(content, finish_reason)] if content is not None else []
        self.usage = usage


def _patch(client: LLMClient, side_effect) -> list[int]:
    calls: list[int] = []

    def create(**kwargs):
        calls.append(1)
        result = side_effect(len(calls))
        if isinstance(result, Exception):
            raise result
        return result

    client.client.chat.completions.create = create  # type: ignore[method-assign]
    return calls


def test_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _: None)
    client = _client()
    calls = _patch(
        client,
        lambda n: _connection_error() if n == 1 else _Completion("# Rules\n"),
    )

    assert client.generate("prompt") == "# Rules"
    assert len(calls) == 2


def test_gives_up_after_max_retries(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr("time.sleep", slept.append)
    client = _client(max_retries=3)
    _patch(client, lambda n: _status_error(503))

    with pytest.raises(LLMError, match="after 3 attempts"):
        client.generate("prompt")

    # No pointless sleep after the final attempt: 3 attempts → 2 backoffs.
    assert slept == [1, 2]


def test_rate_limit_is_retryable(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _: None)
    client = _client(max_retries=2)
    _patch(
        client,
        lambda n: (
            RateLimitError("slow down", response=_Response(429), body=None)
            if n == 1
            else _Completion("ok")
        ),
    )
    assert client.generate("p") == "ok"


@pytest.mark.parametrize(
    ("status", "message"),
    [(401, "Authentication failed"), (403, "Authentication failed"), (404, "not found")],
)
def test_terminal_status_codes_are_not_retried(status: int, message: str):
    client = _client()
    calls = _patch(client, lambda n: _status_error(status))

    with pytest.raises(LLMError, match=message):
        client.generate("prompt")
    assert len(calls) == 1


def test_truncated_output_raises_actionable_error():
    client = _client()
    _patch(client, lambda n: _Completion("partial", finish_reason="length"))

    with pytest.raises(LLMError, match="truncated"):
        client.generate("prompt")


def test_empty_choices_raise():
    client = _client()
    _patch(client, lambda n: _Completion(None))

    with pytest.raises(LLMError, match="no choices"):
        client.generate("prompt")


def test_token_usage_is_recorded():
    client = _client()
    usage = type("U", (), {"prompt_tokens": 120, "completion_tokens": 30})()
    _patch(client, lambda n: _Completion("ok", usage=usage))

    client.generate("prompt")

    assert client.last_usage.prompt_tokens == 120
    assert client.last_usage.total_tokens == 150


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("```markdown\n# Title\n```", "# Title"),
        ("```md\n# Title\n```", "# Title"),
        ("```\n# Title\n```", "# Title"),
        ("  # Title  ", "# Title"),
    ],
)
def test_markdown_fences_are_stripped(raw: str, expected: str):
    assert LLMClient._sanitize(raw) == expected
