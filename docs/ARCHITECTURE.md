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
| `verify.py` | `assert_png()` refuses a written image whose size or DPI does not match its profile. `check_artwork()` warns (never blocks) when user-supplied art is smaller than the safe zone |

`_TYPE_TO_PROFILE` is deliberately empty: every card type is square, so every lookup falls through to `DEFAULT_PROFILE`. That empty dict *is* the answer to "which types print at which size", not a stub.

### `generate_card.py` — the renderer

Currently a single top-level module; being folded into `src/cardgen/render/`. Its stages:

1. **Type detection** (`detect_type`) — trust `Type` if present, validate against that type's schema, otherwise try every schema until one matches.
2. **Context transform** (`transform_context`) — inline icon substitution, `RoadsSet` normalisation.
3. **Template selection** — `<type>_template.html`, with `room` + subtype `hearth` diverting to `room_hearth_template.html`.
4. **Render** — Jinja to HTML with the artwork inlined as base64, then Chromium to PNG at the profile's canvas size, stamped to 300 DPI and asserted.
5. **Crop** — safe and trim PNGs from the profile's boxes, each asserted.

### `src/cardgen/store/` — the card store

SQLite behind the model. The validated card is stored **whole**, as JSON, in its JSON key spelling; the scalar columns beside it (`type`, `name`, `subtype`, `faction`, `tier`) exist only so the gallery can list and filter without parsing every row, and are derived on write by `index_fields` rather than passed in — so they cannot disagree with the JSON they came from. Adding a field to the model therefore needs no schema change here at all.

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

The gallery's edit form is generated from the card type's JSON Schema, so a new field on the model appears in the form with no frontend change. The schema carries `x-key-order` — the same order `to_json_dict` writes — so the form and the exported file agree without JavaScript restating the list. A field whose shape the builder does not recognise falls back to a JSON box rather than disappearing: a field you cannot see is a field you cannot fix.

### `templates/` and `style.css`

Nine per-type templates over shared partials (`_costs_box`, `_spiderweb`, `filters_defs`). Theming is data-attribute driven: `body[data-type]`, `body[data-subtype]`, `body[data-faction]` and `body[data-tier]` select CSS custom-property blocks, so a card's colours follow from its data rather than from template branching.

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

### Do not bound a numeric field on intuition

`defence` carries no lower bound. A `ge=0` guess rejected `Shark_Tank`, a Room with `Defence: -1` — defence reads as a modifier as well as a stat. Bound a field only where the data shows the bound, or where a negative is meaningless (health, movement, tier, and the cost fields).

### Reversed: "Overlord and Creature print at TCG size"

Reported as a defect on 2026-08-23 on the strength of `Rules/Cardtypes.txt`, which lists those two types under "tcg format". **Reversed 2026-08-24:** every card type is square. That line records an intention that was left open, not a specification. Kept here because the file still says it and the next reader will draw the same conclusion — see the `Rules/` blind-spot note in REFERENCES.md.
