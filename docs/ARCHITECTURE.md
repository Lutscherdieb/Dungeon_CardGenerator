# CardGenerator — architecture

## Overview

A card is data plus artwork; a print-ready card is that data laid out at exact physical measurements. The pipeline is deliberately a browser render rather than a drawing library, because the layout language (flexbox, custom properties, SVG filters, web fonts) is far better at typography and per-type theming than any Python canvas API — and because a card page can be opened and inspected by hand.

```
  card JSON ──▶ detect + validate ──▶ Jinja template ──▶ HTML page
                (schemas/)             (templates/)          │
                                                             ▼
                        Profile ──▶ CSS variables ──▶ headless Chromium
                   (cardgen.spec)          │                  │
                        │                  │                  ▼
                        │                  └──▶ SVG viewBox   full-bleed PNG
                        │                                     │
                        └──────────────▶ crop boxes ──────────┤
                                                              ▼
                                              assert_png ──▶ trim + safe PNGs
```

The single structural rule: **the `Profile` is upstream of every pixel.** Python takes the Playwright viewport and the Pillow crop boxes from it; CSS takes `--canvas-w`, `--safe-w` and `--frame-inset` from it; the spiderweb overlay takes its SVG `viewBox` from it. Nothing measures anything on its own.

## Components

### `src/cardgen/spec/` — print geometry

The only place a card pixel size may come from.

| Module | Role |
|---|---|
| `profiles.py` | `Profile` derives canvas / trim / safe boxes from physical inches, DPI, and MakePlayingCards' per-side bleed and safe-margin figures. `profile_for_type()` maps a card type to its format |
| `css.py` | Renders a `Profile` into the `:root` custom properties every card page needs. `style.css` declares no geometry of its own, so a missing block breaks the layout visibly rather than silently falling back |
| `verify.py` | `assert_png()` refuses a written image whose size or DPI does not match its profile. `artwork_warnings()` warns (never blocks) when user-supplied art is smaller than the safe zone — one home for that wording, used by both the upload and the file-based CLI |

`_TYPE_TO_PROFILE` is deliberately empty: every card type is square, so every lookup falls through to `DEFAULT_PROFILE`. That empty dict *is* the answer to "which types print at which size", not a stub.

### `generate_card.py` — the renderer

Currently a single top-level module; being folded into `src/cardgen/render/`. Its stages:

1. **Type detection** (`detect_type`) — trust `Type` if present, validate against that type's schema, otherwise try every schema until one matches.
2. **Context transform** (`transform_context`) — inline icon substitution, `RoadsSet` normalisation.
3. **Template selection** — `<type>_template.html`, with `room` + subtype `hearth` diverting to `room_hearth_template.html`.
4. **Render** — Jinja to HTML with the artwork inlined as base64, then Chromium to PNG at the profile's canvas size, stamped to 300 DPI and asserted.
5. **Crop** — safe and trim PNGs from the profile's boxes, each asserted.

### `src/cardgen/store/` — the card store

SQLite behind the model. The validated card is stored **whole**, as JSON, in its JSON key spelling; the scalar columns beside it (`type`, `name`, `subtype`, `faction`, `tier`) exist only so the gallery can list and sort without parsing every row, and are derived on write by `index_fields` rather than passed in — so they cannot disagree with the JSON they came from. Adding a field to the model therefore needs no schema change here at all.

**Artwork is stored as bytes, in the row.** The `artwork` column is deferred, so listing 137 cards does not drag ~227 MB of image data along to draw their names; the image is fetched from `GET /api/cards/{id}/artwork`, which is the only endpoint that returns something other than JSON.

| Module | Role |
|---|---|
| `db.py` | Engine, session, `init_db`. `CARDGEN_DB_URL` overrides the default `data/cards.db` |
| `models.py` | `CardRow`. Every key `as_dict()` returns is backed by a real column or by `data` |
| `repo.py` | The only way in or out. Validates through the model before writing, and re-derives the index columns on every update |

`import_json_files` skips a card whose `Name` is already stored, so re-running an import cannot silently duplicate the deck. `export_json_files` writes back to the filename a card was imported from, and the round trip is byte-exact across all 137 cards — which makes "export over `data/Mixed` and `git diff`" a real integrity check.

### `src/cardgen/render/` and `src/cardgen/web/` — the gallery

