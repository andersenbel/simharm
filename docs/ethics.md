# Ethics

**Purpose.** SimHarm studies how language-model behaviour on physically harmful
instructions depends on the system an operator builds around the model, and what
that implies for who is responsible for outcomes. It extends a published study
(RoboHarm) with a controlled manipulation it did not cover.

**Why a simulation.** No hardware, chemicals, appliances or batteries are used.
The five hazards are reproduced only as abstract states in a text world, which
removes any physical risk and lets the conditions be varied cheaply and
repeatably.

**No uplift.** Scenes and simulator responses contain no instructions, recipes
or technical details useful for causing real harm. The simulator records states
such as "the two liquids are now in the cup" and never describes consequences.
The hazards themselves (aerosol can on a flame, metal in a toaster, battery in
water, bleach with ammonia, a knife and a doll) are the ones RoboHarm published
and are common household-safety knowledge.

**Why the logs are published.** The full transcripts are the primary evidence:
they let others check the scoring, re-classify ambiguous cases and reproduce the
analysis. Before publication the logs are scrubbed of personal data (the CLI adds
the account e-mail address to Claude's context; see `docs/limitations.md`).
