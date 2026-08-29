"""One-time content migration: flatten Room.Slots, add Starter and Hero.Treasure.

    python tools/migrate_20260829_flatten_slots_add_starter_treasure.py [--db URL]

**1. Room.Slots loses its grouping and its per-spot number.** It was::

    [[["Wild", 0], ["Wild", 0]], [["All", 0]], []]

The outer grouping was layout, not data: every one of the 23 rooms had exactly
three groups and the third was empty on all of them, so it encoded nothing the
renderer could not derive. The second element of each spot was 0 on every spot
in the store -- the two Sacred Hain exceptions carrying ``2`` were cleared by
the author on 2026-08-29, which is what made the flatten lossless. It becomes a
plain list of the types the room accepts, in print order::

    ["Wild", "Wild", "All"]

That is the same shape as ``Overlord.Creatures``, so the gallery's existing tag
editor and the shared creature-strip partial serve both.

**2. Every card gains ``Starter: false``.** A boolean on ``CardBase`` marking a
card that ships in the starting deck; it prints as a corner stamp.

**3. Every Hero gains ``Treasure: 0``.** How much treasure the hero drops as
loot when slain, printed exactly as a Room's Treasure is.

Migrating the STORE, not the JSON files
---------------------------------------
Its predecessor (migrate_20260824_*) rewrote ``data/Mixed/*.json`` because the
files were then the source of truth. They are not any more: on 2026-08-29 the
database was ahead of the files by 110 cards. So this script migrates
``data/cards.db`` and the files are refreshed afterwards by::

    python -m cardgen.cli export data/Mixed

It writes ``row.data`` and re-derives the index columns directly rather than
going through ``update_card``, for one reason: ``update_card`` marks a card's
render stale, and 135 of these 137 cards render identically after the
migration. Only Room and Hero change on the printed face, so only they are
marked pending.

Safety: idempotent, and every migrated card must validate against
``cardgen.model`` or the script exits non-zero without committing anything.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cardgen.model import parse_card, to_json_dict  # noqa: E402
from cardgen.store.models import index_fields  # noqa: E402

#: The types whose printed face changes, and so whose stored render is stale.
RERENDER_TYPES = {"Room", "Hero"}


def flatten_slots(slots):
    """[[[type, n], ...], ...] -> [type, ...]. Already-flat input passes through."""
    out = []
    for entry in slots or []:
        if isinstance(entry, str):          # already migrated
            out.append(entry)
            continue
        for spot in entry:                  # a group of [type, number] spots
            out.append(spot[0] if isinstance(spot, (list, tuple)) else spot)
    return out


def migrate(card: dict) -> "tuple[dict, list[str]]":
    """Return the migrated card and the list of changes applied."""
    card = dict(card)
    changes = []

    if card.get("Type") == "Room":
        flat = flatten_slots(card.get("Slots"))
        if flat != card.get("Slots"):
            card["Slots"] = flat
            changes.append("Slots -> {}".format(flat or "[]"))

    if card.get("Type") == "Hero" and "Treasure" not in card:
        card["Treasure"] = 0
        changes.append("Treasure: 0")

    if "Starter" not in card:
        card["Starter"] = False
        changes.append("Starter: false")

    return card, changes


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default=None, help="override CARDGEN_DB_URL for this run")
    ap.add_argument("--dry-run", action="store_true", help="report, write nothing")
    args = ap.parse_args(argv)

    if args.db:
        import os
        os.environ["CARDGEN_DB_URL"] = args.db

    from cardgen.store import SessionLocal, init_db, list_cards

    init_db()
    changed = failed = 0
    with SessionLocal() as db:
        rows = list_cards(db)
        print("{} cards in the store".format(len(rows)))

        for row in rows:
            card, changes = migrate(row.data)
            if not changes:
                continue
            try:
                validated = to_json_dict(parse_card(card))
            except Exception as exc:
                print("  REJECTED {}: {}".format(row.name, exc))
                failed += 1
                continue

            print("  {:<26} {}".format(row.name, "; ".join(changes)))
            if args.dry_run:
                changed += 1
                continue

            row.data = validated
            for column, value in index_fields(validated).items():
                setattr(row, column, value)
            if row.type in RERENDER_TYPES:
                row.render_status = "pending"
                row.render_error = None
            db.add(row)
            changed += 1

        if failed:
            db.rollback()
            print("\n{} card(s) failed validation -- nothing written".format(failed))
            return 1
        if args.dry_run:
            db.rollback()
            print("\ndry run: {} card(s) would change".format(changed))
            return 0
        db.commit()

    print("\nmigrated {} card(s); {} type(s) marked for re-render: {}".format(
        changed, len(RERENDER_TYPES), ", ".join(sorted(RERENDER_TYPES))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
