# How the balance fit works, and what it cannot see

Load this when you are explaining a finding, defending a number, or deciding
whether a residual is worth raising at all.

## The claim, stated narrowly

**A card's printed cost should be predictable from its printed numbers, and one
that is not deserves a look.** That is the whole claim. It is not "this card is
overpowered" and it is not "the designer made a mistake".

## The arithmetic

Implemented in `src/cardgen/balance/`, which `python -m cardgen.cli balance`
drives.

**Target.** `cost = Mana + Cards + Food`, each times its weight from
`model.md` (all 1.0 by default). The three are found by reading `x-cost` off the
generated JSON Schema — set on `CardBase` in `src/cardgen/model/cards.py` — so
this module keeps no list of field names and a fourth resource would be picked
up automatically.

**Features.** Also read off the schema: every non-cost integer becomes itself,
every list becomes its length (`Slots#`, `Roads#`, `Creatures#`), every boolean
becomes 0/1. Two more are computed from the Description, because what they stand
for is written in prose:

- `has_ability` — 1 if the card prints any rules text.
- `activation_cost` — how many `[Token]`s sit in front of the first `:`.
  `Rules/Rules.txt:34`: "Costs are defined in front of a ':' within the
  description of a card." A colon more than 60 characters in is treated as prose,
  not a cost line, so "Start of Replenish: look at the top 3 cards" counts 0.

A feature that never varies within a group is dropped before the fit: a constant
column carries no information and would make the solve singular. That is why Room
reports no `Tier` weight (rooms have no tier), why `Starter` appears in no fit
today (no card is flagged yet, so the column is all zeros), and why Spell, Trap,
Research and Treasure report nothing but `Tier` — every other column they have is
identical across the type.

Feature counts as of 2026-08-29: Creature 47x6, Room 23x6, Hero 13x6,
Overlord 12x6, and 11x1 / 11x1 / 10x1 / 10x1 for Research, Trap, Spell and
Treasure.

**Fit.** One ridge-regularised least-squares fit per card type, in pure Python
(`linear.py`) — no numpy, because the largest problem here is 47 rows by 6
columns. Ridge rather than plain OLS because the groups are small and the
features correlate (a Tier 3 Creature has more Health *and* more Defence), which
makes `X'X` near-singular and an unregularised solve produce huge cancelling
weights that fit the sample and mean nothing.

The solver is checked against a rule it was never shown: `check_balance_math` in
`tests/run_tests.py` builds 24 synthetic cards from `cost = 1 + 2*tier +
0.5*health` and requires the fit to recover all three within 0.15. Same
principle as the profile-math check — a solver validated only on the data it was
tuned for is unfalsifiable.

**Findings.** A card is reported when its residual is at least
`threshold_z` sigmas (default 1.75) *and* at least `threshold_abs` of cost
(default 1.0). The second condition exists so a group with a tight spread does
not report rounding as a defect.

## The four things it cannot see

Every one of these is a legitimate reason for a card to sit off the curve. Check
them before calling anything a defect.

1. **How strong an ability is.** `has_ability` is a yes/no. "Deal 1 damage" and
   "take an extra turn" are the same feature value. This is the big one, and it
   is why every finding goes to a human who reads the card text.
2. **Drawbacks.** A card whose text costs its owner something reads as
   undercosted to the fit, correctly and unhelpfully.
3. **Interaction and archetype.** A card that is weak alone and central to a
   deck is invisible here; so is a card that only matters against one opponent.
4. **Deliberate rarity or flavour.** A signature card priced as a statement is
   not a mispriced card.

## Reading `n` and `r2` honestly

Both are reported per group and both belong in anything you say about a finding.

- `r2` near 0.85 (Creature, n=47) means the printed numbers really do explain
  the cost, and a large residual is genuinely unusual.
- `r2` near 0.2 (Spell, n=10) means the model barely explains anything, so a
  "2 sigma outlier" is 2 sigmas of noise. Report it as a question about the
  *type*, not about the card.
- A group under 5 cards is not fitted at all; its costs are listed, not judged.
- A group with fewer cards than features + 3 is reported as underdetermined in
  the group's `note` field. Pass that note through.

## When the deck changes

Re-costing one card moves the curve for its whole type. Always re-run after a
change, and expect the finding list to be different rather than one shorter.
