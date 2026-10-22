"""Claude through Claude Code in headless mode (`claude -p`), no API key needed.

One CLI session per trial. The first step starts the session with our system
prompt; later steps `--resume` it and send only the newest user message, so the
model sees a real multi-turn conversation. Our code keeps the canonical history
and checks before every call that it matches what was sent to the session.

Known limitation (docs/limitations.md): even with --system-prompt the CLI adds
an identity line, an environment block and account context to the system
prompt. Each trial runs in a fresh empty temporary directory so the working
directory reveals nothing about the experiment.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from .base import Provider, ProviderError

BASE_FLAGS = [
    "--tools", "",                 # no built-in tools
    "--strict-mcp-config",         # no MCP servers
    "--setting-sources", "",       # ignore user/project/local settings (hooks, CLAUDE.md)
    "--disable-slash-commands",    # no skills
    "--output-format", "json",
]
LIMIT_PAT = re.compile(r"usage limit|rate limit|limit reached|overloaded|try again", re.IGNORECASE)


def cli_version(binary="claude") -> str:
    try:
        return subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception as e:  # pragma: no cover
        return f"unknown ({e})"


class ClaudeCLIProvider(Provider):
    name = "claude_cli"

    def __init__(self, model: str, effort: str | None = None, binary: str = "claude",
                 timeout: float = 600, **_):
        self.model, self.effort, self.binary, self.timeout = model, effort, binary, timeout
        self.version = cli_version(binary)
        self._reported = None
        self._last_usage = None
        self.session_id = None
        self.cwd = None

    def info(self) -> dict:
        return {"model_requested": self.model, "model_reported": self._reported,
                "effort": self.effort or "CLI default", "temperature": "CLI default (not settable)",
                "cli_version": self.version, "flags": self.command(system="<system>", resume=False)[1:]}

    def command(self, system: str, resume: bool) -> list:
        cmd = [self.binary, "-p", "--system-prompt", system, "--model", self.model, *BASE_FLAGS]
        if self.effort:
            cmd += ["--effort", self.effort]
        sid = self.session_id or "<uuid>"
        cmd += ["--resume", sid] if resume else ["--session-id", sid]
        return cmd

    def start_trial(self, context: dict) -> None:
        self.session_id = str(uuid.uuid4())
        self.cwd = tempfile.mkdtemp(prefix="arm-")
        self._sent: list[dict] = []

    def end_trial(self) -> None:
        if self.cwd:
            # Remove the session transcript the CLI stored for this temp directory.
            real = os.path.realpath(self.cwd)
            proj = Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", real)
            shutil.rmtree(proj, ignore_errors=True)
            shutil.rmtree(self.cwd, ignore_errors=True)
        self.cwd = self.session_id = None

    def step(self, messages):
        system, convo = messages[0]["content"], messages[1:]
        if messages[0]["role"] != "system" or convo[-1]["role"] != "user":
            raise ValueError("expected [system, ..., user]")
        if convo[:-1] != self._sent:
            raise RuntimeError("history mismatch between runner and CLI session")
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}  # stay on the subscription
        proc = subprocess.run(self.command(system, resume=bool(self._sent)), input=convo[-1]["content"],
                              capture_output=True, text=True, cwd=self.cwd, env=env, timeout=self.timeout)
        try:
            out = json.loads(proc.stdout)
        except json.JSONDecodeError:
            raise ProviderError(f"CLI returned no JSON (exit {proc.returncode}): {proc.stderr[-500:] or proc.stdout[-500:]}",
                                retry_after=60)
        if out.get("is_error"):
            msg = str(out.get("result") or out)
            raise ProviderError(f"CLI error: {msg[:500]}", retry_after=900 if LIMIT_PAT.search(msg) else 60)
        text = out.get("result") or ""
        usage = out.get("modelUsage") or {}
        main = [m for m in usage if "haiku" not in m] or list(usage)
        self._reported = main[0] if main else self._reported
        self._last_usage = {"modelUsage": usage, "total_cost_usd_list_price": out.get("total_cost_usd")}
        self._sent = convo[:-1] + [convo[-1], {"role": "assistant", "content": text}]
        return text

    def last_call_meta(self) -> dict:
        return self._last_usage or {}
