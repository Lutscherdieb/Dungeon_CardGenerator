"""One-time content migration: unify the card text field, flatten Slots.

    python tools/migrate_20260824_unify_text_flatten_slots.py [data/Mixed]

**1. "Rules" becomes "Description".** Rooms stored their printed text under
``Rules`` and the other seven types under ``Description`` -- one concept, two
spellings, bridged by hand in every consumer. Unified on the game's own word:
Rules/Rules.txt:34 reads "Costs are defined in front of a ':' within the
description of a card." 23 files carry ``Rules``, 114 carry ``Description``,
and no file carries both, so the rename is unambiguous.

**2. Slots loses its fake dict wrapper.** It was a list of single-key objects::

    [{"1": [["All", 0]]}, {"2": [["Magic", 0], ["Demon", 0]]}, {"3": []}]

The keys are always the 1-based index (verified across all 23 rooms) and no
template ever reads them -- ``room_template.html`` iterates ``slot.values()``.
It was a list pretending to be a dict::

    [[["All", 0]], [["Magic", 0], ["Demon", 0]], []]

The inner pairs are left exactly as they are. Their second element is 0 on 64
of 66 spots and 2 on the two Sacred_Hain spots; Rules/Ideas.txt lists slot
requirements as an idea rather than a rule, so what that number means is a
question for the author, not something to encode here.

Kept in the repo rather than deleted: the reasoning above is the record of why
the data looks the way it does, and re-running is safe.

Safety: idempotent, and every migrated file must validate against
``cardgen.model`` or the script exits non-zero without writing anything.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cardgen.model import parse_card  # noqa: E402

INDENT = 4


def flatten_slots(slots):
    """[{"1": [...]}, ...] -> [[...], ...]. Already-flat input passes through."""
    out = []
    for group in slots:
        if isinstance(group, dict):
            out.append([spot for key in sorted(group, key=int) for spot in group[key]])
        else:
            out.append(group)
    return out


def migrate(data: dict) -> "tuple[dict, list[str]]":
    """Return the migrated card and the list of changes applied."""
    changes = []
    out = {}
    for key, value in data.items():
        if key == "Rules":
            # Keep the field in place so the diff stays a one-line rename.
            out["Description"] = value
            changes.append("Rules -> Description")
        elif key == "Slots":
            flat = flatten_slots(value)
            if flat != value:
                changes.append("Slots flattened")
            out["Slots"] = flat
        else:
            out[key] = value
    return out, changes


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/Mixed")
    paths = sorted(target.glob("*.json"))
    if not paths:
        print("no .json files under {}".format(target))
        return 1

    planned, invalid = [], []
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        if "Rules" in data and "Description" in data:
            invalid.append("{}: carries both Rules and Description".format(path.name))
            continue
        migrated, changes = migrate(data)
        try:
            parse_card(migrated)
        except Exception as exc:
            invalid.append("{}: does not validate after migration: {}".format(
                path.name, str(exc).splitlines()[1:3]))
            continue
        if changes:
            planned.append((path, migrated, changes))

    if invalid:
        print("REFUSING TO WRITE -- {} file(s) failed:".format(len(invalid)))
        for problem in invalid:
            print("  " + problem)
        return 1

    for path, migrated, _ in planned:
        path.write_text(
            json.dumps(migrated, indent=INDENT, ensure_ascii=False) + "\n",
            encoding="utf-8", newline="",
        )

    tally: "dict[str, int]" = {}
    for _, _, changes in planned:
        for change in changes:
            tally[change] = tally.get(change, 0) + 1

    print("migrated {} of {} file(s); {} already current".format(
        len(planned), len(paths), len(paths) - len(planned)))
    for change, count in sorted(tally.items()):
        print("  {:<24} {} file(s)".format(change, count))
    return 0


if __name__ == "__main__":
    sys.exit(main())
