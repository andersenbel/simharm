"""Run the experiment matrix with resume.

    python -m runner.run --run-id pilot --trials 1
    python -m runner.run --run-id main
    python -m runner.run --run-id dry --models mock --trials 2

Trials are written to results/raw/<run_id>.jsonl as soon as they finish. A
restarted run skips every (model, task, condition, trial) already in the file.
Infrastructure failures are retried; a trial that keeps failing is recorded in
<run_id>.errors.jsonl, not in the results, and is picked up again on resume.
"""

import argparse
import json
import platform
import random
import subprocess
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from providers import ProviderError, make_provider
from scoring.review import write_review_queue
from sim.world import SIM_VERSION

from .agent import run_trial
from .config import ROOT, file_hash, load

MAX_INFRA_RETRIES = 6


def git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout
        return (out.stdout.strip() or "no-commit") + ("+dirty" if dirty.strip() else "")
    except FileNotFoundError:
        return "unknown"


def code_hash() -> str:
    """Content hash of the code that produces and scores trials (independent of git)."""
    import hashlib
    h = hashlib.sha256()
    for d in ("sim", "runner", "scoring", "providers"):
        for f in sorted((ROOT / d).glob("*.py")):
            h.update(f.name.encode() + f.read_bytes())
    return h.hexdigest()[:12]


def trial_key(rec: dict) -> tuple:
    return (rec["model"], rec["task"], rec["condition"], rec["trial"])


def read_done(path: Path) -> set:
    done = set()
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    done.add(trial_key(json.loads(line)))
    return done


def plan(exp: dict, model_names: list, tasks: list, conditions: list, trials: int) -> list:
    cells = [(m, t, c, i) for m in model_names for t in tasks for c in conditions for i in range(trials)]
    random.Random(exp["seed"]).shuffle(cells)
    return cells


def main(argv=None):
    load_dotenv(ROOT / ".env")
    exp, prompts, taskcfg = load("experiment"), load("prompts"), load("tasks")
    all_models = {m["name"]: m for m in exp["models"] + exp.get("extra_models", [])}

    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--models", nargs="+", default=[m["name"] for m in exp["models"]])
    ap.add_argument("--tasks", nargs="+", default=exp["tasks"])
    ap.add_argument("--conditions", nargs="+", default=exp["conditions"] + exp.get("sensitivity_conditions", []))
    ap.add_argument("--trials", type=int, default=exp["trials_per_cell"])
    ap.add_argument("--mock-behavior", default=None, help="override behaviour of the mock model")
    args = ap.parse_args(argv)

    unknown = [m for m in args.models if m not in all_models]
    if unknown:
        sys.exit(f"unknown model(s): {unknown}; known: {list(all_models)}")

    raw_dir = ROOT / exp["results_dir"] / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_path, err_path = raw_dir / f"{args.run_id}.jsonl", raw_dir / f"{args.run_id}.errors.jsonl"
    done = read_done(out_path)
    cells = [(c, order) for order, c in enumerate(plan(exp, args.models, args.tasks, args.conditions, args.trials))
             if c not in done]
    print(f"run {args.run_id}: {len(done)} trials already logged, {len(cells)} to go", flush=True)

    versions = {"sim": SIM_VERSION, "git": git_commit(), "code_sha": code_hash(), "python": platform.python_version(),
                "prompts_sha": file_hash("prompts"), "tasks_sha": file_hash("tasks"),
                "experiment_sha": file_hash("experiment")}
    lock = threading.Lock()
    counts = defaultdict(int)

    def write(path, rec):
        with lock, open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()

    def worker(model_name: str, queue: list):
        cfg = dict(all_models[model_name])
        if cfg["provider"] == "mock" and args.mock_behavior:
            cfg["behavior"] = args.mock_behavior
        provider = make_provider(cfg)
        while True:
            with lock:
                if not queue:
                    return
                (_, task_id, cond, trial), order = queue.pop(0)
            task = taskcfg["tasks"][task_id]
            key = {"model": model_name, "task": task_id, "condition": cond, "trial": trial}
            for attempt in range(1, MAX_INFRA_RETRIES + 1):
                provider.start_trial({"key": key, "oracle": task["oracle"], "condition": cond})
                try:
                    rec = run_trial(provider, task_id=task_id, task=task, scene_spec=taskcfg["scenes"][task["scene"]],
                                    condition=cond, prompts=prompts, max_steps=exp["max_steps"])
                    break
                except ProviderError as e:
                    wait = e.retry_after or 30
                    print(f"[{model_name} {task_id} {cond} #{trial}] infra error (attempt {attempt}): {e}; "
                          f"retrying whole trial in {wait:.0f}s", flush=True)
                    time.sleep(wait)
                finally:
                    provider.end_trial()
            else:
                write(err_path, {**key, "run_id": args.run_id, "error": "gave up after infra retries",
                                 "at": datetime.now(timezone.utc).isoformat()})
                continue
            rec = {"run_id": args.run_id, **key, "order": order, "provider": cfg["provider"],
                   "provider_info": provider.info(), "versions": versions,
                   "logged_at": datetime.now(timezone.utc).isoformat(), **rec}
            write(out_path, rec)
            with lock:
                counts[model_name] += 1
                n = sum(counts.values())
            print(f"[{n}/{len(cells)}] {model_name} {task_id} {cond} #{trial}: {rec['outcome']} "
                  f"({rec['steps']} steps, {rec['duration_s']}s)", flush=True)

    by_model = defaultdict(list)
    for cell, order in cells:
        by_model[cell[0]].append((cell, order))
    with ThreadPoolExecutor() as pool:
        futures = [pool.submit(worker, m, q) for m, q in by_model.items()
                   for _ in range(min(all_models[m].get("workers", 1), len(q)))]
        for f in futures:
            f.result()

    n_review = write_review_queue(ROOT / exp["results_dir"])
    print(f"finished. review queue: {n_review} rows -> results/review_queue.csv")


if __name__ == "__main__":
    main()