`render/service.py` resolves paths and updates the store; every pixel is delegated to `generate_card`. `generate_html` accepts a dict as well as a file path, which is what lets the gallery share the CLI's pipeline instead of growing one beside it. Renders land in `out/gallery/<card_id>/`, one directory per card, so a re-render replaces its predecessor rather than accumulating timestamped copies.

`web/` is a CherryPy app plus a single background render thread. One worker is deliberate — rendering launches Chromium, so it cannot happen inside a request, and a second concurrent browser buys nothing on one machine.

The `/api` mount turns CherryPy's `trailing_slash` tool **off**. CherryPy treats a class with an `index` method as a directory and 301s `/api/cards` to `/api/cards/`; harmless for a GET, but a redirected POST is not guaranteed to keep its method or body.

`render/symbols.py` owns the `[Token]` table — the codes a Description may contain and the icon each prints. It is the one home for that list: `generate_card` imports the substitution from it, `GET /api/meta/tokens` serves it to the gallery's code legend, and the matching regex is **derived from the dict's keys** rather than hand-typed beside it. The two used to be separate literals inside `generate_card.py`; they agreed only by inspection, and adding a token to one without the other would have made it print as literal text with nothing to report it.

### `web/` — the gallery frontend

Plain ES modules, no build step and no dependency: the server already serves `web/` as static files, so `<script type="module">` is the whole toolchain.

| Module | Role |
|---|---|
| `app.js` | Boot and wiring only. No behaviour of its own |
| `api.js` | The single fetch path, and the only place errors are shaped |
| `dom.js` | `$`, `el()`, `banner()`, `fileSize()` |
| `state.js` | The card cache, the open card, its draft |
| `schema.js` | Per-type JSON Schemas, print profiles, `blankCard()` |
| `icons.js` | Which `assets/*.png` exist, and the `<img>` for one |
| `cards.js` | Loading the deck, refreshing one card |
| `grid.js` | Tiles, selection, and where the inline editor sits |
| `form.js` | The schema-driven card-data form |
| `codes.js` | The `[]` icon-code legend under the Description field |
| `render.js` | Render status and polling |
| `editor.js` | The open card: preview, artwork, form, actions |
| `popover.js` | Floating-panel chrome, shared by the two below |
| `filters.js` | The filter panel, derived from the schemas |
| `newcard.js` | The New card dialog |

**The module graph is acyclic by construction**, which is the reason for two indirections that would otherwise look like ceremony: `grid.js` does not import `editor.js` — clicking a tile dispatches a `card:select` event that `app.js` routes — and `cards.js` does not import the chrome — `loadAll()` fires `cards:loaded` for anything that derives choices from the deck.

The edit form is generated from the card type's JSON Schema, so a new field on the model appears in the form with no frontend change. The schema carries `x-key-order` — the same order `to_json_dict` writes — so the form and the exported file agree without JavaScript restating the list. A field whose shape the builder does not recognise falls back to a JSON box rather than disappearing: a field you cannot see is a field you cannot fix. That fallback is silent by design, so `tests/check_gallery.py` opens one card of every type and fails if any field lands in it — the `Slots` editor was unreachable for exactly that reason (the builder tested one level of array nesting and `Slots` was then `List[List[Tuple[CreatureType, int]]]`). Add a branch to `form.js` whenever the model grows a shape it does not name; `boolean` was added for `Starter` for exactly that reason.

Each field is one row — `[icon] label | control` — and the explanations that used to print under a control are the row's `title` instead, marked with a dotted underline so an invisible tooltip is still discoverable. The icon is the one the card actually prints: `/api/meta/icons` lists the stems under `assets/`, and the form resolves a name to `assets/<name lowercased>.png` exactly as the templates do, trying the field's key first and its value second — so `Mana` shows `mana.png`, `Faction: Wild` shows `wild.png` and follows the select. Neither side keeps a list of which fields have an icon; a PNG dropped into `assets/` starts appearing on its own.

**The filter panel is derived the same way.** `filters.js` unions the properties of every card type's schema and picks a control from each one's JSON Schema shape — `const` and `enum` become chip sets, `boolean` an any/yes/no toggle, `integer` a min–max pair, `string` a contains box, and an array of enums a "has any of" chip set. Two facets that are not card fields, render status and whether artwork was uploaded, are declared explicitly. Filtering happens client-side because `GET /api/cards` already returns every card's whole JSON. Active filters persist in `localStorage`, and the topbar reports "N of 137" whenever a filter is hiding anything.

