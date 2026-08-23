# CardGenerator — constitution

## Goal

Generate print-ready boardgame card images at exact MakePlayingCards measurements from card data plus artwork.

A local tool for one custom dungeon-building boardgame. Card data and a piece of artwork go in; a full-bleed PNG matching MakePlayingCards' published upload specification comes out, ready to order. Eight card types — Room, Spell, Hero, Trap, Research, Treasure, Overlord, Creature — share one HTML/CSS template family rendered through headless Chromium.

The measurements are the product. Everything else in the repo exists to serve them.

## Non-goals

- **Not a game engine or rules simulator.** `Rules/` documents how the game is played so cards can be authored correctly; nothing here executes those rules.
- **Not internet-facing.** The gallery binds to localhost for a single user. No accounts, no sharing, no hosting. Anything that assumes multiple users or a public URL is out of scope until that decision is explicitly revisited.
- **Not a general-purpose card designer.** The templates encode this game's visual language. Making them configurable for other games would trade away the thing that keeps them consistent.
- **Not an art tool.** Artwork is authored elsewhere and uploaded; the renderer places and crops it, and warns when it is too small.

## Users

Just me, on this machine.

## Quality bars & definition of done

- A change is done when: it's implemented, its mapped docs are current (see the documentation contract below), and the verify method below has actually been run with its output checked.
- **A wrong-sized image is a failed render, not a warning.** Geometry assertions run inside the pipeline, so an image that does not match its profile never reaches the output directory. Do not downgrade an assertion to a log line.
- **Preview before writing** any new design, schema change, or data migration — show what will change and get an explicit OK first.
- Escalate when simple turns complex: if a change starts touching the geometry, the card model, and the templates at once, stop and say so before continuing.

## Verify method

Render one card of every type and assert every written PNG against its print profile, plus check the geometry derivation against MakePlayingCards' own published figures. This covers all nine templates, so a template that stops parsing or a profile that drifts fails loudly.

- Command: `python tests/run_tests.py > tests/last-run.txt 2>&1`
- Evidence: `tests/last-run.txt`
- Exempt: `["**/*.md", "Rules/**", "data/**"]`

Artwork supplied by the user is validated separately and advisorily: `cardgen.spec.check_artwork` warns when an image is smaller than the safe zone and would print soft. That is a warning by design, never a block.

## Documentation contract

| Document | What it promises its reader |
|---|---|
| `README.md` | What this is, current status, how to run + verify it |
| `docs/ARCHITECTURE.md` | How the pipeline fits together: where geometry comes from, how a card becomes a PNG, and which module owns what |

## References summary

- **MakePlayingCards print spec** — the published upload dimensions, bleed and safe-area figures that every `Profile` must satisfy. Live website.
- **`Rules/`** — the game's own design documents; the source of truth for card types, costs and terminology. Read-only, and part idea book: see the CLAUDE.md rule before implementing from it.

## Open direction notes

- **Rebuild the web gallery.** The `REST-CardGenerator` branch is a non-working sketch (`Card.as_dict` reads three columns that do not exist, so every list request 500s). Rebuild on CherryPy + SQLAlchemy + SQLite with the card data as one pydantic model; harvest ideas from that branch, then delete it.
- **SQLite becomes the source of truth**, with JSON import for the 137 existing cards and export back out so game content stays diffable in git.
- **Ask the author what the second number in a `Slots` spot means.** It is 0 on 64 of 66 spots and 2 on the two `Sacred_Hain` spots, whose text mentions "[Wild] with Level 1". `Rules/Ideas.txt` lists slot requirements as an idea, so it is not safe to name the field from that alone.
- `Food` is declared on every card type and used by one card. Kept deliberately — cards for it are not designed yet.
- **Collapse the nine card templates onto one base template.** They are 658 lines of the same skeleton; `room` and `room_hearth` are near-identical 96-line copies.
- **Reuse one Chromium instance across a batch.** The renderer currently launches a browser per card, which dominates the runtime of a 137-card run.
