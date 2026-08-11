from core.llm_client import LLMClient, LLMError


class _Msg:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content, finish_reason="stop"):
        self.message = _Msg(content)
        self.finish_reason = finish_reason


class _Response:
    def __init__(self, choice):
        self.choices = [choice]


def test_sanitize_strips_fences():
    assert LLMClient._sanitize("```markdown\n# Title\n```") == "# Title"
    assert LLMClient._sanitize("```\nplain\n```") == "plain"
    assert LLMClient._sanitize("  # Title  ") == "# Title"
    assert LLMClient._sanitize("") == ""
    assert LLMClient._sanitize(None) == ""


def _client_with_response(monkeypatch, response):
    client = LLMClient("sk-fake", "model", "http://localhost")
    monkeypatch.setattr(client.client.chat.completions, "create", lambda **kw: response)
    return client


def test_returns_sanitized_content(monkeypatch):
    client = _client_with_response(monkeypatch, _Response(_Choice("```md\nok\n```")))
    assert client.generate("p") == "ok"


def test_raises_on_truncated_output(monkeypatch):
    client = _client_with_response(monkeypatch, _Response(_Choice("...", "length")))
    try:
        client.generate("p")
        raise AssertionError("should have raised")
    except LLMError as e:
        assert "truncated" in str(e).lower()


def test_raises_on_empty_output(monkeypatch):
    client = _client_with_response(monkeypatch, _Response(_Choice("", "stop")))
    try:
        client.generate("p")
        raise AssertionError("should have raised")
    except LLMError as e:
        assert "empty" in str(e).lower()
