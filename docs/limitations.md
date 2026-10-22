# Limitations

## Claude through the Claude Code CLI

There is no Anthropic API key, so Claude is called via `claude -p` (headless
Claude Code) on a subscription. Flags used (see `providers/claude_cli.py`):

```
claude -p --system-prompt "<SimHarm system prompt>" --model claude-opus-5 \
  --tools "" --strict-mcp-config --setting-sources "" --disable-slash-commands \
  --output-format json  (--session-id <uuid> | --resume <uuid>)
```

- **The system prompt is not only ours.** `--system-prompt` replaces Claude Code's
  default prompt, but the CLI still adds (verified before the pilot by asking the model
  to list its system prompt): an identity line ("a Claude agent built on
  Anthropic's Claude Agent SDK"), an environment block (working directory,
  platform, OS, date, model name), and account context including the account
  e-mail address. `--bare` would avoid this but requires an API key. In the probe
  the model remarked that this context "suggests this scene may be a test
  harness". This is a confound for all conditions and specifically for C5
  ("real physical robot"), whose claim is contradicted by the environment block.
  Mitigation: each trial runs in an empty temporary directory with a neutral
  name; the e-mail address is scrubbed from the logs before publication
  (`analysis/scrub.py`). The OpenAI arm does not have this confound.
- **No tools.** `--tools ""` disables all built-in tools; MCP servers, settings,
  hooks, CLAUDE.md and skills are disabled by the other flags. Verified: the model
  reported having no tools.
- **History.** The CLI cannot take a pre-built conversation with assistant turns
  (stream-json input makes the model answer every user message anew), so each
  trial is one CLI session: `--session-id` on the first step, `--resume` with only
  the new user message afterwards. The runner keeps the canonical history and
  checks before each call that it matches what the session has received.
- **Sampling** (temperature, thinking budget) cannot be set beyond `--effort`;
  defaults are used. The CLI also makes a small auxiliary Haiku call per
  invocation (visible in `modelUsage`); it does not see the conversation output
  we score.
- **Model version.** RoboHarm tested Claude Fable 5.1; it requires paid usage
  credits on the subscription. SimHarm tests `claude-opus-5`.

- **Malformed JSON.** In the main run 13 of 1,951 Claude replies were a
  `refuse` object missing its final closing brace. They were scored by the
  text-refusal rules or by manual review (all were refusals); the parser was
  not loosened after the fact.

## Simulation instead of hardware

- Text scene descriptions replace three camera views; the model is told object
  identities and labels that RoboHarm's models had to perceive.
- Actions are symbolic; failure from motor control (a large share of RoboHarm's
  "attempted, failed") cannot happen in the same way. Completion rates are
  therefore not comparable with RoboHarm.
- Appliance state must be stated in text (burner lit, toaster on), which makes
  the hazard more explicit than an image.
- A text world with JSON actions may itself signal "this is a test", and models
  may behave differently when they believe they are evaluated.

## Design

- 10 trials per cell: enough to separate large effects, not small ones.
- One wording per condition; C2 and C3 texts are our own and other wordings may
  give different results.
- Different model versions from RoboHarm; providers can change models behind a
  name over time (reported names and dates are logged).
- Rule-based text-refusal classification with manual review; reviewer is the
  project author (single annotator).

## Checks added after the main run

- **C1i and C1b are exploratory**, designed after seeing the pilot and the
  main run (methodology §5, §11, change log). Their results are reported as
  such, not as confirmations of a preregistered hypothesis.
- **C1b removes information**: without labels or object identity the model
  cannot know that a hazard exists. Completion in C1b shows how much the
  behaviour depends on being told what the objects are; it is not a safety
  failure in the same sense as completion in C1.
- **Object-id leak (fixed).** Until the fix, implicit/blind scenes showed the
  id `power_bank`; 80 GPT/Claude trials and 20 Qwen trials were excluded and
  re-run (`config/exclusions.yaml`). Other ids were checked.
- **Comparison with RoboHarm transcripts** relies on visible text only and on
  keyword rules (methodology §10); hidden reasoning is not published.

## Published logs

- **Absolute timestamps removed.** Before publication, `started_at` and
  `logged_at` in `results/raw/*.jsonl` were replaced by the offset from the
  first trial start of the same run (`+HH:MM:SS`, `analysis/scrub.py
  --relative-times`). Durations, trial order and parallelism are unchanged;
  dates were also removed from the documentation and review notes. Model replies
  were not edited.
- **No personal data.** The logs were scanned for e-mail addresses, user names
  and local paths before publication (`analysis/scrub.py`).

## Additional model (Qwen2.5-7B)

- Served locally by llama.cpp at its default sampling (temperature 0.8), unlike
  the provider defaults of the two main models; results are reported
  separately and not compared statistically with them.
- Qwen often uses `refuse()` to report confusion ("pot is not pickable"); these
  were marked `refused_capability` by hand (58 cases, two borderline), so its
  safety-refusal rate is the meaningful refusal measure.
- 3 of 700 Qwen trials ended as protocol errors and are excluded from rates.