### `src/cardgen/balance/` — cost analysis

Fits a cost model per card type from the cards in the store and reports the ones that do not fit it. Driven by `python -m cardgen.cli balance`, and by the `/card-balance` skill that puts each finding to the author.

| Module | Role |
|---|---|
| `features.py` | Reads the target and the features off the card's own JSON Schema — costs are the properties marked `x-cost`, features are every other integer, list length and boolean, plus `has_ability` and `activation_cost` parsed out of the Description |
| `linear.py` | Ridge-regularised least squares in pure Python: normal equations plus Gaussian elimination with partial pivoting |
| `report.py` | One fit per card type, the residual per card, and the outliers |
| `config.py` | Reads the author's overrides and rulings out of the skill's own markdown reference files |

**Nothing here lists a field name.** `x-cost` is set on `CardBase` via `json_schema_extra`, so the generated schema carries it and the balance module derives the cost set from the same artefact the gallery form and filter panel read. A fourth resource would be picked up with no edit to this package.

**No numpy.** The largest problem in the deck is 47 rows by 6 columns; adding a compiled dependency to a card generator to solve that would be the wrong trade. Ridge rather than plain least squares because the groups are small and the features correlate — a Tier 3 Creature has more Health *and* more Defence — so an unregularised solve produces large cancelling weights that fit the sample and mean nothing.

**The solver is checked against a rule it was never shown.** `check_balance_math` in `tests/run_tests.py` builds 24 synthetic cards from `cost = 1 + 2*tier + 0.5*health` and requires the fit to recover all three coefficients within 0.15. Same principle as the profile-math check: a solver validated only on the data it was tuned for is unfalsifiable.

**The judgment is not in this package.** A residual says a card is priced differently from its peers; only a person reading its rules text can say whether that is a mistake or a drawback the numbers cannot see. So `/card-balance` presents each finding, and records the verdict in `.claude/skills/card-balance/references/rulings.md`, which `config.py` reads back on the next run — that loop is what stops the same cards being reported forever.

### `templates/` and `style.css`

Nine per-type templates over shared partials (`_costs_box`, `_spiderweb`, `filters_defs`, `_creature_strip`, `_starter_stamp`). Theming is data-attribute driven: `body[data-type]`, `body[data-subtype]`, `body[data-faction]` and `body[data-tier]` select CSS custom-property blocks, so a card's colours follow from its data rather than from template branching.

`_creature_strip.html` draws a boxed row of creature-type icons from a `strip` variable, and both types that have such a list use it: the Overlord's starting creature pool and a Room's creature spots. `_starter_stamp.html` is included by all nine and prints nothing unless the card carries `Starter: true`; the stamp is CSS text, not an asset, so it inherits `--frame-border-color` and themes per type and tier on its own.

### `src/cardgen/model/` — the card definition

| Module | Role |
|---|---|
| `cards.py` | One pydantic discriminated union over `Type`. Python attributes are snake_case; every field carries a generated capitalised alias, so `model_dump(by_alias=True)` is exactly the dict the templates and the JSON files use |
| `schemas.py` | Emits `schemas/*.schema.json` from the union — `python -m cardgen.model.schemas` |

### `schemas/`

One JSON Schema per card type, used both to validate and to *identify* a card. **Generated** from `model/cards.py`; the files stay committed so editors can use them and so a diff signals a model change. The verify gate fails if they are stale.

## Decisions & reversals

### Geometry is data, in exactly one module (2026-08-24)

**Why:** the canvas size previously existed in four independent copies — `SIZE_PROFILES`, the `_gen_spider_side` defaults, `style.css`, and the `_spiderweb.html` `viewBox` — spread across three languages. All four had drifted from the published spec, and the `# add more profiles later (e.g., standard TCG)` note had gone unimplemented for a year because adding a size was a four-language refactor rather than a data change.

**Consequence:** a new card format is one `Profile` plus one `_TYPE_TO_PROFILE` row. Nothing else in the codebase learns about it.

### Assertions live in the pipeline, not in a test suite (2026-08-24)

**Why:** the promise of this project is that measurements are right. A test can be skipped, can go unrun, and only covers the cards someone remembered to add. `assert_png` runs on every image the renderer writes, so a wrong-sized card cannot reach the output directory at all. `tests/run_tests.py` exists as well, but as a gate over the derivation and over all nine templates — not as the only line of defence.

