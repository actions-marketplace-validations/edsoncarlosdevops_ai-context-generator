import time
from openai import OpenAI, RateLimitError, APIStatusError, APIConnectionError


class LLMError(Exception):
    pass


class LLMClient:
    """Calls any OpenAI-compatible LLM endpoint with smart retry logic."""

    # Only these error types warrant a retry
    _RETRYABLE = (RateLimitError, APIConnectionError)

    def __init__(self, api_key: str, model: str, base_url: str, max_tokens: int = 4096):
        self.model = model
        self.max_tokens = max_tokens
        self.client = OpenAI(api_key=api_key, base_url=base_url)

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
                return response.choices[0].message.content or ""

            except self._RETRYABLE as e:
                last_error = e
                wait = 2 ** attempt  # 1s, 2s, 4s
                print(f"  [retry {attempt + 1}/{max_retries}] Rate limit / connection error — retrying in {wait}s")
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
                    wait = 2 ** attempt
                    print(f"  [retry {attempt + 1}/{max_retries}] Server error {e.status_code} — retrying in {wait}s")
                    time.sleep(wait)
                else:
                    raise LLMError(f"LLM API error (HTTP {e.status_code}): {e.message}") from e

            except Exception as e:
                raise LLMError(f"Unexpected LLM error: {e}") from e

        raise LLMError(
            f"LLM generation failed after {max_retries} retries. Last error: {last_error}"
        )
