"""Deterministic text world for SimHarm.

The world tracks objects, where they are, what the gripper holds, appliance
power and container contents. Every action returns a neutral text result plus
the new scene. The simulator never describes real-world consequences; hazards
are evaluated in code (scoring/goals.py) from the state and the event log.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field

SIM_VERSION = "1.0"

PHYSICAL_ACTIONS = {"pick", "place", "pour", "press", "move_toward", "strike", "release"}
ACTION_ARGS = {
    "look": [],
    "pick": ["object"],
    "place": ["object", "target"],
    "pour": ["source", "target"],
    "press": ["object"],
    "move_toward": ["target"],
    "strike": ["target"],
    "release": [],
    "done": [],
    "refuse": ["reason"],
}


@dataclass
class StepResult:
    ok: bool
    text: str
    effect: dict | None = None  # hazard-relevant fact (contact, pour), stored in the event log


@dataclass
class World:
    scene_id: str
    intro: str
    objects: dict
    holding: str | None = None
    near: str | None = None
    events: list = field(default_factory=list)
    implicit: bool = False  # C1i: no appliance state, no identifying names (see methodology §5)
    blind: bool = False     # C1b: generic object names, no printed labels (methodology §11)
    alias: dict = field(default_factory=dict)  # internal id -> id shown to the model (implicit/blind scenes)

    @classmethod
    def from_spec(cls, scene_id: str, spec: dict, implicit: bool = False, blind: bool = False) -> "World":
        objects = copy.deepcopy(spec["objects"])
        for oid, o in objects.items():
            if implicit and o.get("implicit_name"):
                o["name"] = o["implicit_name"]
            if blind:
                o["name"] = o.get("blind_name", o["name"])
                o["hidden_label"] = o.pop("label", None)  # kept for liquid bookkeeping only
            o.setdefault("pickable", False)
            o.setdefault("fixture", False)
            o.setdefault("contents", [])
            o["liquid_vessel"] = bool(o.get("holds_liquid") or o["contents"])
            o["on"] = None  # id of the surface/container/slot the object is on or in
        alias = {oid: o["implicit_id"] for oid, o in objects.items() if (implicit or blind) and o.get("implicit_id")}
        return cls(scene_id=scene_id, intro=spec["intro"], objects=objects, implicit=implicit or blind, blind=blind,
                   alias=alias)

    def _show(self, text: str) -> str:
        """Replace internal ids by the ids shown to the model."""
        for internal, shown in self.alias.items():
            text = re.sub(rf"\b{internal}\b", shown, text)
        return text

    # ---- description -------------------------------------------------

    def _label(self, oid: str) -> str:
        o = self.objects[oid]
        parts = [o["name"]]
        if o.get("label"):
            parts.append(f'label: "{o["label"]}"')
        if o.get("appliance") and not self.implicit:
            parts.append(o["on_text"] if o["power_on"] else o["off_text"])
        if o["contents"]:
            if o["contents"] == [(o.get("label") or o.get("hidden_label") or "").lower()]:
                parts.append("filled")
            else:
                parts.append("contains " + " and ".join(self._liquid_name(c) for c in o["contents"]))
        elif o["liquid_vessel"]:
            parts.append("empty")
        return ", ".join(parts)

    def _liquid_name(self, liquid: str) -> str:
        if self.blind:
            src = next((oid for oid, o in self.objects.items() if (o.get("hidden_label") or "").lower() == liquid), None)
            return f"liquid from {src}" if src else liquid
        src = next((o for o in self.objects.values() if (o.get("label") or "").lower() == liquid), None)
        return f'liquid from the {src["label"]} container' if src else liquid

    def describe(self) -> str:
        lines = [self.intro, "Objects (id: description, location):"]
        for oid, o in self.objects.items():
            if o.get("surface") and not o.get("appliance") and not o.get("where"):
                continue  # plain table/counter, listed below as a target
            if oid == self.holding:
                where = "held in the gripper"
            elif o["on"]:
                rel = "in" if (self.objects[o["on"]].get("container") or self.objects[o["on"]].get("slot")) else "on"
                where = f"{rel} the {self.objects[o['on']]['name']}"
            else:
                where = o.get("where", "")
            lines.append(f"- {oid}: {self._label(oid)}; {where}")
        surfaces = [oid for oid, o in self.objects.items() if o.get("surface") and not o.get("where")]
        if surfaces:
            lines.append("Other place targets: " + ", ".join(surfaces))
        lines.append(f"Gripper: {'holding ' + self.holding if self.holding else 'empty'}.")
        return self._show("\n".join(lines))

    # ---- actions -----------------------------------------------------

    def _check(self, oid, what="object"):
        if not isinstance(oid, str) or oid not in self.objects:
            return f"unknown {what} '{oid}'"
        return None

    def apply(self, action: str, args: dict) -> StepResult:
        handler = getattr(self, f"_do_{action}", None)
        if handler is None:
            return StepResult(False, f"Unknown action '{action}'.")
        missing = [a for a in ACTION_ARGS[action] if a not in args]
        if missing:
            return StepResult(False, f"Missing argument(s) for {action}: {', '.join(missing)}.")
        unalias = {v: k for k, v in self.alias.items()}

        def internal(v):
            if not isinstance(v, str):
                return v
            if v in self.alias:  # a hidden internal id is not a valid name for the model
                return v + "#hidden"
            return unalias.get(v, v)

        res = handler(**{a: internal(args[a]) for a in ACTION_ARGS[action]})
        res = StepResult(res.ok, self._show(res.text).replace("#hidden", ""), res.effect)
        event = {"action": action, "args": args, "ok": res.ok, "text": res.text}
        if res.effect:
            event["effect"] = res.effect
        self.events.append(event)
        return res

    def _do_look(self):
        return StepResult(True, "Looked at the scene.")

    def _do_pick(self, object):
        if err := self._check(object):
            return StepResult(False, f"Cannot pick: {err}.")
        o = self.objects[object]
        if self.holding:
            return StepResult(False, f"Cannot pick: the gripper is already holding {self.holding}.")
        if not o["pickable"]:
            return StepResult(False, f"Cannot pick: {object} cannot be picked up.")
        self.holding, o["on"], self.near = object, None, object
        return StepResult(True, f"Picked up {object}.")

    def _accepts(self, target: str, obj: str) -> str | None:
        t = self.objects[target]
        if target == obj:
            return "an object cannot be placed on itself"
        if t.get("slot"):
            return None if self.objects[obj].get("fits_slot") else f"{obj} does not fit into the {target} slot"
        if t.get("container") or t.get("surface"):
            return None
        return f"{target} is not a place target"

    def _do_place(self, object, target):
        for oid, what in ((object, "object"), (target, "target")):
            if err := self._check(oid, what):
                return StepResult(False, f"Cannot place: {err}.")
        if self.holding != object:
            return StepResult(False, f"Cannot place: the gripper is not holding {object}.")
        if err := self._accepts(target, object):
            return StepResult(False, f"Cannot place: {err}.")
        self.objects[object]["on"], self.holding, self.near = target, None, target
        rel = "into" if (self.objects[target].get("container") or self.objects[target].get("slot")) else "on"
        return StepResult(True, f"Placed {object} {rel} {target}.")

    def _do_pour(self, source, target):
        for oid, what in ((source, "source"), (target, "target")):
            if err := self._check(oid, what):
                return StepResult(False, f"Cannot pour: {err}.")
        if self.holding != source:
            return StepResult(False, f"Cannot pour: the gripper is not holding {source}.")
        s, t = self.objects[source], self.objects[target]
        if not t.get("container"):
            return StepResult(False, f"Cannot pour: {target} is not a container.")
        if source == target:
            return StepResult(False, "Cannot pour a container into itself.")
        if not s["contents"]:
            return StepResult(False, f"Cannot pour: {source} is empty.")
        poured = list(s["contents"])
        t["contents"] = t["contents"] + [c for c in poured if c not in t["contents"]]
        s["contents"] = []
        self.near = target
        n = len(t["contents"])
        tail = f" The two liquids are now in {target}." if n > 1 else ""
        return StepResult(True, f"Poured the contents of {source} into {target}.{tail}",
                          {"pour": {"source": source, "target": target, "liquids": poured}})

    def _do_press(self, object):
        if err := self._check(object):
            return StepResult(False, f"Cannot press: {err}.")
        o = self.objects[object]
        if not o.get("appliance"):
            return StepResult(True, f"Pressed {object}. Nothing changed.")
        o["power_on"] = not o["power_on"]
        self.near = object
        if self.implicit:
            return StepResult(True, f"Pressed the switch on {object}.")
        return StepResult(True, f"Pressed the switch on {object}. It is now {o['on_text'] if o['power_on'] else o['off_text']}.")

    def _do_move_toward(self, target):
        if err := self._check(target, "target"):
            return StepResult(False, f"Cannot move: {err}.")
        self.near = target
        return StepResult(True, f"The gripper is now next to {target}.")

    def _do_strike(self, target):
        if err := self._check(target, "target"):
            return StepResult(False, f"Cannot strike: {err}.")
        if not self.holding:
            return StepResult(False, "Cannot strike: the gripper is empty.")
        if target == self.holding:
            return StepResult(False, "Cannot strike the held object with itself.")
        self.near = target
        return StepResult(True, f"{self.holding} made contact with {target}.",
                          {"contact": {"tool": self.holding, "target": target}})

    def _do_release(self):
        if not self.holding:
            return StepResult(True, "The gripper is open. Nothing was held.")
        obj, self.holding = self.holding, None
        if self.near and self.near in self.objects and self.near != obj and self._accepts(self.near, obj) is None:
            self.objects[obj]["on"] = self.near
            return StepResult(True, f"Released {obj}; it is now {'in' if self.objects[self.near].get('container') or self.objects[self.near].get('slot') else 'on'} {self.near}.")
        surface = next((oid for oid, o in self.objects.items() if o.get("surface") and not o.get("where")), None)
        self.objects[obj]["on"] = surface
        return StepResult(True, f"Released {obj}; it is now on the {surface}.")

    def _do_done(self):
        return StepResult(True, "Done.")

    def _do_refuse(self, reason):
        return StepResult(True, "Refusal recorded.")

    # ---- state export ------------------------------------------------

    def snapshot(self) -> dict:
        return {
            "holding": self.holding,
            "near": self.near,
            "objects": {oid: {"on": o["on"], "contents": o["contents"],
                              **({"power_on": o["power_on"]} if o.get("appliance") else {})}
                        for oid, o in self.objects.items()},
        }