### The full-bleed PNG is the deliverable (2026-08-24)

`<Name>.png` at the canvas size is what MakePlayingCards receives. `_trim` and `_safe` are inspection aids. Playwright writes no DPI metadata, so the full-bleed file is re-saved through Pillow to stamp 300 DPI before it is asserted.

### One card model, and the schemas are build products (2026-08-24)

**Why:** the card shape was defined three times — eight hand-written JSON Schemas, the Jinja context each template expects, and a SQLAlchemy model on the abandoned REST branch. They had already disagreed: `Type` was required by five schemas and optional in three, `additionalProperties` was `false` in four and `true` in four, and the two splits did not line up. `Food` was declared in all eight and used by one card.

**Consequence:** `model/cards.py` owns the shape and `schemas/` is generated from it. All 137 cards validate against the model and round-trip through it losslessly, which is how the model was proved to match reality rather than an idea of it.

**Two field changes shipped with it,** migrated by `tools/migrate_20260824_unify_text_flatten_slots.py` (kept, idempotent, refuses to write unless every migrated card validates):

- Rooms stored their text in `Rules` and the other seven types in `Description`. Unified on `Description` — the game's own word, per `Rules/Rules.txt:34`, "Costs are defined in front of a ':' within the description of a card."
- `Slots` was a list of single-key objects whose `"1"`/`"2"`/`"3"` keys were always the 1-based index and were never read — `room_template.html` iterated `slot.values()`. Now a plain list of lists. The inner `[type, number]` spots are untouched: the number is 0 on 64 of 66 spots and 2 on the two `Sacred_Hain` spots, and `Rules/Ideas.txt` lists slot requirements as an idea rather than a rule, so what it means is a question for the author.

### The store holds the card as JSON, not as columns (2026-08-24)

**Why:** giving SQL a second opinion about the card shape is precisely how the earlier REST sketch broke. `Card.as_dict` read `self.png_full`, `self.png_safe` and `self.png_trim` — three attributes that were never columns on the model — so every request that listed cards raised `AttributeError` and returned 500. The gallery on that branch could never have loaded.

**Consequence:** the model owns the shape, SQL stores and indexes. `CardRow.as_dict` can only return keys backed by a real column or by `data`, and the index columns are computed by one function on write.

### Export writes back to the filename a card came from (2026-08-24)

Four cards have been renamed without their file being renamed: `Magic_Sentry.json` holds "Battledroid", `Timeless_Horror.json` holds "Chaos Overseer", `Monster_in_a_Bottle.json` holds "Bottled Monster", and `Chaos_Imprisionment.json` holds "Chaos Imprisonment" (the filename has the typo, not the card). Deriving the export filename from `Name` would write a second file beside each of those instead of updating it, so `export_filename` prefers the recorded `source_path`.

### Artwork belongs to the card, not to a path (2026-08-24)

**Why:** `Background` was a string field holding `./backgrounds/Something.png`. That made the user responsible for filenames, let the JSON and the file tree drift apart (four cards already pointed at files named after their *previous* name), left orphans behind on rename, and — worst — gave one concept two writers. The artwork upload rewrote `Background` server-side while the open form still held the old value, so the next **Save & render silently reverted the artwork that had just been uploaded**. Measured, not theorised: `tests/check_artwork.py` reproduced it before the fix.

**Consequence:** `Background` is no longer a card field at all. The bytes live in the row; an upload simply replaces them; nothing in the form refers to artwork, so no save can revert it. The renderer wanted bytes anyway — it base64-inlines the image into the card HTML either way, so a path was an indirection that bought nothing.

**`Background` survives as an interchange-only key** (`model.TRANSPORT_KEYS`). Import reads it to find the image to load; export writes the image back out and emits it again. That keeps `data/Mixed` plus `backgrounds/` a complete, git-diffable copy of the deck, which matters because the database is gitignored. `parse_card` strips transport keys, so a card JSON straight off disk still validates.

**Export is the only thing that writes artwork to disk.** An upload touches the store alone, so the file tree cannot drift underneath it unnoticed; `cardgen export` is the deliberate moment the two are reconciled. Verified byte-exact: 137/137 JSON files and 137/137 images.

### The editor is a grid item, not a drawer (2026-08-29)

