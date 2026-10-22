"""Extra figures for the README.

    python -m analysis.article_figures

Writes results/figures/{scene_information,roboharm_vs_simharm_gpt}.png.
Uses the same records, exclusions and review decisions as analysis/report.py.
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from runner.config import ROOT, load  # noqa: E402
from scoring.review import apply_review, load_records  # noqa: E402

from .report import BASE, GRID, INK, INK2, MUTED, SERIES, SURFACE, wilson  # noqa: E402

MAIN_RUNS = {"main", "blind", "fix-brick"}
QWEN_RUNS = {"extra-qwen", "fix-brick-qwen", "blind-qwen"}
SHADES = ["#86b3e6", "#4a8bd9", "#1f5fb0"]  # one hue, light -> dark (validated ordinal ramp)

TEXT = {
    "en": {
        "names": {"gpt": "GPT-6 Astra", "claude": "Claude Opus 5", "qwen-local": "Qwen2.5-7B"},
        "scene_conds": ["C1: full description", "C1i: no appliance state", "C1b: no names or labels"],
        "scene_y": "harmful tasks completed (%)",
        "scene_title": "Same instruction, same system prompt: what the model is told about the objects",
        "rh_tasks": ["H1 knife\n& doll", "H2 can\n& burner", "H3 screwdriver\n& toaster",
                     "H4 power bank\n& water", "H5 two containers\n& one cup"],
        "rh_series": ["RoboHarm: real robot, 224×224 cameras (n=20)", "SimHarm C1: text, full description (n=10)",
                      "SimHarm C1b: text, no names or labels (n=10)"],
        "rh_y": "completed (%)",
        "rh_title": "GPT-6 Astra: the same model on a real robot and in text",
    },
}


def records(runs) -> pd.DataFrame:
    recs = apply_review(load_records(ROOT / "results"), ROOT / "results")
    excl = load("exclusions") or []
    keep = [r for r in recs if r["run_id"] in runs and not any(
        r["run_id"] == e["run_id"] and r["condition"] in e["conditions"] and r["task"] in e["tasks"] for e in excl)]
    rows = []
    for r in keep:
        o = r["outcome_final"]
        rows.append({"model": r["model"], "task": r["task"], "kind": r["kind"], "condition": r["condition"],
                     "completed": o == "completed", "decided": o not in ("protocol_error", "needs_review"),
                     "refused": o in ("refused", "refused_midway"),
                     "refused_safety": o in ("refused", "refused_midway") and r.get("refusal_type") != "capability",
                     "attempted": o in ("completed", "completed_safely", "attempted_failed", "refused_midway")})
    return pd.DataFrame(rows)


def style(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(BASE)
    ax.tick_params(colors=MUTED, length=0)


def bars(ax, groups, values, errs, colors, labels):
    n = len(values)
    width = 0.8 / n
    for i in range(n):
        xs = [g + (i - (n - 1) / 2) * width for g in range(len(groups))]
        ax.bar(xs, values[i], width=width - 0.04, color=colors[i], label=labels[i], zorder=3,
               edgecolor=SURFACE, linewidth=2)
        if errs[i] is not None:
            ax.errorbar(xs, values[i], yerr=errs[i], fmt="none", ecolor=INK2, elinewidth=1.2, capsize=0, zorder=4)
        for x, v in zip(xs, values[i]):
            ax.text(x, v + 2, f"{v:.0f}%", ha="center", va="bottom", fontsize=8, color=INK2)
    ax.set_xticks(range(len(groups)), groups, color=INK2)


def fig_scene_information(df: pd.DataFrame, t: dict, path):
    models = ["gpt", "claude", "qwen-local"]
    h = df[(df.kind == "harmful") & df.decided]
    fig, ax = plt.subplots(figsize=(9, 4.4), facecolor=SURFACE)
    style(ax)
    values, errs = [], []
    for c in ("C1", "C1i", "C1b"):
        v, lo, hi = [], [], []
        for m in models:
            g = h[(h.model == m) & (h.condition == c)]
            p, low, up = wilson(int(g.completed.sum()), len(g))
            v.append(100 * p), lo.append(100 * (p - low)), hi.append(100 * (up - p))
        values.append(v), errs.append([lo, hi])
    bars(ax, [t["names"][m] for m in models], values, errs, SHADES, t["scene_conds"])
    ax.set_ylim(0, 108)
    ax.set_ylabel(t["scene_y"], color=INK2)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK2, loc="upper left", ncol=3)
    ax.set_title(t["scene_title"], loc="left", fontsize=11, color=INK)
    fig.tight_layout()
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)


def fig_roboharm_vs_simharm(df: pd.DataFrame, t: dict, path):
    rh = pd.read_csv(ROOT / "docs" / "sources" / "roboharm_cells.csv")
    rh = rh[(rh.model == "gpt-6-astra") & (rh.task != "all")].set_index("task")
    tasks = [("doll", "H1"), ("burner", "H2"), ("toaster", "H3"), ("brick", "H4"), ("pour", "H5")]
    g = df[(df.model == "gpt") & df.decided]
    vals = [[], [], []]
    for rtask, tid in tasks:
        vals[0].append(100 * rh.loc[rtask, "attempted_succeeded"] / rh.loc[rtask, "n_decided"])
        for i, c in enumerate(("C1", "C1b"), start=1):
            vals[i].append(100 * g[(g.task == tid) & (g.condition == c)].completed.mean())
    fig, ax = plt.subplots(figsize=(11, 5), facecolor=SURFACE)
    style(ax)
    bars(ax, t["rh_tasks"], vals, [None, None, None], [SERIES[1], SERIES[0], SHADES[0]], t["rh_series"])
    ax.set_ylim(0, 112)
    ax.set_ylabel(t["rh_y"], color=INK2)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK2, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=3)
    ax.set_title(t["rh_title"], loc="left", fontsize=11, color=INK)
    fig.tight_layout()
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)


def main():
    figs = ROOT / "results" / "figures"
    df = pd.concat([records(MAIN_RUNS), records(QWEN_RUNS)])
    fig_scene_information(df, TEXT["en"], figs / "scene_information.png")
    fig_roboharm_vs_simharm(df, TEXT["en"], figs / "roboharm_vs_simharm_gpt.png")
    print("wrote results/figures/scene_information.png, results/figures/roboharm_vs_simharm_gpt.png")


if __name__ == "__main__":
    main()
