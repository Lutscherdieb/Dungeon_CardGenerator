"""The author's corrections, read out of the skill's own reference files.

Both ``references/model.md`` and ``references/rulings.md`` are written for a
human first: prose explaining a decision, with one fenced ```json block holding
the machine-readable part of it. That way there is one file per concern rather
than a markdown file and a JSON file that can disagree, and the reason for an
override always sits beside the override.

A missing file is not an error. The skill's memory starts empty, and the report
is meaningful without it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

#: Where the skill keeps its memory, relative to the repo root.
SKILL_DIR = Path(".claude") / "skills" / "card-balance" / "references"
MODEL_FILE = SKILL_DIR / "model.md"
RULINGS_FILE = SKILL_DIR / "rulings.md"

_FENCE = re.compile(r"```json\s*\n(.*?)\n```", re.S)

#: What an empty model file means: costs weighted equally, nothing pinned.
DEFAULTS: Dict[str, Any] = {
    "cost_weights": {},      # resource name -> multiplier, default 1.0
    "weights": {},           # card type -> {feature: fixed weight}
    "ignore_features": {},   # card type -> [feature names to leave out]
    "threshold_z": 1.75,     # how many residual sigmas counts as an outlier
    "threshold_abs": 1.0,    # ... and never flag less than this much cost
}


def load_json_block(path: Path) -> Dict[str, Any]:
    """The first ```json block in a markdown file, or {} if there is none."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return {}
    match = _FENCE.search(text)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ValueError("{}: the json block is not valid JSON: {}".format(path, exc))
    return parsed if isinstance(parsed, dict) else {}


def load_model(path: Path = MODEL_FILE) -> Dict[str, Any]:
    """The cost model, with every unset key at its default."""
    config = dict(DEFAULTS)
    config.update(load_json_block(path))
    return config


def load_rulings(path: Path = RULINGS_FILE) -> Dict[str, Dict[str, Any]]:
    """Accepted outliers, keyed by card name.

    A card listed here has already been judged deliberate: the report mentions
    it as accepted rather than re-raising it, so a run only surfaces what has
    not been ruled on yet. That is what stops the same twelve cards being
    reported every time.
    """
    block = load_json_block(path)
    return {entry["card"]: entry
            for entry in block.get("accepted", [])
            if isinstance(entry, dict) and entry.get("card")}
