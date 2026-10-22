"""Optional: Claude through the Anthropic API. Used only if ANTHROPIC_API_KEY is
set and a model entry selects `provider: anthropic_api`. Requires `pip install anthropic`
(not a core dependency)."""

import os

from .base import Provider, ProviderError


class AnthropicAPIProvider(Provider):
    name = "anthropic_api"

    def __init__(self, model: str, max_tokens: int = 4096, **_):
        import anthropic
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        self._a = anthropic
        self.client = anthropic.Anthropic(max_retries=0)
        self.model, self.max_tokens, self._reported = model, max_tokens, None

    def info(self) -> dict:
        return {"model_requested": self.model, "model_reported": self._reported,
                "temperature": "provider default (not set)", "sdk_version": self._a.__version__}

    def step(self, messages):
        try:
            r = self.client.messages.create(model=self.model, max_tokens=self.max_tokens,
                                            system=messages[0]["content"], messages=messages[1:])
        except (self._a.RateLimitError, self._a.APIConnectionError, self._a.InternalServerError) as e:
            raise ProviderError(str(e), retry_after=30) from e
        self._reported = r.model
        return "".join(b.text for b in r.content if b.type == "text")
