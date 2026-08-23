# CardGenerator — external references & ground truths

**Every reference here is read-only: read freely, write never, at every entry point.** The `protect-references` hook blocks writes to declared paths; a deliberate exception is flipping `modules.references` off in `.claude/base-manifest.json` (visible, logged), never a quiet edit. If a task seems to require changing a reference, stop and warn the user.

This file is the single source of truth for references. The manifest's `readonly_refs` mirror is **generated from the entry frontmatter blocks below**. Never hand-edit the mirror; `/base:doctor` check 10 and `/base:doc-audit` both check agreement. Machine-local paths live in gitignored `references.local.json` (`{"<id>": "<absolute local path>"}`) **at the repo root** — that exact location is where the hooks look, and a copy under `.claude/` is silently ignored, leaving every local reference unguarded. Bound per-machine by `/base:repo-setup`.

## Ground-truth routing

| Domain / question | Reference | Access method | Escalation when it runs out |
|---|---|---|---|
| Any print measurement: upload size, bleed, safe area, DPI, what a card size is called | `mpc-print-spec` | `WebFetch https://www.makeplayingcards.com/faq-photo.aspx` | Download MPC's own template file for the size and measure it; ask MPC support for sizes they do not publish |
| What a card type is, what a cost or symbol means, which types exist | `game-rules` | `Read Rules/*.txt` | Ask the user — they are the author. Never infer a rule from the card data or the templates |
| Whether a line in `Rules/` is decided or still open | `game-rules` | `Read Rules/ToDo.txt` and `Rules/Ideas.txt` first | Ask the user. Parked ideas read exactly like specifications |

## Registry

## MakePlayingCards print specification

```yaml
id: mpc-print-spec
kind: website
readonly: true
local: false
committed_path: null
url: https://www.makeplayingcards.com/faq-photo.aspx
volatility: live
```

- **Access method:** `WebFetch https://www.makeplayingcards.com/faq-photo.aspx`. The per-product pages (for example `/design/custom-square-cards-deck.html`) list which sizes exist; the FAQ page carries the pixel figures.
- **Comparison procedure:**
  1. Read the two figures MPC states per side at 300 DPI: bleed outside the trim line, and safe-area margin inside it. Both were 36px as of 2026-08-24.
  2. Check they still match `MPC_BLEED_PX` and `MPC_SAFE_MARGIN_PX` in `src/cardgen/spec/profiles.py`.
  3. Check the derivation still reproduces a published figure for a size we do **not** print — poker, 2.5in x 3.5in, uploads at 822 x 1122 px. `tests/run_tests.py` asserts this. A formula that only satisfies our own square numbers is unfalsifiable.
- **Known blind spots / failed approaches:**
  - MPC's FAQ table lists minimum upload pixels only for its most common sizes. "Large Square" (3.5in x 3.5in — the size this project prints) is listed as a product but **without** a pixel figure, so its numbers are derived from the stated per-side bleed rather than read off directly. That is why step 3 above cross-checks against a size that *does* publish its pixels.
  - Do not take print numbers from comments in this repo. `SIZE_PROFILES` claimed `1/8" bleed each side -> 1125x1125`; MPC specifies 36px per side, giving 1122. The Readme had it right and the code had drifted, so recency of the file is no guide.
  - MPC quotes bleed as `1/8"` in prose but `36 pixels` in figures. 1/8in at 300 DPI is 37.5px. **The pixel figure is the operative one** — the prose is rounded.

## Game rules and design notes

```yaml
id: game-rules
kind: document
readonly: true
local: false
committed_path: Rules
url: null
volatility: live
```

- **Access method:** `Read Rules/Rules.txt`, `Rules/Cardtypes.txt`, `Rules/Content.txt`, `Rules/ToDo.txt`, `Rules/Ideas.txt`.
- **Comparison procedure:** card data, schemas and templates must agree with `Rules/` on card types, cost notation and creature-type names. Where they disagree, `Rules/` wins as a statement of intent — but raise the disagreement with the user rather than editing either side. The user is the author of both.
- **Known blind spots / failed approaches:**
  - **These files mix decided rules with parked ideas, and nothing marks which is which.** `Rules/ToDo.txt` is explicitly open questions, `Rules/Ideas.txt` is a wishlist, and `Rules/Cardtypes.txt` contains both. Reading it as a specification produced a confident, wrong report that 59 of 137 cards were rendered at the wrong physical size, on the strength of the line `tcg format / - Overlord / - Creature`. Every card type is square; that line was an intention left open. Ask before implementing.
  - `Rules/Rules.txt` numbers its turn phases 1-10 but lists them out of order with `?` prefixes on the unsettled ones. The prefixes are meaningful.
