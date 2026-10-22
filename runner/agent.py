"""One trial: model <-> simulator loop."""

import time
from datetime import datetime, timezone

from scoring.classify import classify, classify_text
from scoring.goals import HAZARDS, evaluate
from sim.world import PHYSICAL_ACTIONS, World

from .protocol import parse_reply


def system_prompt(prompts: dict, condition: str) -> str:
    return prompts["system_prefix"][condition] + prompts["base"] + "\n\n" + prompts["protocol"].strip()


def run_trial(provider, *, task_id: str, task: dict, scene_spec: dict, condition: str,
              prompts: dict, max_steps: int) -> dict:
    world = World.from_spec(task["scene"], scene_spec,
                            implicit=condition in prompts.get("implicit_scene_conditions", []),
                            blind=condition in prompts.get("blind_scene_conditions", []))
    c3_steps = task["instructions"]["C3"] if condition == "C3" else None
    if c3_steps:
        first = prompts["c3_first_user"].format(scene=world.describe(), step=c3_steps[0])
    else:
        instruction = task["instructions"]["C2" if condition == "C2" else "C1"]
        first = prompts["first_user"].format(scene=world.describe(), instruction=instruction)
    messages = [{"role": "system", "content": system_prompt(prompts, condition)},
                {"role": "user", "content": first.strip()}]

    names = [task["goal"], task["literal_goal"], *HAZARDS]
    first_reached: dict = {}
    turns, steps, physical, c3_index = [], 0, 0, 0
    retry_pending, end_reason, refusal_reason = False, None, None
    started, t0 = datetime.now(timezone.utc).isoformat(), time.monotonic()

    while True:
        if steps >= max_steps:
            end_reason = "max_steps"
            break
        call_t0 = time.monotonic()
        reply = provider.step(messages)
        turn = {"call": len(turns) + 1, "reply": reply, "latency_s": round(time.monotonic() - call_t0, 2)}
        if hasattr(provider, "last_call_meta"):
            turn["usage"] = provider.last_call_meta()
        turns.append(turn)
        messages.append({"role": "assistant", "content": reply})

        parsed = parse_reply(reply)
        if parsed.action is None:
            turn["parse_error"] = parsed.error
            text_class = classify_text(reply)
            turn["text_class"] = text_class
            if text_class == "refusal":
                end_reason, refusal_reason = "refused_text", reply
                break
            if text_class == "ambiguous":
                # No retry: asking again for JSON would push towards compliance.
                end_reason = "needs_review"
                break
            if retry_pending:
                end_reason = "protocol_error"
                break
            retry_pending = True
            messages.append({"role": "user", "content": prompts["invalid_json"].format(error=parsed.error)})
            continue
        retry_pending = False
        steps += 1
        action = parsed.action
        turn.update({"step": steps, "action": action, "extra_text": parsed.extra_text})

        if action["action"] == "refuse":
            end_reason, refusal_reason = "refuse", action["args"].get("reason")
            break
        if action["action"] == "done":
            if c3_steps and c3_index < len(c3_steps) - 1:
                c3_index += 1
                turn["c3_next"] = c3_index + 1
                messages.append({"role": "user", "content": prompts["c3_next_step"].format(step=c3_steps[c3_index])})
                continue
            end_reason = "done"
            break

        result = world.apply(action["action"], action["args"])
        if action["action"] in PHYSICAL_ACTIONS:
            physical += 1
        turn["sim"] = {"ok": result.ok, "text": result.text}
        for name, value in evaluate(world, names).items():
            if value and name not in first_reached:
                first_reached[name] = steps
        messages.append({"role": "user",
                         "content": prompts["feedback"].format(result=result.text, scene=world.describe()).strip()})

    goal_reached = task["goal"] in first_reached
    literal_reached = task["literal_goal"] in first_reached
    outcome = classify(task["kind"], goal_reached=goal_reached, literal_reached=literal_reached,
                       end_reason=end_reason, physical_before_end=physical)
    return {
        "task": task_id,
        "kind": task["kind"],
        "scene": task["scene"],
        "condition": condition,
        "outcome": outcome,
        "end_reason": end_reason,
        "refusal_reason": refusal_reason,
        "goal_reached": goal_reached,
        "literal_goal_reached": literal_reached,
        "first_reached_step": first_reached,
        "hazards_reached": [h for h in HAZARDS if h in first_reached],
        "steps": steps,
        "physical_actions": physical,
        "model_calls": len(turns),
        "c3_steps_reached": c3_index + 1 if c3_steps else None,
        "turns": turns,
        "messages": messages,
        "final_state": world.snapshot(),
        "events": world.events,
        "started_at": started,
        "duration_s": round(time.monotonic() - t0, 2),
    }
