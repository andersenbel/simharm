"""Common provider interface."""


class ProviderError(Exception):
    """A call failed in a way that says nothing about model behaviour.

    `retry_after` (seconds) is set for transient failures such as rate limits.
    The runner retries these; the trial is not logged until it completes.
    """

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class Provider:
    name = "base"

    def start_trial(self, context: dict) -> None:
        """Called before each trial. `context` holds task, condition, trial key."""

    def end_trial(self) -> None:
        """Called after each trial, also on failure."""

    def step(self, messages: list[dict]) -> str:
        """messages: [{"role": "system"|"user"|"assistant", "content": str}, ...]."""
        raise NotImplementedError

    def info(self) -> dict:
        """Model name as reported by the provider, settings and versions."""
        return {}
