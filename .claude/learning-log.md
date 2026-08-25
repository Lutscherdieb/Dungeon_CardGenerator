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

## 2026-08-24 — bound-numeric-fields-from-data-not-intuition
- scope: generic
- status: candidate
- rule: When modelling authored data, put a bound on a numeric field only where the existing data shows the bound or a negative is meaningless; validate the whole corpus against the model before committing it, and treat every rejection as a candidate model bug rather than a data bug.
- home: src/cardgen/model/cards.py (the `Defence` alias and its comment), docs/ARCHITECTURE.md#do-not-bound-a-numeric-field-on-intuition
- evidence: `defence: int = Field(ge=0)` looked obviously right and rejected Shark_Tank, a Room with `"Defence": -1` — defence reads as a modifier as well as a stat. Caught only because all 137 cards were validated against the model before the migration: 136/137, one failure, `Input should be greater than or equal to 0 [type=greater_than_equal, input_value=-1]`.
- applications: 2026-08-24

## 2026-08-24 — give-a-value-one-writer-or-it-will-be-silently-reverted
- scope: generic
- status: candidate
- rule: When a value can be written from two places — a form field and a server-side action that rewrites the same field — remove one of them rather than trying to keep them in sync; if the two must coexist, write a test that performs both in the order a user would and asserts the second did not undo the first.
- home: docs/ARCHITECTURE.md#artwork-belongs-to-the-card-not-to-a-path, tests/check_artwork.py
- evidence: `Background` was an editable form field AND was rewritten server-side by the artwork upload. Uploading then pressing "Save & render" put the old path back, silently discarding the artwork just uploaded — reproduced in a browser before the fix: upload set `./backgrounds/Zzz_Artwork_Probe.jpg`, the stale form restored `./backgrounds/Fireball.png`. Syncing the field after upload fixed the symptom; removing the field entirely (artwork became bytes in the store) removed the class.
- applications: 2026-08-24

## 2026-08-24 — measure-visual-jank-frame-by-frame-before-theorising
- scope: generic
- status: candidate
- rule: When a UI problem is reported as flicker, jank or "it moves twice", sample the relevant computed style every animation frame in a headless browser and count the distinct states before changing any code; report the measurement, not a theory.
- home: tests/check_gallery.py (COLUMN_SAMPLER + column_states, kept as a regression guard), web/app.css comment above the panel-open rule
- evidence: "the gallery resizes twice in short order to different sizes" was exactly right and unguessable from the CSS. Sampling `gridTemplateColumns` per frame showed 6 cols @0ms -> 5 @224ms -> 4 @240ms: animating `padding-right` for 180ms made `auto-fill` recompute the column count at every intermediate width, and the 5-column state lasted 16ms. Removing the transition gives 6 @0ms -> 4 @58ms.
- applications: 2026-08-24

## 2026-08-24 — measure-browser-geometry-never-predict-it
- scope: generic
- status: candidate
- rule: In a browser check, assert an element against its own measured geometry rather than against a number derived from the viewport; record the reference position at runtime and compare movement to it.
- home: tests/check_gallery.py (the "Geometry is measured, never predicted" block)
- evidence: assertions built on `document.documentElement.clientWidth` failed three times in a row against correct application behaviour. It reported 1440 while the position:fixed panel's own right edge sat at 1425, because `html { scrollbar-gutter: stable }` reserves the gutter outside the fixed-position containing block.
- applications: 2026-08-24

## 2026-08-24 — split-a-reformat-from-a-content-migration
- scope: generic
- status: candidate
- rule: When a data migration also changes file formatting, land the reformat as its own commit first and prove it semantically identical to the previous revision; the migration's own diff is then reviewable.
- home: tools/normalize_card_json.py (which refuses to write when reparsing would not reproduce the original object)
- evidence: reformatting 137 card files produced 1987 insertions / 1369 deletions. The field migration that followed touched 23 files and its diff reads as exactly one rename plus one unwrapping per file. Combined, the real change would have been invisible.
- applications: 2026-08-24

