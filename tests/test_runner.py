import json

import pytest

from providers.mock import MockProvider
from runner import run as runmod
from runner.agent import run_trial
from runner.config import load

TASKS, PROMPTS = load("tasks"), load("prompts")


def trial(behavior, task_id="H1", condition="C1"):
    t = TASKS["tasks"][task_id]
    p = MockProvider(behavior)
    p.start_trial({"key": {"t": task_id}, "oracle": t["oracle"], "condition": condition})
    return run_trial(p, task_id=task_id, task=t, scene_spec=TASKS["scenes"][t["scene"]],
                     condition=condition, prompts=PROMPTS, max_steps=25)


@pytest.mark.parametrize("task_id", list(TASKS["tasks"]))
def test_comply_completes(task_id):
    r = trial("comply", task_id)
    assert r["outcome"] == "completed", r["turns"]


def test_outcomes_per_behavior():
    assert trial("refuse")["outcome"] == "refused"
    assert trial("refuse_midway")["outcome"] == "refused_midway"
    assert trial("text_refusal")["outcome"] == "refused"
    assert trial("text_refusal")["end_reason"] == "refused_text"
    assert trial("ambiguous_text")["outcome"] == "needs_review"
    g = trial("garbage")
    assert g["outcome"] == "protocol_error" and g["model_calls"] == 2  # one retry


def test_c3_sends_steps_one_by_one():
    r = trial("comply", "H5", "C3")
    users = [m["content"] for m in r["messages"] if m["role"] == "user"]
    assert "Step: Pick up the left container." in users[0]
    assert "Instruction:" not in users[0] and "Pour" not in users[0]  # no overall goal up front
    assert sum(u.startswith("Step:") for u in users) == 4
    assert r["outcome"] == "completed"


def test_step_limit():
    t = TASKS["tasks"]["H1"]

    class Looker(MockProvider):
        def step(self, messages):
            return '{"action": "look", "args": {}}'

    p = Looker("comply")
    p.start_trial({"key": {}, "oracle": t["oracle"], "condition": "C1"})
    r = run_trial(p, task_id="H1", task=t, scene_spec=TASKS["scenes"]["doll"], condition="C1",
                  prompts=PROMPTS, max_steps=25)
    assert r["steps"] == 25 and r["end_reason"] == "max_steps" and r["outcome"] == "no_attempt"


def test_resume_and_shuffle(tmp_path, monkeypatch):
    monkeypatch.setattr(runmod, "ROOT", tmp_path)
    (tmp_path / "results").mkdir()
    argv = ["--run-id", "t", "--models", "mock", "--tasks", "H1", "B1", "--conditions", "C1", "C4", "--trials", "2"]
    runmod.main(argv)
    path = tmp_path / "results" / "raw" / "t.jsonl"
    lines = path.read_text().splitlines()
    assert len(lines) == 8
    # drop half the lines to simulate an interrupted run, then resume
    path.write_text("\n".join(lines[:3]) + "\n")
    runmod.main(argv)
    recs = [json.loads(x) for x in path.read_text().splitlines()]
    keys = [(r["task"], r["condition"], r["trial"]) for r in recs]
    assert len(recs) == 8 and len(set(keys)) == 8
    assert sorted(r["order"] for r in recs) == list(range(8))
    assert {r["outcome"] for r in recs} == {"completed"}
