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

### `templates/` and `style.css`

Nine per-type templates over shared partials (`_costs_box`, `_spiderweb`, `filters_defs`). Theming is data-attribute driven: `body[data-type]`, `body[data-subtype]`, `body[data-faction]` and `body[data-tier]` select CSS custom-property blocks, so a card's colours follow from its data rather than from template branching.

### `schemas/`

One JSON Schema per card type, used both to validate and to *identify* a card. They are hand-maintained and have drifted from each other — see the decisions below.

## Decisions & reversals

### Geometry is data, in exactly one module (2026-08-24)

**Why:** the canvas size previously existed in four independent copies — `SIZE_PROFILES`, the `_gen_spider_side` defaults, `style.css`, and the `_spiderweb.html` `viewBox` — spread across three languages. All four had drifted from the published spec, and the `# add more profiles later (e.g., standard TCG)` note had gone unimplemented for a year because adding a size was a four-language refactor rather than a data change.

**Consequence:** a new card format is one `Profile` plus one `_TYPE_TO_PROFILE` row. Nothing else in the codebase learns about it.

### Assertions live in the pipeline, not in a test suite (2026-08-24)

**Why:** the promise of this project is that measurements are right. A test can be skipped, can go unrun, and only covers the cards someone remembered to add. `assert_png` runs on every image the renderer writes, so a wrong-sized card cannot reach the output directory at all. `tests/run_tests.py` exists as well, but as a gate over the derivation and over all nine templates — not as the only line of defence.

### The full-bleed PNG is the deliverable (2026-08-24)

`<Name>.png` at the canvas size is what MakePlayingCards receives. `_trim` and `_safe` are inspection aids. Playwright writes no DPI metadata, so the full-bleed file is re-saved through Pillow to stamp 300 DPI before it is asserted.

### Not yet done: one card model

The card shape is currently defined three times — eight hand-written JSON Schemas, the Jinja context each template expects, and (on the abandoned REST branch) a SQLAlchemy model. They already disagree: `Type` is required by five schemas and optional in three, `additionalProperties` is `false` in four and `true` in four, and the two splits do not line up. A single pydantic discriminated union should generate the schemas and the DB columns. Tracked in PROJECT.md's direction notes.

### Reversed: "Overlord and Creature print at TCG size"

Reported as a defect on 2026-08-23 on the strength of `Rules/Cardtypes.txt`, which lists those two types under "tcg format". **Reversed 2026-08-24:** every card type is square. That line records an intention that was left open, not a specification. Kept here because the file still says it and the next reader will draw the same conclusion — see the `Rules/` blind-spot note in REFERENCES.md.
