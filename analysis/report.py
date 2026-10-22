"""Tables, figures and results/summary.md from the raw logs.

    python -m analysis.report                 # all runs in results/raw
    python -m analysis.report --run-id main   # one run

Rates use N = decided trials (everything except protocol_error and unresolved
needs_review), as in RoboHarm's analysis. Intervals are Wilson 95%; differences
between conditions use Newcombe's hybrid score interval. A difference whose
interval contains 0 is reported as "no detectable difference".
"""

import argparse
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from runner.config import ROOT, load  # noqa: E402
from scoring.classify import REFUSAL_OUTCOMES  # noqa: E402
from scoring.review import apply_review, load_records  # noqa: E402

Z = 1.959964
UNDECIDED = {"protocol_error", "needs_review"}
ATTEMPT = {"completed", "completed_safely", "attempted_failed", "refused_midway"}
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]  # validated categorical slots 1-3
INK, INK2, MUTED, GRID, BASE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
SURFACE = "#fcfcfb"


def wilson(k: int, n: int):
    if n == 0:
        return (math.nan, math.nan, math.nan)
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    # clamp so float rounding never puts the bound on the wrong side of p (p = 0 or 1)
    return (p, min(p, max(0.0, c - h)), max(p, min(1.0, c + h)))


def newcombe(k1, n1, k2, n2):
    """CI for p2 - p1 (Newcombe 1998, method 10)."""
    p1, l1, u1 = wilson(k1, n1)
    p2, l2, u2 = wilson(k2, n2)
    if math.isnan(p1) or math.isnan(p2):
        return (math.nan, math.nan, math.nan)
    d = p2 - p1
    return (d, d - math.sqrt((p2 - l2) ** 2 + (u1 - p1) ** 2), d + math.sqrt((u2 - p2) ** 2 + (p1 - l1) ** 2))


def frame(records) -> pd.DataFrame:
    rows = []
    for r in records:
        o = r["outcome_final"]
        rows.append({"run_id": r["run_id"], "model": r["model"], "model_reported": r["provider_info"].get("model_reported"),
                     "task": r["task"], "kind": r["kind"], "condition": r["condition"], "trial": r["trial"],
                     "outcome": o, "decided": o not in UNDECIDED, "refused": o in REFUSAL_OUTCOMES,
                     "refused_safety": o in REFUSAL_OUTCOMES and r.get("refusal_type") != "capability",
                     "attempted": o in ATTEMPT, "completed": o == "completed",
                     "hazard_any": bool(r["hazards_reached"]), "steps": r["steps"]})
    return pd.DataFrame(rows)


def rates(df: pd.DataFrame, by: list) -> pd.DataFrame:
    out = []
    for key, g in df.groupby(by, sort=True):
        d = g[g.decided]
        n = len(d)
        row = dict(zip(by, key if isinstance(key, tuple) else (key,)))
        row.update({"n_runs": len(g), "n": n, "undecided": len(g) - n})
        for m in ("refused", "refused_safety", "attempted", "completed"):
            k = int(d[m].sum())
            p, lo, hi = wilson(k, n)
            row.update({f"{m}_k": k, f"{m}_rate": p, f"{m}_lo": lo, f"{m}_hi": hi})
        out.append(row)
    return pd.DataFrame(out)


def pct(p, lo=None, hi=None):
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return "–"
    s = f"{100 * p:.0f}%"
    return s if lo is None else f"{s} [{100 * lo:.0f}–{100 * hi:.0f}]"


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


def condition_contrasts(df: pd.DataFrame, conditions) -> pd.DataFrame:
    out = []
    for (model, kind), g in df[df.decided].groupby(["model", "kind"]):
        base = g[g.condition == conditions[0]]
        for c in conditions[1:]:
            cur = g[g.condition == c]
            for m in ("refused", "completed"):
                d, lo, hi = newcombe(int(base[m].sum()), len(base), int(cur[m].sum()), len(cur))
                verdict = ("no detectable difference" if (math.isnan(d) or lo <= 0 <= hi)
                           else ("higher" if d > 0 else "lower") + f" than {conditions[0]}")
                out.append({"model": model, "kind": kind, "metric": m, "condition": c,
                            "diff_vs_C1": d, "lo": lo, "hi": hi, "verdict": verdict})
    return pd.DataFrame(out)


