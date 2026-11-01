# Third-party material

The MIT license in [LICENSE](LICENSE) covers the code and the data produced by
this project. It does **not** cover the third-party material listed below, which
stays under its own terms.

## RoboHarm (Robocurve)

**Source.** RoboHarm: Do Frontier Robot Policies Refuse Unsafe Instructions?
Edward Sun, Sravanthi Machcha, Sabrina Zou, Tzu Kit Chan, Jay Chooi. Robocurve,
18 September 2026.

- Report and published data: https://robocurve.org/roboharm/
- Repository: https://github.com/robocurve/roboharm, licensed under
  [Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)](https://creativecommons.org/licenses/by-nc/4.0/)
- Agent transcripts: https://roboharm-artifacts.pages.dev/runs/transcripts/

**What is used here, and where.**

| Material | Origin | Where it appears | Changes |
|---|---|---|---|
| The five task instructions and the five archived benign instructions | RoboHarm repository, `docs/tasks/*.md` (CC BY-NC 4.0) | `config/tasks.yaml`, `docs/methodology.md`, `tests/test_config.py`, `README.md`, `article/*.md`, and in the prompts recorded in `results/raw/*.jsonl` and `results/review_queue.csv` | Used verbatim. The scenes they refer to were rewritten as text descriptions for a simulator; object lists and positions follow the task pages. |
| Per-task result counts (`cells.csv`) | Robocurve report data, https://robocurve.org/roboharm/data/cells.csv | `docs/sources/roboharm_cells.csv` (unchanged copy); numbers derived from it in `results/summary.md`, `results/extra_qwen/summary.md`, `results/tables/roboharm_comparison.csv`, `results/extra_qwen/tables/roboharm_comparison.csv`, `README.md`, `docs/methodology.md`, `article/*.md` | Used for comparison only. |
| Short excerpts from agent transcripts (single sentences) | RoboHarm agent transcripts | `results/roboharm_transcripts.md`, `results/tables/roboharm_transcripts.csv`, `docs/sources/roboharm_transcripts_manual.md`, `docs/methodology.md`, `article/*.md` | Quoted for analysis with trial ids; keyword flags and counts are this project's own. The full transcripts are not redistributed. |

No RoboHarm code is included. The simulator, runner, scoring and analysis in
this repository were written independently.

**Terms.** Material from RoboHarm is used for non-commercial research with
attribution. If you reuse it, follow CC BY-NC 4.0: credit the authors, link the
license, indicate changes, and do not use it for commercial purposes. The
authors' wording for the instructions should be preserved verbatim, as they ask
(see the RoboHarm task pages).

## BenchFlow robohub

Referenced for comparison in `README.md` and `docs/methodology.md`
(https://github.com/benchflow-ai/robohub, Apache-2.0). No code or data from it
is included.
