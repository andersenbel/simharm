"""Deterministic offline provider for tests and dry runs."""

import hashlib
import json

from .base import Provider

BEHAVIORS = ["comply", "refuse", "refuse_midway", "text_refusal", "ambiguous_text", "garbage", "mixed"]


class MockProvider(Provider):
    name = "mock"

    def __init__(self, behavior: str = "comply", **_):
        if behavior not in BEHAVIORS:
            raise ValueError(f"unknown mock behavior {behavior!r}")
        self.behavior = behavior

    def start_trial(self, context: dict) -> None:
        self.plan = [a for a in context["oracle"] if a["action"] != "done"]
        self.condition = context["condition"]
        self.calls = 0
        self.mode = self.behavior
        if self.behavior == "mixed":
            key = json.dumps(context["key"], sort_keys=True).encode()
            options = ["comply", "comply", "refuse", "refuse_midway", "text_refusal", "garbage"]
            self.mode = options[int(hashlib.sha256(key).hexdigest(), 16) % len(options)]

    def info(self) -> dict:
        return {"model_reported": f"mock-{self.behavior}", "temperature": "n/a (deterministic)"}

    @staticmethod
    def _j(action, **args):
        return json.dumps({"action": action, "args": args})

    def step(self, messages):
        self.calls += 1
        last = messages[-1]["content"]
        if self.mode == "refuse":
            return self._j("refuse", reason="This could cause harm.")
        if self.mode == "text_refusal":
            return "I can't do that, it would be unsafe."
        if self.mode == "ambiguous_text":
            return "Are you sure? This seems risky."
        if self.mode == "garbage":
            return "pick the thing"
        if self.mode == "refuse_midway" and self.calls == 2:
            return self._j("refuse", reason="On reflection this is unsafe.")
        if self.condition == "C3":
            if last.startswith("Step:") or "\nStep:" in last:
                return json.dumps(self.plan.pop(0)) if self.plan else self._j("done")
            return self._j("done")
        return json.dumps(self.plan.pop(0)) if self.plan else self._j("done")
