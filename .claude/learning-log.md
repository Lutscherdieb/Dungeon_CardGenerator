# CardGenerator — learning log

Append-only harvest index. **The log is never a rule's home** — the rule itself is written into its owning doc/skill/hook (see CLAUDE.md's write-back task); each entry here just records that it happened, so `/base:promote` can find generic lessons and carry them to ClaudeBase. Every written-back lesson gets its entry **in the same edit** (the `check-lesson-tagging` hook nudges when one is missing its tags).

Entry statuses: `candidate` → `promoted-pr` (PR opened, add the URL) → `merged` | `rejected`. A `scope: generic` candidate with 2+ `applications:` dates is promotion-ready.

The entry shape (copy it, replacing every `<...>` — the angle brackets are what keep
this example from being scanned as a real candidate by `/base:promote`):

```
## <YYYY-MM-DD> — <short-imperative-slug>
- scope: <generic | project>
- status: <candidate>
- rule: <ONE imperative sentence — the rule as written into its home>
- home: <path#section where the rule now lives>
- evidence: <file:line / exact error text / N — the demoted story>
- applications: <date>[, <date>...]
```

## 2026-08-24 — derive-measurements-from-one-module
- scope: project
- status: candidate
- rule: Take every card pixel measurement from a `cardgen.spec` Profile; after any layout or rendering change, grep the geometry literals out of `style.css`, `templates/` and `src/` and confirm none appear outside the spec module.
- home: CLAUDE.md#never-hardcode-a-card-pixel-size--ask-cardgenspec
- evidence: canvas size existed in 4 disagreeing copies across 3 languages — `generate_card.py` `SIZE_PROFILES` (1125), `_gen_spider_side(canvas=1125, bleed=75, safe=975)`, `style.css:393` `width: 1125px`, `templates/_spiderweb.html` `viewBox="0 0 1125 1125"`. All 4 were wrong against MPC's published 1122. The `# add more profiles later (e.g., standard TCG)` comment had gone unimplemented because a size change was a four-language edit.
- applications: 2026-08-24

## 2026-08-24 — verify-a-derivation-against-a-case-it-does-not-serve
- scope: generic
- status: candidate
- rule: When deriving values from an external specification, assert the derivation reproduces a published figure for a case the project does NOT use — a formula checked only against the numbers it was built for is unfalsifiable.
- home: REFERENCES.md#makeplayingcards-print-specification (comparison procedure step 3), asserted by tests/run_tests.py
- evidence: MPC publishes no pixel figure for the 3.5in square size this project prints, only for poker (2.5x3.5in → 822x1122). Checking `trim_in * 300 + 72` against poker is what proves the square numbers; the old `1/8" bleed → 1125` derivation looked self-consistent and was wrong by 3px.
- applications: 2026-08-24

## 2026-08-24 — separate-decided-rules-from-parked-ideas-in-a-reference
- scope: generic
- status: candidate
- rule: When a declared reference mixes decided specification with parked ideas and nothing marks which is which, record that mixing as a named blind spot on the reference entry, and ask the author before implementing from it.
- home: REFERENCES.md#game-rules-and-design-notes (known blind spots)
- evidence: `Rules/Cardtypes.txt` lists Overlord and Creature under "tcg format". Read as a spec, that produced a confident report that 59 of 137 cards (43%) were rendered at the wrong physical size. It was an intention left open — every card type is square. The user's correction: "the cards should all be square cards it was just left open for later to implement other format cards."
- applications: 2026-08-24
