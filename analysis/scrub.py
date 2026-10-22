"""Remove personal data from logs before publication.

    python -m analysis.scrub                             # report matches only
    python -m analysis.scrub --apply                     # rewrite files in results/ in place
    python -m analysis.scrub --relative-times --apply    # also replace absolute timestamps

Replaces every e-mail address with "[email removed]". Extra strings (e.g. a name
or a home-directory path) can be given with --also.

--relative-times replaces `started_at` and `logged_at` in results/raw/*.jsonl with
the offset from the first trial start of the same run ("+HH:MM:SS"), so durations,
order and parallelism stay checkable while absolute dates are removed.
"""

import argparse
import json
import re
from datetime import datetime

from runner.config import ROOT

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
TIME_FIELDS = ("started_at", "logged_at")


def _offset(t: datetime, t0: datetime) -> str:
    s = int(round((t - t0).total_seconds()))
    return f"+{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def relativize(path, apply: bool) -> int:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    absolute = [r for r in records if any(str(r.get(f, "")).startswith("20") for f in TIME_FIELDS)]
    if not absolute:
        return 0
    t0 = min(datetime.fromisoformat(r["started_at"]) for r in records)
    for r in records:
        for f in TIME_FIELDS:
            if f in r and not str(r[f]).startswith("+"):
                r[f] = _offset(datetime.fromisoformat(r[f]), t0)
    if apply:
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    return len(absolute)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--relative-times", action="store_true")
    ap.add_argument("--also", nargs="*", default=[])
    args = ap.parse_args()
    total = 0
    for path in sorted((ROOT / "results").rglob("*")):
        if not path.is_file() or path.suffix not in (".jsonl", ".csv", ".md"):
            continue
        text = path.read_text(encoding="utf-8")
        new, n = EMAIL.subn("[email removed]", text)
        for s in args.also:
            n += new.count(s)
            new = new.replace(s, "[removed]")
        if n:
            total += n
            print(f"{path.relative_to(ROOT)}: {n} match(es)")
            if args.apply:
                path.write_text(new, encoding="utf-8")
    print(f"{total} match(es){' replaced' if args.apply else ' (dry run)'}")
    if args.relative_times:
        for path in sorted((ROOT / "results" / "raw").glob("*.jsonl")):
            n = relativize(path, args.apply)
            if n:
                print(f"{path.relative_to(ROOT)}: {n} record(s) with absolute timestamps"
                      f"{' relativized' if args.apply else ' (dry run)'}")


if __name__ == "__main__":
    main()