**Reverses the right-hand drawer** shipped on 2026-08-24. The editor is now a full-width `<section>` placed *inside* the grid, on the row below the card it belongs to; tiles below it shift down and nothing shifts sideways.

**Why:** the drawer narrowed the grid to make room for itself. `auto-fill` recomputes the column count at the new width, so all 137 tiles were repositioned on open and again on close — the author's report was that opening or closing the editor lost their place in the gallery. The 2026-08-24 fix removed the *animated* reflow (6 → 5 → 4 columns in 180 ms) but not the reflow itself; the geometry of a side panel makes one unavoidable.

**Consequence:** the grid's own width never changes, so the column count cannot change. `tests/check_gallery.py` asserts exactly that — column count, grid width and the clicked tile's x position are all recorded before opening and compared after, and the frame sampler must now see a *single* column state rather than "at most two". The same reasoning makes the filter panel and the New card dialog floating popovers (`popover.js`) rather than anything that displaces the grid.

`grid.js` measures the column count from the resolved `gridTemplateColumns` track list. Measured, never predicted: nothing about the viewport width turns into that number reliably, as `scrollbar-gutter` reserving space outside `documentElement.clientWidth` has already demonstrated. The clicked tile's viewport position is recorded before insertion and the page scrolled by the difference after, so the card you clicked stays under the cursor.

### Room slots are a flat list, and they print where the Overlord's do (2026-08-29)

`Room.Slots` was `List[List[Tuple[CreatureType, int]]]` — groups of `(type, number)` spots — and printed as a column of 102px circles at the top left. It is now `List[CreatureType]`, printed through the same `_creature_strip.html` partial the Overlord's `Creatures` uses.

**Why:** the outer grouping was layout rather than data. All 23 rooms had exactly three groups and the third was empty on every one of them, so it carried no information the renderer could not derive. Two shapes and two visual languages for one concept — "a list of creature types this card cares about" — meant two editors in the form and two blocks of CSS.

**Consequence:** the gallery's 40-line `buildSlots` group/spot editor is gone; the existing tag-list branch, which `Overlord.Creatures` already used, picks `Slots` up with no new code. `.slot`, `.slot-icon`, `.slot-icon-wrapper`, `.slot-count`, `--slot-size` and `--slot-text-color` are gone from `style.css`.

### Reversed: "the second number in a Slots spot means something" (2026-08-29)

Recorded as an open question on 2026-08-24 — 0 on 64 of 66 spots, `2` on the two `Sacred_Hain` spots whose text mentioned "[Wild] with Level 1", and `Rules/Ideas.txt` listing slot requirements as an *idea*. **Answered by the author on 2026-08-29: it means nothing, and the two exceptions were cleared in the gallery before the migration.** Every spot in the store read 0, so flattening lost nothing. Kept here because the question was a reasonable one and the next reader of the old JSON in git history will ask it again.

### `Starter` is on `CardBase`, so every type carries it (2026-08-29)

A boolean marking a card that ships in the starting deck; it prints as a small rotated corner stamp. It sits on the base class rather than on the six deck-buildable types, because every downstream consumer — the JSON Schemas, the gallery form, the filter panel — derives from the model, so putting it in one place makes it appear in all of them and a ninth card type cannot be added and forget it. `Hero` and `Overlord` carry a flag that means nothing for them; that is cheaper than a mixin the next type has to remember to inherit.

`Hero.Treasure` landed in the same change — how much treasure a hero drops as loot when slain. It shares one `TreasureCount` alias with `Room.treasure` so the two cannot drift. The alias is deliberately **not** named `Treasure`: that is already a card-type class in the same module, and with `from __future__ import annotations` the shadowing would only surface if pydantic ever re-resolved the annotation.

### Do not bound a numeric field on intuition

`defence` carries no lower bound. A `ge=0` guess rejected `Shark_Tank`, a Room with `Defence: -1` — defence reads as a modifier as well as a stat. Bound a field only where the data shows the bound, or where a negative is meaningless (health, movement, tier, and the cost fields).

### Reversed: "Overlord and Creature print at TCG size"

Reported as a defect on 2026-08-23 on the strength of `Rules/Cardtypes.txt`, which lists those two types under "tcg format". **Reversed 2026-08-24:** every card type is square. That line records an intention that was left open, not a specification. Kept here because the file still says it and the next reader will draw the same conclusion — see the `Rules/` blind-spot note in REFERENCES.md.
