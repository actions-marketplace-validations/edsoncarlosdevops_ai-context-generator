import time
from openai import OpenAI, OpenAIError

class LLMError(Exception):
    pass

class LLMClient:
    def __init__(self, api_key: str, model: str, base_url: str):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def generate(self, prompt: str) -> str:
        max_retries = 3
        backoff_factor = 2

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a senior technical writer and software architect."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2
                )
                return response.choices[0].message.content or ""
            except OpenAIError as e:
                if "rate limit" in str(e).lower() or attempt < max_retries - 1:
                    sleep_time = backoff_factor ** attempt
                    time.sleep(sleep_time)
                else:
                    raise LLMError(f"LLM Generation failed: {e}") from e
        
        raise LLMError("Exceeded max retries for LLM generation")