def plot_by_condition(agg: pd.DataFrame, metric: str, models, conditions, path: Path, title: str,
                      panels=(("harmful", "Harmful tasks H1–H5"), ("benign", "Benign controls B1–B5")), group="kind",
                      ylabel=None, suptitle=None, model_labels=None):
    fig, axes = plt.subplots(1, len(panels), figsize=(5 * len(panels), 4.2), sharey=True, facecolor=SURFACE)
    width = 0.8 / max(1, len(models))
    for ax, (key, label) in zip(axes, panels):
        ax.set_facecolor(SURFACE)
        for i, model in enumerate(models):
            g = agg[(agg.model == model) & (agg[group] == key)].set_index("condition").reindex(conditions)
            xs = [j + (i - (len(models) - 1) / 2) * width for j in range(len(conditions))]
            ys = 100 * g[f"{metric}_rate"]
            err = [100 * (g[f"{metric}_rate"] - g[f"{metric}_lo"]), 100 * (g[f"{metric}_hi"] - g[f"{metric}_rate"])]
            color = SERIES[i % len(SERIES)]
            ax.errorbar(xs, ys, yerr=err, fmt="o", ms=8, color=color, ecolor=color, elinewidth=2, capsize=0,
                        mec=SURFACE, mew=2, label=(model_labels or {}).get(model, model), zorder=3)
        ax.set_xticks(range(len(conditions)), conditions, color=INK2)
        ax.set_ylim(-4, 104)
        ax.set_title(label, loc="left", fontsize=11, color=INK)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.spines["bottom"].set_color(BASE)
        ax.tick_params(colors=MUTED, length=0)
    axes[0].set_ylabel(ylabel or f"{title} (% of decided trials)", color=INK2)
    if len(models) > 1:
        handles, labels = axes[0].get_legend_handles_labels()
        fig.legend(handles, labels, frameon=False, loc="upper right", ncol=len(models), fontsize=9, labelcolor=INK2)
    fig.suptitle(suptitle or f"{title} by operator condition, Wilson 95% CI", x=0.01, ha="left", fontsize=12, color=INK)
    fig.tight_layout()
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)


