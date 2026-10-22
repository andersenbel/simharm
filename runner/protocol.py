"""Parsing of model replies into one JSON action.

A reply is accepted if exactly one JSON object with a valid action can be found
in it. Surrounding prose or a code fence is tolerated and recorded as
`extra_text`, so models are not penalised for formatting habits; two or more
JSON objects, an unknown action or missing arguments make the reply invalid.
"""

import json
from dataclasses import dataclass

from sim.world import ACTION_ARGS


@dataclass
class Parsed:
    action: dict | None
    error: str | None
    extra_text: bool = False


def _json_objects(text: str) -> list:
    """Top-level {...} spans that parse as JSON objects."""
    found, depth, start, in_str, esc = [], 0, None, False, False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"' and depth > 0:
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    found.append((obj, start, i + 1))
    return found


def _validate(obj: dict) -> str | None:
    action = obj.get("action")
    if action not in ACTION_ARGS:
        return f"unknown action {action!r}"
    args = obj.get("args", {})
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return "'args' must be an object"
    missing = [a for a in ACTION_ARGS[action] if not isinstance(args.get(a), str) or not args.get(a)]
    if missing:
        return f"missing argument(s) for {action}: {', '.join(missing)}"
    return None


def parse_reply(text: str) -> Parsed:
    objs = _json_objects(text or "")
    if not objs:
        return Parsed(None, "no JSON object found")
    if len(objs) > 1:
        return Parsed(None, f"{len(objs)} JSON objects found, expected exactly one")
    obj, start, end = objs[0]
    if err := _validate(obj):
        return Parsed(None, err)
    rest = (text[:start] + text[end:]).replace("```json", "").replace("```", "").strip()
    action = {"action": obj["action"], "args": obj.get("args") or {}}
    if "note" in obj:
        action["note"] = obj["note"]
    return Parsed(action, None, extra_text=bool(rest))
