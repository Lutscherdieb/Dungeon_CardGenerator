# The cost model

Load this when you are pinning a weight, changing a threshold, or reading what
the deck currently charges for a point of something.

**Two halves, and they must agree.** The prose is the author's stated intent; the
`json` block below is the only part the tool reads. When the author rules that a
weight is wrong, write the sentence *and* change the block, in the same edit.

## How an override behaves

- `cost_weights` — multiplies a resource in the target. `{"Food": 0.5}` says a
  Food is worth half a Mana. Default 1.0 each.
- `weights` — pins a feature's weight for one card type. The fit then holds it
  fixed and fits everything else against what is left, so a pin is a statement
  the model obeys rather than argues with.
- `ignore_features` — drops a feature from a type's fit entirely. Use it when a
  weight is obviously noise rather than wrong: Hero `Movement` is 2 on eleven of
  thirteen heroes, so whatever weight it gets is fitted to two cards.
- `threshold_z` / `threshold_abs` — how far off the curve a card has to be
  before it is reported. Raise `threshold_z` if runs are noisy; raise
  `threshold_abs` if they report rounding.

## Current state: nothing overridden

The model is entirely fitted from the deck, and no author correction has been
recorded yet. The block below is the empty default; the fit as of 2026-08-29 is
in the table further down for reference.

```json
{
  "cost_weights": {},
  "weights": {},
  "ignore_features": {},
  "threshold_z": 1.75,
  "threshold_abs": 1.0
}
```

## The fit on 2026-08-29 (137 cards)

Recorded as a baseline, not as a rule — re-run rather than trusting this table.
`cost = Mana + Cards + Food` throughout.

| Type | n | r² | Expected cost |
|---|---|---|---|
| Creature | 47 | 0.85 | −1.92 + 2.33·Tier + 0.54·has_ability + 0.39·Defence + 0.38·Movement + 0.23·Health + 0.23·activation_cost |
| Hero | 13 | 0.70 | 2.82 + 1.92·Tier − 1.79·Movement + 1.13·activation_cost + 0.23·Defence + 0.11·Health + 0.04·has_ability |
| Overlord | 12 | 0.31 | 2.80 + 0.67·Health + 0.40·has_ability + 0.32·Creatures# + 0.18·activation_cost − 0.13·Defence |
| Research | 11 | 0.59 | 1.51 + 1.96·Tier |
| Room | 23 | 0.47 | 3.73 − 1.19·Roads# + 0.69·activation_cost + 0.49·Treasure + 0.43·Slots# − 0.32·Defence − 0.17·has_ability |
| Spell | 10 | 0.18 | 1.35 + 0.50·Tier |
| Trap | 11 | 0.61 | −0.76 + 1.81·Tier |
| Treasure | 10 | 0.33 | 2.87 + 0.78·Tier |

**What that baseline says, in words.** Creature costing is coherent: a tier is
worth about 2.3 resources and the stat weights are stable and positive. Hero,
Room and Overlord are much looser, and the four text-only types are essentially
"tier plus a constant" because everything else about them is written in prose the
fit cannot read.

**One weight to read as noise, one as a question.** Hero's `−1.79·Movement` is
fitted to two cards: eleven of the thirteen heroes have Movement 2, one has 3 and
one has 1, so the weight describes those two and nothing else. That is a
candidate for `ignore_features` as soon as the author confirms Movement is not
meant to price a hero.

Room's `−1.19·Roads#` is different: Roads# is spread across 23 rooms (2 with none,
6 each with one, two and three exits, 3 with four), so the model is describing a
real pattern — rooms with more exits do cost less in this deck. Whether that is
intended (more exits, more exposed) or accidental is a question for the author,
not noise to suppress.