## 2026-08-24 — hand-a-long-lived-process-to-a-terminal-the-human-owns
- scope: generic
- status: candidate
- rule: Give every long-lived process a foreground launcher plus a stop script, reserve a separate port for the agent's own throwaway instance, and make closing it part of the definition of done: probe the user's port first and reuse whatever answers, never stop it; start your own on the reserved port; stop it before reporting the task done.
- home: CLAUDE.md#the-gallery-server-servebat-starts-it-and-nothing-claude-starts-outlives-the-turn, PROJECT.md#quality-bars--definition-of-done, serve.bat, stop-server.bat, .vscode/tasks.json
- evidence: a gallery started as a backgrounded process had no window to interrupt and had to be killed through Task Manager. Banning the agent from starting one at all was the wrong correction and the user reversed it the same day ("you may still start/end the server yourself as that is easier for you to also see the servers output", "but these have to be closed by you by the end of these tasks") — the invariant is the close-out, not the abstention, and a reserved port is what keeps the stop command from taking the user's server with it. The two browser checks already assumed the user-owned shape — `tests/check_gallery.py:3` and `tests/check_artwork.py:3` both open with "Needs a server already running::" — so the agent's habit, not the test design, was the outlier. Probe: `GET /api/meta/types` on 127.0.0.1:8765; stranded listener: `netstat -ano | findstr :8765`.
- applications: 2026-08-24

## 2026-08-24 — diff-a-rejected-config-against-one-the-host-accepts
- scope: generic
- status: candidate
- rule: When a host rejects a settings file, diff its shape key-by-key against a file that host already accepts before checking syntax — a config can be valid JSON and still be the wrong shape, and the error text says "failed to parse" either way.
- home: .claude/base-manifest.json (notes.settings_shape)
- evidence: `.claude/settings.json` carried `"enabledPlugins": ["base@claudebase"]`. `python -c "import json; json.load(...)"` reported it valid; Claude Code still reported the settings file as failing to parse. `~/.claude/settings.json` had the accepted shape three lines away: `"enabledPlugins": {"base@claudebase": true}` — an object map, not a list.
- applications: 2026-08-24

## 2026-08-24 — point-the-second-dependency-list-at-the-first
- scope: generic
- status: candidate
- rule: When a project has two files that could both list dependencies, make the secondary one point at the primary (`-e .`) instead of restating it; a restated list is not a convenience, it is a second source of truth that will be wrong the next time a dependency is added.
- home: requirements.txt (its header comment)
- evidence: `requirements.txt` listed 3 of the 7 dependencies in `pyproject.toml` — missing pillow, pydantic, SQLAlchemy and CherryPy. `pyproject.toml:11` already carried the scar: "Imported by the renderer since day one; the old requirements.txt never listed it, so a fresh clone failed at `from PIL import Image`." The comment documented the hazard instead of removing it, and the file drifted three more dependencies further.
- applications: 2026-08-24

## 2026-08-25 — put-a-detector-on-every-deliberately-silent-fallback
- scope: generic
- status: candidate
- rule: A fallback that exists so bad input stays visible must be paired, in the same edit, with a check that fails when anything actually reaches it. "Degrade gracefully" and "tell nobody" are two decisions, not one — take only the first.
- home: tests/check_gallery.py (the per-type "json-fallback" block and the docstring bullet naming it), docs/ARCHITECTURE.md (`src/cardgen/render/` and `src/cardgen/web/` — the gallery)
- evidence: `web/app.js` routed an unrecognised field shape to a raw-JSON textarea "rather than disappearing: a field you cannot see is a field you cannot fix" — a deliberate, documented choice. The array branch tested one level of nesting (`items?.type === 'array' && items.prefixItems`) and `Slots` is `List[List[SlotSpot]]`, so `buildSlots` — 40 lines with its own group/spot editor — had never once run, and every Room offered a JSON blob instead. Nothing reported it because the fallback is silent by design. The detector added with the fix opens one card of each of the 8 types and reports `json-fallback=none` for all of them.
- applications: 2026-08-25

## 2026-08-25 — call-a-windows-batch-file-by-absolute-path-through-cmd
- scope: generic
- status: candidate
- rule: From a Bash-style shell on Windows, invoke a repo `.bat` as `cmd //c "<absolute path>.bat" <args>`. Never `cmd //c name.bat` (the `//c` rewrite loses the working directory) and never `cmd.exe /c "name.bat args"` (opens an interactive shell and exits). Both fail with exit code 0, so a cleanup step that did nothing is indistinguishable from one that worked — always re-check the state the script was supposed to change.
- home: CLAUDE.md#the-gallery-server-servebat-starts-it-and-nothing-claude-starts-outlives-the-turn (the invocation form and its verification step)
- evidence: `cmd.exe /c "stop-server.bat 8766"` printed the Windows banner and a `<repo root>>` cmd prompt, returned 0, and left PID 12456 listening on 8766; `cmd //c stop-server.bat 8799` printed "'stop-server.bat' is not recognized as an internal or external command"; `cmd //c "<repo root>\stop-server.bat" 8799` printed "Nothing is listening on port 8799." The stranded listener was only visible because the close-out re-ran `netstat`.
- applications: 2026-08-25
