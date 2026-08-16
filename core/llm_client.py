import re
import time

from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError


class LLMError(Exception):
    pass


class LLMClient:
    """Calls any OpenAI-compatible LLM endpoint with smart retry logic."""

    # Only these error types warrant a retry
    _RETRYABLE = (RateLimitError, APIConnectionError)

    _FENCE_RE = re.compile(r"^```(?:markdown|md)?\s*\n?(.*?)\n?```\s*$", re.DOTALL)

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        max_tokens: int = 4096,
        timeout: float = 120.0,
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    @staticmethod
    def _sanitize(content: str | None) -> str:
        """Strip stray markdown fences and enforce a clean, non-empty result."""
        content = (content or "").strip()
        match = LLMClient._FENCE_RE.match(content)
        if match:
            content = match.group(1).strip()
        return content

    def generate(self, prompt: str) -> str:
        max_retries = 3
        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a Principal Software Architect specializing in "
                                "AI-assisted development governance. You produce concise, "
                                "actionable Markdown documentation."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                    max_tokens=self.max_tokens,
                )
                choice = response.choices[0]
                if choice.finish_reason == "length":
                    raise LLMError(
                        f"LLM output was truncated (max_tokens={self.max_tokens}). "
                        "Increase max_tokens in your config to fit the requested line budget."
                    )
                content = self._sanitize(choice.message.content)
                if not content:
                    raise LLMError("LLM returned empty content.")
                return content

            except self._RETRYABLE as e:
                last_error = e
                wait = 2**attempt  # 1s, 2s, 4s
                print(
                    f"  [retry {attempt + 1}/{max_retries}] Rate limit / connection error — retrying in {wait}s"
                )
                time.sleep(wait)

            except APIStatusError as e:
                # 401 Unauthorized, 403 Forbidden — never retry
                if e.status_code in (401, 403):
                    raise LLMError(
                        f"Authentication failed (HTTP {e.status_code}). "
                        "Check your API key and provider base URL."
                    ) from e
                # 5xx Server errors — retry
                if e.status_code >= 500:
                    last_error = e
                    wait = 2**attempt
                    print(
                        f"  [retry {attempt + 1}/{max_retries}] Server error {e.status_code} — retrying in {wait}s"
                    )
                    time.sleep(wait)
                else:
                    raise LLMError(f"LLM API error (HTTP {e.status_code}): {e.message}") from e

            except LLMError:
                raise

            except Exception as e:
                raise LLMError(f"Unexpected LLM error: {e}") from e

        raise LLMError(
            f"LLM generation failed after {max_retries} retries. Last error: {last_error}"
        )