def roboharm_comparison(cells: pd.DataFrame) -> pd.DataFrame:
    rh = pd.read_csv(ROOT / "docs" / "sources" / "roboharm_cells.csv")
    rh = rh[rh.task != "all"]
    task_map = {t["roboharm_task"]: tid for tid, t in load("tasks")["tasks"].items() if t.get("roboharm_task")}
    rows = []
    for _, r in rh.iterrows():
        if r.model == "molmoact2":
            continue
        rows.append({"source": f"RoboHarm (robot, {r.model})", "task": task_map[r.task],
                     "refused": f"{int(r.refused_any)}/{int(r.n_decided)}",
                     "completed": f"{int(r.attempted_succeeded)}/{int(r.n_decided)}"})
    for _, c in cells[(cells.kind == "harmful") & (cells.condition == "C1")].iterrows():
        rows.append({"source": f"SimHarm C1 ({c.model})", "task": c.task,
                     "refused": f"{c.refused_k}/{c.n}", "completed": f"{c.completed_k}/{c.n}"})
    return pd.DataFrame(rows).sort_values(["task", "source"])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", nargs="*", default=None)
    ap.add_argument("--out", default=None, help="output dir (default results/)")
    args = ap.parse_args(argv)
    exp = load("experiment")
    results = ROOT / exp["results_dir"]
    out = Path(args.out) if args.out else results
    (out / "figures").mkdir(parents=True, exist_ok=True)
    (out / "tables").mkdir(parents=True, exist_ok=True)

    records = apply_review(load_records(results), results)
    if args.run_id:
        records = [r for r in records if r["run_id"] in args.run_id]
    exclusions = load("exclusions") or []

    def excluded(r):
        return any(r["run_id"] == e["run_id"] and r["condition"] in e["conditions"] and r["task"] in e["tasks"]
                   for e in exclusions)
    n_excluded = sum(map(excluded, records))
    records = [r for r in records if not excluded(r)]
    if not records:
        raise SystemExit("no records")
    df = frame(records)
    present = set(df.condition)
    conditions = [c for c in exp["conditions"] if c in present]
    sensitivity = [c for c in exp.get("sensitivity_conditions", []) if c in present]
    models = list(dict.fromkeys(df.model))

    cells = rates(df, ["model", "kind", "task", "condition"])
    agg = rates(df, ["model", "kind", "condition"])
    contrasts = condition_contrasts(df, conditions + sensitivity)
    comp = roboharm_comparison(cells)
    cells.to_csv(out / "tables" / "cells.csv", index=False)
    agg.to_csv(out / "tables" / "by_condition.csv", index=False)
    contrasts.to_csv(out / "tables" / "contrasts_vs_C1.csv", index=False)
    comp.to_csv(out / "tables" / "roboharm_comparison.csv", index=False)
    pd.crosstab([df.model, df.kind, df.condition], df.outcome).to_csv(out / "tables" / "outcome_counts.csv")

    agg_main = agg[agg.condition.isin(conditions)]
    plot_by_condition(agg_main, "refused", models, conditions, out / "figures" / "refusal_by_condition.png", "Refusal rate")
    # Descriptive split (not a preregistered contrast): H1 is the only task with a human-figure
    # target and the one RoboHarm singles out.
    df["group"] = df.task.where(df.task == "H1", df.kind.map({"harmful": "H2–H5", "benign": "B1–B5"}))
    agg_g = rates(df[df.condition.isin(conditions)], ["model", "group", "condition"])
    plot_by_condition(agg_g, "refused", models, conditions, out / "figures" / "refusal_by_condition_split.png",
                      "Refusal rate", panels=(("H1", "H1: knife and doll"), ("H2–H5", "Harmful H2–H5"),
                                              ("B1–B5", "Benign controls B1–B5")), group="group")
    plot_by_condition(agg_main, "completed", models, conditions, out / "figures" / "completion_by_condition.png", "Completion rate")

    reported = df.groupby("model").model_reported.agg(lambda s: ", ".join(sorted({str(x) for x in s})))
    lines = ["# SimHarm results summary", "",
             f"Runs: {', '.join(sorted(df.run_id.unique()))}. Trials logged: {len(df)}; decided: {int(df.decided.sum())}; "
             f"protocol errors: {int((df.outcome == 'protocol_error').sum())}; awaiting manual review: "
             f"{int((df.outcome == 'needs_review').sum())}.", "",
             f"Excluded trials: {n_excluded} (see config/exclusions.yaml): "
             + "; ".join(f"{e['run_id']} {'/'.join(e['conditions'])} {'/'.join(e['tasks'])}: {e['reason']}"
                         for e in exclusions), "",
             "Models (as reported by the provider): " + "; ".join(f"{m}: {reported[m]}" for m in models), "",
             "Rates are over decided trials; brackets are Wilson 95% intervals. "
             "`refused` includes refusals after starting (`refused_midway`) and refusals on capability grounds; "
             "`refused_safety` excludes those marked `refused_capability` in manual review.", "",
             "## Refusal and completion by condition (pooled over tasks)", ""]
    t = agg_main.assign(refused=[pct(*x) for x in agg_main[["refused_rate", "refused_lo", "refused_hi"]].values],
                   refused_safety=[pct(*x) for x in agg_main[["refused_safety_rate", "refused_safety_lo", "refused_safety_hi"]].values],
                   completed=[pct(*x) for x in agg_main[["completed_rate", "completed_lo", "completed_hi"]].values])
    lines += [md_table(t[["model", "kind", "condition", "n", "refused", "refused_safety", "completed"]]), "",
              "![Refusal by condition](figures/refusal_by_condition.png)", "",
              "![Completion by condition](figures/completion_by_condition.png)", "",
              "Descriptive split by task group (H1 is the only human-figure target; not a preregistered contrast):", "",
              "![Refusal by condition, split](figures/refusal_by_condition_split.png)", "",
              "## Differences from C1 (Newcombe 95% CI, percentage points)", ""]
    contrasts_main = contrasts[contrasts.condition.isin(conditions)]
    ct = contrasts_main.assign(diff=[f"{100 * d:+.0f} [{100 * lo:+.0f}, {100 * hi:+.0f}]" if not math.isnan(d) else "–"
                                for d, lo, hi in contrasts_main[["diff_vs_C1", "lo", "hi"]].values])
    lines += [md_table(ct[["model", "kind", "metric", "condition", "diff", "verdict"]]), "",
              "## Per task and condition", ""]
    if sensitivity:
        s_rows = agg[agg.condition.isin(["C1"] + sensitivity)].sort_values(["model", "kind", "condition"])
        s_rows = s_rows.assign(refused=[pct(*x) for x in s_rows[["refused_rate", "refused_lo", "refused_hi"]].values],
                               completed=[pct(*x) for x in s_rows[["completed_rate", "completed_lo", "completed_hi"]].values])
        sc = contrasts[contrasts.condition.isin(sensitivity)]
        sc = sc.assign(diff=[f"{100 * d:+.0f} [{100 * lo:+.0f}, {100 * hi:+.0f}]" if not math.isnan(d) else "–"
                             for d, lo, hi in sc[["diff_vs_C1", "lo", "hi"]].values])
        lines[-2:-2] = ["## Sensitivity checks: C1i and C1b", "",
                        "Same instruction and system prompt as C1. C1i: the scene does not state whether the burner is "
                        "lit or the toaster is on, and the power bank is described as a \"black brick\". C1b "
                        "(methodology §11): as C1i, plus generic names (\"can\", \"burner with a heating coil\", "
                        "\"screwdriver\") and no printed labels (no AMMONIA/BLEACH).", "",
                        md_table(s_rows[["model", "kind", "condition", "n", "refused", "completed"]]), "",
                        md_table(sc[["model", "kind", "metric", "condition", "diff", "verdict"]]), ""]
    pt = cells.assign(refused=[f"{k}/{n}" for k, n in cells[["refused_k", "n"]].values],
                      completed=[f"{k}/{n}" for k, n in cells[["completed_k", "n"]].values])
    lines += [md_table(pt[["model", "task", "condition", "refused", "completed", "undecided"]]), "",
              "## Outcome counts", "", md_table(pd.crosstab([df.model, df.kind, df.condition], df.outcome).reset_index()), "",
              "## C1 versus RoboHarm", "",
              "RoboHarm numbers are from Robocurve's published `cells.csv` (https://robocurve.org/roboharm/). "
              "They come from physical robots, camera input, different model versions (Claude Fable 5.1, "
              "GPT-6 Astra) and human labelling; SimHarm uses a text simulator. The rows are not directly comparable.", "",
              md_table(comp), ""]
    (out / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out / 'summary.md'}")


if __name__ == "__main__":
    main()
