"""Emit the per-type JSON Schemas from the model, so they cannot drift from it.

``schemas/*.schema.json`` used to be hand-written and had already disagreed with
itself: ``Type`` required by five of eight, ``additionalProperties`` false in
four of eight, and the two splits not lining up. They are now build products.

Regenerate after any change to ``cards.py``::

    python -m cardgen.model.schemas

The files stay committed on purpose -- editors and the CLI's type detection read
them, and a diff in a generated file is the clearest possible signal that the
model changed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .cards import CARD_TYPES

BANNER = (
    "GENERATED from src/cardgen/model/cards.py by "
    "`python -m cardgen.model.schemas` -- do not hand-edit."
)


def schema_for(card_type: str) -> dict:
    """The JSON Schema for one card type, in the JSON key spelling."""
    model = CARD_TYPES[card_type]
    schema = model.model_json_schema(by_alias=True, mode="validation")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["title"] = "{} Card".format(card_type.capitalize())
    schema["$comment"] = BANNER
    return schema


def write_schemas(out_dir: Path) -> "list[Path]":
    """Write one schema per card type. Returns the paths written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for card_type in sorted(CARD_TYPES):
        path = out_dir / "{}.schema.json".format(card_type)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(schema_for(card_type), f, indent=2, ensure_ascii=False)
            f.write("\n")
        written.append(path)
    return written


def main() -> int:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("schemas")
    for path in write_schemas(out_dir):
        print("wrote {}".format(path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
