# CardGenerator — project rules

Generate print-ready boardgame card images at exact MakePlayingCards measurements from card data plus artwork.

<!-- BASE:doctrine-header:v1 START -->
This repo was created from **ClaudeBase** (the version at creation, and the last synced one, are recorded in `.claude/base-manifest.json`). The generic machinery — setup, audits, sync, harvest — arrives via the `base` plugin and updates with it; this file and the other seeded docs are owned by this project, except the `BASE:` marker regions, which `/base:sync` maintains (never hand-edit inside them — needing to is a missing-interview-question bug in Base, file it as a lesson). `/base:doctor` shows status. No personal data in version control: no real names, emails, machine-specific absolute paths, or session IDs — machine-local state lives in gitignored `*.local.*` files.
<!-- BASE:END -->

## What this project is

See [PROJECT.md](PROJECT.md) — the constitution: goal, non-goals, quality bars, verify method, and the documentation contract. Generic skills read it first; keep it current when direction changes.

## The hard rule: external references are read-only

This project's declared ground truths are registered in [REFERENCES.md](REFERENCES.md).

<!-- BASE:doctrine-references:v1 START -->
**Read freely, write never — at every entry point.** Each reference's access method and comparison procedure live in REFERENCES.md; the `protect-references` hook blocks writes to declared paths. If a task seems to require editing a reference, **stop and warn the user instead of proceeding**, even if only part of a larger task touches it. A deliberate exception is made by flipping `modules.references` off in `.claude/base-manifest.json` — a visible, logged act — never by quiet edits.
<!-- BASE:END -->

<!-- BASE:doctrine-writeback:v1 START -->
## The highest-priority standing task: turn every lesson into a *rule*, not a war story

**Improving this project's workflow, skills, and docs with what a task teaches is the single most important recurring job — above finishing any individual feature.** A lesson only counts once it's written as a **prescriptive rule that tells the next session what to DO**, not a "gotcha" describing what went wrong. The test: *could someone follow this without already knowing the story behind it?*

When writing a finding back:
1. **Lead with the imperative** — a step someone executes.
2. **Include the verification step** if the failure was "I thought I had done it right" — an instruction that can be silently satisfied wrongly needs a check that proves it was satisfied.
3. **Keep the evidence, demote it** — `file:line`, exact error text, sample size N — *after* the rule, never in place of it. Record failed approaches too; they're the expensive knowledge to rediscover.
4. **Prefer removing the choice over documenting the hazard** — a helper that can't be called wrongly beats any warning text.

The escalation ladder for a recurring failure: prose warning → imperative rule + verification step → audit detection recipe → hook. A rule that gets violated *after* being written down is evidence the writing was in the wrong **form**, not that people need reminding.

