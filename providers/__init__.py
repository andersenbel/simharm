"""Provider registry."""

from .base import Provider, ProviderError


def make_provider(cfg: dict) -> Provider:
    kind = cfg["provider"]
    opts = {k: v for k, v in cfg.items() if k not in ("name", "provider", "workers")}
    if kind == "mock":
        from .mock import MockProvider
        return MockProvider(**opts)
    if kind == "openai":
        from .openai_provider import OpenAIProvider
        return OpenAIProvider(**opts)
    if kind == "claude_cli":
        from .claude_cli import ClaudeCLIProvider
        return ClaudeCLIProvider(**opts)
    if kind == "anthropic_api":
        from .anthropic_api import AnthropicAPIProvider
        return AnthropicAPIProvider(**opts)
    raise ValueError(f"unknown provider {kind!r}")


__all__ = ["Provider", "ProviderError", "make_provider"]
