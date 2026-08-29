# Rulings — cards the author has already judged

Load this when recording a verdict, or checking whether a card has already been
judged.

**This file is the skill's memory.** A card listed in the `json` block below is
excluded from every future run, so the report only ever shows what has not been
decided yet. That is the difference between a check that gets sharper and one
that prints the same twelve cards forever.

Append-only. A ruling that turns out to be wrong is **marked reversed with the
reason and left in place** — a retired decision that vanishes gets re-derived by
the next session.

## How to add one

1. Add an object to `accepted` with `card`, `reason` and `date` (absolute, never
   "today"). The `reason` is what a future session reads instead of re-asking, so
   write the *why*, not the residual.
2. Add a paragraph under "The rulings" below if the reason needs more than a
   line — the block is for the tool, the prose is for the person.
3. If the ruling generalises past this one card, it is a rule: write it into
   [model.md](model.md) as an imperative and log it in
   `.claude/learning-log.md` in the same edit.

Only `accepted` is read. A card the author decided to *change* does not belong
here — the change itself removes it from the report.

```json
{
  "accepted": []
}
```

## The rulings

*None yet.* The first `/card-balance` run against the 2026-08-29 deck produced
14 open findings and no verdicts have been recorded.
