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
- **A task is not done while a server Claude started is still listening.** The gallery on 8765 is the author's, started from `serve.bat`; Claude may run its own throwaway on 8766 for testing, and closing it is part of the close-out, not an afterthought — see the server rule in [CLAUDE.md](CLAUDE.md).

## Verify method

Render one card of every type and assert every written PNG against its print profile, plus check the geometry derivation against MakePlayingCards' own published figures. This covers all nine templates, so a template that stops parsing or a profile that drifts fails loudly.

- Command: `python tests/run_tests.py > tests/last-run.txt 2>&1`
- Evidence: `tests/last-run.txt`
- Exempt: `["**/*.md", "Rules/**", "data/**"]`

Run it from VS Code with **Terminal → Run Task → `Verify`**, or by hand with the command above.

**The gate does not cover the gallery frontend.** `web/**` is mapped to `docs/ARCHITECTURE.md` but deliberately kept out of `source_globs`: rendering cards proves nothing about the browser UI, so demanding the gate for a frontend edit would be ritual rather than verification. The frontend's checks are `tests/check_gallery.py` and `tests/check_artwork.py`, which drive a real browser and need the gallery **already running** — start it with `serve.bat`, then run them against it. Both honour `CARDGEN_URL`, which is also how Claude points them at its own throwaway server on 8766 instead of yours on 8765 — see the server rule in [CLAUDE.md](CLAUDE.md).

Artwork supplied by the user is validated separately and advisorily: `cardgen.spec.artwork_warnings` warns when an image is smaller than the safe zone and would print soft. That is a warning by design, never a block. Artwork itself is stored in the database as bytes, not as a path — `tests/check_artwork.py` drives that end to end in a real browser.

## Documentation contract

| Document | What it promises its reader |
|---|---|
| `README.md` | What this is, current status, how to run + verify it |
| `docs/ARCHITECTURE.md` | How the pipeline fits together: where geometry comes from, how a card becomes a PNG, and which module owns what |
| `.claude/skills/card-balance/` | What "balanced" currently means for this deck, and every card the author has ruled on |

## References summary

- **MakePlayingCards print spec** — the published upload dimensions, bleed and safe-area figures that every `Profile` must satisfy. Live website.
- **`Rules/`** — the game's own design documents; the source of truth for card types, costs and terminology. Read-only, and part idea book: see the CLAUDE.md rule before implementing from it.

## Open direction notes

- **Delete the `REST-CardGenerator` branch.** Everything worth keeping from it has been rebuilt; it survives only as a reference for how not to do it (`Card.as_dict` read three columns that did not exist, so every list request 500'd).
- **Four card files have drifted from their card's name** — `Magic_Sentry.json` holds "Battledroid", `Timeless_Horror.json` holds "Chaos Overseer", `Monster_in_a_Bottle.json` holds "Bottled Monster", and `Chaos_Imprisionment.json` holds "Chaos Imprisonment" (the filename carries the typo). Nothing breaks — export follows the file it came from — but the files and their artwork are worth renaming. Author's call.
- ~~**Ask the author what the second number in a `Slots` spot means.**~~ **Answered 2026-08-29: nothing.** The author cleared the two `Sacred_Hain` exceptions, leaving every spot at 0, and `Room.Slots` was flattened to a plain list of creature types printed through the same partial as the Overlord's creature pool.
- ~~`Food` is declared on every card type and used by one card.~~ **Resolved 2026-08-29:** Food is now a live cost on 78 of 137 cards — the author rebalanced Mana into Food in the gallery, and this export is the first time that work reached git. Keeping the field was the right call.
- **Collapse the nine card templates onto one base template.** They are 658 lines of the same skeleton; `room` and `room_hearth` are near-identical 96-line copies.
- **Reuse one Chromium instance across a batch.** The renderer currently launches a browser per card, which dominates the runtime of a 137-card run.
