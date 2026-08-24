# CardGenerator

Generate print-ready boardgame card images at exact MakePlayingCards measurements from card data plus artwork.

## Status

Mid-restructure, on branch `v2`.

**Done:** print geometry is derived from a single MPC-backed profile and asserted on every written PNG — the canvas is now MPC's actual 1122 x 1122 (it had drifted to 1125), the safe zone 978 (was 975). One pydantic model owns the card shape and generates the JSON Schemas; all 137 cards validate against it. The CLI renders all eight card types.

The gallery runs: browse all 137 cards, edit them in a form generated from the model, upload artwork, and get a print-ready PNG back.

**Next:** collapse the nine card templates onto one base template, and reuse a single Chromium across a batch. The `REST-CardGenerator` branch is a non-working sketch kept only for reference — see the direction notes in [PROJECT.md](PROJECT.md).

## What this is

A local tool for one custom dungeon-building boardgame. Card data and a piece of artwork go in; a full-bleed PNG matching MakePlayingCards' published upload specification comes out, ready to order. Eight card types — Room, Spell, Hero, Trap, Research, Treasure, Overlord, Creature — share one HTML/CSS template family rendered through headless Chromium.

The measurements are the product. Everything else in the repo exists to serve them.

## Run & verify

```bash
pip install -e .
python -m playwright install chromium
```

Render every card in a folder:

```bash
python generate_card.py --input data/Mixed --output-dir out
```

Render one card:

```bash
python generate_card.py --input data/Mixed/Bear.json --output-dir out
```

A batch run creates `out/<unix-timestamp>_<count>/` containing, per card, `<Name>.html`, `<Name>.png` (full bleed — **this is the file you upload to MPC**), `<Name>_trim.png` (the cut card) and `<Name>_safe.png` (the safe area), plus a `preview.html` grid of everything in the batch. Flags `--html`, `--png`, `--safe`, `--trim` narrow the output; the default is all four.

### The gallery

```bash
python -m cardgen.cli import     # load data/Mixed into the store (skips names already there)
python -m cardgen.cli serve      # http://127.0.0.1:8765
```

Browse, edit, upload artwork, re-render. Every save re-renders in the background.
`render` renders every stored card; `export` writes the store back out as card JSON
**and artwork**, byte-for-byte matching what `data/Mixed` and `backgrounds/` already
hold. Artwork lives in the store as bytes, so export is the deliberate moment it is
written back to disk for git — see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

`pip install -e .` also installs a shorter `cardgen` command, but on this machine its
Scripts directory is not on `PATH`, so `python -m cardgen.cli` is the form that always
works. Add that directory to `PATH` if you would rather type `cardgen serve`.

Verify a change with: `python tests/run_tests.py > tests/last-run.txt 2>&1`

## Print geometry

Every measurement comes from `src/cardgen/spec/profiles.py` and nowhere else — see the first project rule in [CLAUDE.md](CLAUDE.md).

| Region | Size | What it is |
|---|---|---|
| Canvas | 1122 x 1122 px | What gets rendered and uploaded: trim plus 36px of bleed per side |
| Trim | 1050 x 1050 px | The finished 3.5in x 3.5in card, where the cutter aims |
| Safe | 978 x 978 px | Keep artwork and text inside this: trim minus 36px per side |

All at 300 DPI. The bleed and safe-margin figures are MakePlayingCards' own; see [REFERENCES.md](REFERENCES.md) for the source and how to re-check it.

## Layout

| Path | What it is |
|---|---|
| `src/cardgen/spec/` | Print geometry — the single source of truth for every pixel size |
| `src/cardgen/model/` | The card definition — one pydantic model, from which the schemas derive |
| `src/cardgen/store/` | SQLite behind the model: import, edit, export, render state |
| `src/cardgen/render/` | Card data in, print-ready PNGs out. The only rendering path |
| `src/cardgen/web/` | The local gallery: CherryPy API plus a single render worker |
| `web/` | The gallery frontend |
| `generate_card.py` | The CLI renderer; being folded into `src/cardgen/` |
| `templates/` | Jinja card templates, one per type plus shared partials |
| `style.css` | Card styling. Declares no geometry — it reads the profile's CSS variables |
| `schemas/` | Per-type JSON Schemas. **Generated** — `python -m cardgen.model.schemas` |
| `tools/` | One-off migrations and content maintenance scripts, kept for the record |
| `backgrounds/` | The art library in git. The store holds its own copy of each card's artwork |
| `data/Mixed/` | The 137 card definitions |
| `assets/` | Icons and fonts used by the templates |
| `Rules/` | The game's own design documents — a read-only reference, see REFERENCES.md |
| `tests/` | The verify gate |

## Adding a new card type

1. Add a schema in `schemas/<type>.schema.json`.
2. Add a template in `templates/<type>_template.html`.
3. Register both in `generate_card.py` (`TYPE_TO_TEMPLATE_FILE`, `SCHEMA_PATHS`).
4. Add a theme block in `style.css` keyed on `body[data-type="<type>"]`.

Do **not** add a size entry — every type resolves to the same square profile through `cardgen.spec.profile_for_type`. A type only needs a row in `_TYPE_TO_PROFILE` if it genuinely prints at a different physical size.

More: [PROJECT.md](PROJECT.md) (goals, quality bars, doc contract) · [REFERENCES.md](REFERENCES.md) (declared ground truths).

<!-- BASE:readme-footer:v1 START -->
---
<sub>Built on [ClaudeBase](https://github.com/Lutscherdieb/ClaudeBase): the workflow machinery (setup, audits, doc gates, sync/harvest loop) arrives via the `base` Claude Code plugin and updates with it.</sub>
<!-- BASE:END -->
