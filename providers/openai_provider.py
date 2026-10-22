"""OpenAI provider (official SDK). Also serves OpenAI-compatible local servers
(llama.cpp `llama-server`) via `base_url`.

No sampling parameters are sent: every model runs at its provider default.
"""

import argparse
import os

from .base import Provider, ProviderError


class OpenAIProvider(Provider):
    name = "openai"

    def __init__(self, model: str, base_url: str | None = None, api_key: str | None = None,
                 api: str | None = None, timeout: float = 180, **_):
        try:
            import openai
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("pip install openai") from e
        self._openai = openai
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set (add it to .env)")
        self.client = openai.OpenAI(api_key=key, base_url=base_url, timeout=timeout, max_retries=0)
        self.model = model
        self.base_url = base_url
        # The official API is used through the Responses API (as in RoboHarm);
        # local servers through Chat Completions.
        self.api = api or ("chat" if base_url else "responses")
        self._reported = None
        self._fingerprint = None
        self._effort = None
        self._usage = None

    def info(self) -> dict:
        return {"model_requested": self.model, "model_reported": self._reported,
                "system_fingerprint": self._fingerprint, "reasoning_effort": self._effort, "api": self.api, "base_url": self.base_url,
                "temperature": "provider default (not set)", "sdk_version": self._openai.__version__}

    def last_call_meta(self) -> dict:
        return {"usage": self._usage} if self._usage else {}

    def step(self, messages):
        o = self._openai
        try:
            if self.api == "responses":
                r = self.client.responses.create(model=self.model, input=messages)
                self._reported = r.model
                self._effort = getattr(getattr(r, "reasoning", None), "effort", None)
                self._usage = r.usage.model_dump() if r.usage else None
                return r.output_text or ""
            r = self.client.chat.completions.create(model=self.model, messages=messages)
            self._reported = r.model
            self._fingerprint = getattr(r, "system_fingerprint", None)
            self._usage = r.usage.model_dump() if r.usage else None
            return r.choices[0].message.content or ""
        except o.RateLimitError as e:
            raise ProviderError(f"rate limit: {e}", retry_after=30) from e
        except (o.APIConnectionError, o.APITimeoutError, o.InternalServerError) as e:
            raise ProviderError(f"transient: {e}", retry_after=10) from e


def _list_models():
    from dotenv import load_dotenv
    load_dotenv()
    import openai
    for m in sorted(openai.OpenAI().models.list(), key=lambda m: m.id):
        print(m.id)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="list models available to OPENAI_API_KEY")
    if ap.parse_args().list:
        _list_models()
