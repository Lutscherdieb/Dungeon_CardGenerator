---
name: card-balance
description: Check this game's cards for cost/power balance against the whole deck — fits a cost model from the 137 stored cards, flags the ones whose Mana+Cards+Food does not match what their Tier and stats predict, and records your verdict so the same card is never re-reported. Use on "/card-balance", "check the balance", "is this card costed right", "balance pass", "which cards are undercosted", "audit the costs", or after adding or re-costing cards. NOT for checking conventions, docs or code — that is /base:doc-audit; NOT for print geometry — that is the verify gate.
---

# /card-balance — is this card costed like the rest of the deck?

Fits a cost model per card type from the cards actually in the store, reports the
ones that do not fit it, and **writes your verdict back** so the next run is
sharper instead of identical.

The split that makes this work: **the arithmetic is deterministic Python, the
judgment is yours.** `cardgen balance` can say Moonfang costs 1.3 more than its
stats predict. Only a person reading its rules text can say whether that is a
mistake or a drawback the numbers cannot see. So never present a residual as a
verdict, and never change a card without asking.

## Run it

```bash
python -m cardgen.cli balance --json      # what you consume
python -m cardgen.cli balance             # what the author reads
```

It reads `data/cards.db` — the store, not `data/Mixed`, because the gallery is
where cards are edited. It needs no server. Restrict with `--type room`; add
`--all` to re-surface findings already ruled on.

## The procedure

1. **Run it** with `--json`. Every group reports `n` and `r2`; carry both into
   anything you say about a finding from that group. A residual from a fit with
   `r2 = 0.18` over 10 cards is a hint, not evidence — say so in those words.
2. **Skip what has already been judged.** `--json` returns *every* finding,
   each carrying `"accepted": true|false` — it does not drop the accepted ones,
   so that you can see the whole picture. Present only the `false` ones. (The
   text report does split them for you, under "already ruled on".) `--all`
   clears the rulings entirely, which is how you re-open a past decision.
3. **Read each surviving card's `Description` before presenting it.** The fit is
   structurally blind to what an ability is worth (see
   [references/method.md](references/method.md)); a card whose text carries a
   real drawback or a real engine is *supposed* to sit off the curve. Say which
   of the two you think it is, and why.
4. **Present the findings ranked**, worst `|z|` first. For each: the card, its
   type and tier, actual cost, expected cost, the residual, `n`/`r2` for its
   group, and one sentence on what its text does. Ask the author to rule.
5. **Record every verdict in the same turn** — this step is the skill, not
   paperwork after it. See "Writing the verdict back" below.
6. **Re-run** after any cost change: moving one card moves the curve for its
   whole type, and a change can create a new outlier.

## Writing the verdict back

Three verdicts, three homes. All three are markdown for a human, with one fenced
`json` block the tool reads — so the reason always sits beside the rule.

| The author says | Do this |
|---|---|
| "that's deliberate" | Append an entry to [references/rulings.md](references/rulings.md) with the reason **and the date**. It stops being reported. |
| "no, fix it" | Change the card in the gallery or via the API, then re-run. Do not edit `data/Mixed` by hand — the store is the source of truth. |
| "the model is wrong" | Pin the weight or drop the feature in [references/model.md](references/model.md)'s json block, and write the sentence explaining why above it. |

A ruling that generalises past one card is a **rule**, not a war story: write it
as an imperative in `references/model.md`'s prose and add a
`.claude/learning-log.md` entry in the same edit (see the write-back task in
[CLAUDE.md](../../../CLAUDE.md)).

## Reference index

| File | Load when you're... |
|---|---|
| [references/method.md](references/method.md) | Explaining or defending a number — how the fit works, and the four things it structurally cannot see |
| [references/model.md](references/model.md) | Pinning a weight, changing a threshold, or reading the current cost curve |
| [references/rulings.md](references/rulings.md) | Recording a verdict, or checking whether a card has already been judged |

## What this skill is not

- Not `/base:doc-audit`, which audits this repo's own documentation.
- Not the verify gate (`python tests/run_tests.py`), which proves print geometry.
- Not a rules simulator. `PROJECT.md` rules that out; this reads printed numbers
  and printed text, and never executes anything from `Rules/`.
