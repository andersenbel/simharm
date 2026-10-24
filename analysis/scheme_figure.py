"""Experiment scheme for the article (results/figures/{en,uk}/scheme.png).

    python -m analysis.scheme_figure
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

from runner.config import ROOT  # noqa: E402

from .report import INK, INK2, MUTED, SURFACE  # noqa: E402

BOX_FILL, BOX_EDGE, ACCENT = "#f2f6fc", "#1f5fb0", "#2a78d6"


def box(ax, x, y, w, h, title, sub):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=BOX_FILL, ec=BOX_EDGE, lw=1.6))
    ax.text(x + w / 2, y + h * 0.62, title, ha="center", va="center", fontsize=13, weight="bold", color=INK)
    ax.text(x + w / 2, y + h * 0.27, sub, ha="center", va="center", fontsize=8.5, color=INK2)


def arrow(ax, a, b, label, above=True, color=ACCENT):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=14, lw=1.6, color=color))
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    ax.text(mx, my + (0.25 if above else -0.15), label, ha="center", va="center", fontsize=8.5, color=INK2)


LABELS = {
    "uk": {"op": "оператор: промпт, C1–C5", "model": "Модель", "sim": "Симулятор", "sim_sub": "стан світу, без наслідків",
           "eval": "Оцінювання", "eval_sub": "код перевіряє небезпечний стан", "a1": "сцена +\nінструкція",
           "a2": "одна дія\nв JSON", "a3": "новий стан", "a4": "результат дії"},
    "en": {"op": "operator: prompt, C1–C5", "model": "Model", "sim": "Simulator", "sim_sub": "world state, no consequences",
           "eval": "Scoring", "eval_sub": "code checks the hazardous state", "a1": "scene +\ninstruction",
           "a2": "one action\nas JSON", "a3": "new state", "a4": "action result"},
}


def draw(lang: str):
    t = LABELS[lang]
    fig, ax = plt.subplots(figsize=(11.5, 4.4), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    ax.set_xlim(0, 11.5)
    ax.set_ylim(0, 4.4)
    ax.axis("off")
    w, h = 2.6, 1.05
    box(ax, 0.2, 2.8, w, h, "SimHarm", t["op"])
    box(ax, 4.45, 2.8, w, h, t["model"], "GPT / Claude / Qwen")
    box(ax, 8.7, 2.8, w, h, t["sim"], t["sim_sub"])
    box(ax, 6.4, 0.35, 3.0, h, t["eval"], t["eval_sub"])
    arrow(ax, (2.9, 3.55), (4.4, 3.55), t["a1"])
    arrow(ax, (7.15, 3.55), (8.65, 3.55), t["a2"])
    arrow(ax, (8.65, 3.05), (7.15, 3.05), t["a3"], above=False, color=MUTED)
    arrow(ax, (4.4, 3.05), (2.9, 3.05), t["a4"], above=False, color=MUTED)
    arrow(ax, (9.9, 2.75), (9.0, 1.45), "")
    out = ROOT / "results" / "figures" / lang
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / "scheme.png", dpi=170, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    print(out / "scheme.png")


def main():
    for lang in ("en", "uk"):
        draw(lang)


if __name__ == "__main__":
    main()
