"""Rewrite card JSON in one consistent format, changing nothing semantic.

Run before a content migration so the migration's own diff is readable, and
whenever hand-edited files have drifted in spacing. The format matches what the
JSON exporter writes, so hand-authored and exported cards look the same in git.

    python tools/normalize_card_json.py [data/Mixed]

Safety: the parsed content before and after must be identical, or the file is
left alone and the script exits non-zero. Formatting changes are never worth a
silent content change.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

INDENT = 4


def normalize_text(data) -> str:
    return json.dumps(data, indent=INDENT, ensure_ascii=False) + "\n"


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/Mixed")
    paths = sorted(target.glob("*.json"))
    if not paths:
        print("no .json files under {}".format(target))
        return 1

    changed, unchanged, failed = [], 0, []
    for path in paths:
        original = path.read_text(encoding="utf-8")
        try:
            data = json.loads(original)
        except json.JSONDecodeError as exc:
            failed.append("{}: {}".format(path.name, exc))
            continue

        formatted = normalize_text(data)
        if json.loads(formatted) != data:  # cannot happen, but this is the guard
            failed.append("{}: reformat changed the parsed content".format(path.name))
            continue

        if formatted == original:
            unchanged += 1
            continue
        path.write_text(formatted, encoding="utf-8", newline="")
        changed.append(path.name)

    print("normalized {} file(s), {} already consistent".format(len(changed), unchanged))
    if failed:
        print("\nFAILED:")
        for f in failed:
            print("  " + f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