**Every written-back lesson also gets a `.claude/learning-log.md` entry in the same edit**, tagged `scope: generic|project` with an `applications:` date list (the log is the harvest index, never the rule's home). A `generic` lesson applied 2+ times is a `/base:promote` candidate — that's how improvements discovered here reach ClaudeBase and every sibling project. Needing to hand-edit a Base-owned file or `BASE:` region is itself always a `generic` lesson ("Base is missing an option/question").
<!-- BASE:END -->

<!-- BASE:doctrine-docs:v2 START -->
## Documentation is the user interface of this project

The user reads this project's state through the docs named in PROJECT.md's documentation contract. **A change to a mapped source area isn't done until its mapped doc is current** — same weight as the verify gate; the `check-doc-freshness` hook nudges on the manifest's `doc_map`. Rules:
- `AUTO:` regions in docs are generated — never hand-edit inside them; content that must survive regeneration sits outside the markers.
- Root README and contract docs are **not** create-late: they exist from day one and stay current without asking. Optional deep-dive docs are create-late-ask-first; but once one exists, keep it current, don't ask again.
- A new skill/doc file, or a structural edit to one, isn't done until a scoped `/base:doc-audit` cold-test covers the changed files (wording-only fixes exempt). One convention, one home: an index/checklist row links to the owning doc, never restates it.
- Authoring or restructuring a project skill follows `/base:skill-author` (two-tier SKILL.md + `references/` split by content shape, reference-index table, description-line triggers, no confusable names next to `/base:*` skills).
- Documented reversals stay in place, marked as reversed with the reason — a retired idea that vanishes gets re-derived.
- Derive, don't enumerate: no doc or hook hardcodes a list (of modules, files, features) that the manifest or the tree can supply.
<!-- BASE:END -->

<!-- BASE:doctrine-verify:v1 START -->
## Nothing is "done" untested

Every change inside the manifest's `source_globs` ends with the verify method from PROJECT.md actually run and its output checked before being reported as done — silent breakage is common and doesn't always error loudly. Proportionality: changes matching `verify.exempt_patterns` (pure docs/wording) skip this, but a mixed edit that also touches source doesn't. Evidence standard for any claim written back: `file:line`, the exact error text (the next person greps for that string), and sample size N when the conclusion rests on frequency.
<!-- BASE:END -->

## Project-specific rules

### Never hardcode a card pixel size — ask `cardgen.spec`

Every measurement (canvas, trim, safe zone, bleed, DPI, an SVG `viewBox`, a CSS width) comes from a `Profile` in `src/cardgen/spec/profiles.py`. Python asks the `Profile` directly; CSS and templates receive the numbers through `css_variables()` and the `canvas_w`/`canvas_h` context values. `style.css` declares no geometry of its own.

**Verification step:** after any change touching layout or rendering, `grep -rnE '\b(1122|1050|978|1125|975|75px|36px)\b' style.css templates/ src/` must return nothing outside `src/cardgen/spec/`. A number that reappears outside the spec module is a new source of truth, and the next size change will silently skip it.

*Evidence:* the canvas size existed in four disagreeing copies — `SIZE_PROFILES` (generate_card.py), the `canvas=1125, bleed=75, safe=975` defaults of `_gen_spider_side`, `body{width:1125px}` plus `.safe-zone{width:975px;margin:75px}` in style.css, and `viewBox="0 0 1125 1125"` in `templates/_spiderweb.html`. All four were wrong against MPC's published 1122; the `# add more profiles later (e.g., standard TCG)` comment had sat unimplemented because a size change was a four-language edit, not a data change.

### Take MakePlayingCards numbers from the published spec, never from a code comment

Before changing any print measurement, WebFetch the MPC reference registered in [REFERENCES.md](REFERENCES.md) and follow its comparison procedure. Code comments in this repo have been wrong about MPC twice.

**Verification step:** the derivation must reproduce MPC's own published figure for a size we do *not* print — poker at 2.5in x 3.5in uploads at 822 x 1122 px. `tests/run_tests.py` asserts exactly this; a formula that fails it is wrong even if the square numbers happen to look right.

*Evidence:* `SIZE_PROFILES` carried `# 3.5" x 3.5" (trim), 1/8" bleed each side -> 1125x1125`. MPC specifies 36px per side at 300 DPI, not 37.5, giving 1122. The Readme had recorded 1122 correctly all along — the code had drifted away from the docs, which is the opposite of the usual direction, so do not treat the code as the more current source.

### `Rules/` is the game's source of truth, and it is an idea book as well as a spec

`Rules/*.txt` is a registered read-only reference. Never edit it, and never silently reconcile code to it or it to code — when they disagree, raise the disagreement.

**Verification step:** before implementing anything sourced from `Rules/`, ask whether the line is a decided rule or a parked idea. `Rules/ToDo.txt` and `Rules/Ideas.txt` are explicitly open questions; `Rules/Cardtypes.txt` mixes both.

*Evidence:* `Rules/Cardtypes.txt` lists Overlord and Creature under "tcg format", which reads as a spec and was reported as a 59-card sizing defect. It was a parked intention: every card type is square, confirmed 2026-08-24. Acting on it would have re-sized 43% of the deck wrongly.
