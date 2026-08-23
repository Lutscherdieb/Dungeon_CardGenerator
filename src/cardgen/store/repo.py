"""Every read and write of the card store goes through here.

The rule this module exists to enforce: **a card is validated by
``cardgen.model`` before it reaches the database, and the derived index columns
are computed from the validated card, never passed in.** Callers hand over a
raw dict; they cannot write an invalid card and they cannot make ``type`` or
``name`` disagree with ``data``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..model import parse_card, to_json_dict
from .models import CardRow, index_fields


class CardValidationError(ValueError):
    """A card dict did not satisfy the model. Carries a readable summary."""


def _validate(card: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalise a raw card dict, or raise CardValidationError."""
    try:
        return to_json_dict(parse_card(card))
    except Exception as exc:
        raise CardValidationError(_summarize(exc)) from exc


def _summarize(exc: Exception) -> str:
    """Pydantic errors are multi-line; keep the lines that name the field."""
    lines = [line.strip() for line in str(exc).splitlines() if line.strip()]
    useful = [line for line in lines if not line.startswith("For further information")]
    return " | ".join(useful[:6]) or str(exc)


# --- reads -----------------------------------------------------------------


def list_cards(db: Session, *, card_type: Optional[str] = None) -> List[CardRow]:
    stmt = select(CardRow).order_by(CardRow.type, CardRow.name)
    if card_type:
        stmt = stmt.where(CardRow.type == card_type)
    return list(db.scalars(stmt))


def get_card(db: Session, card_id: int) -> Optional[CardRow]:
    return db.get(CardRow, card_id)


def find_by_name(db: Session, name: str) -> Optional[CardRow]:
    return db.scalars(select(CardRow).where(CardRow.name == name)).first()


# --- writes ----------------------------------------------------------------


def create_card(db: Session, card: Dict[str, Any], *, source_path: Optional[str] = None) -> CardRow:
    """Validate and insert. Does not commit -- the caller owns the transaction."""
    validated = _validate(card)
    row = CardRow(data=validated, source_path=source_path, **index_fields(validated))
    db.add(row)
    db.flush()
    return row


def update_card(db: Session, card_id: int, card: Dict[str, Any]) -> CardRow:
    """Replace a card's data wholesale. Re-validates and re-derives the index."""
    row = db.get(CardRow, card_id)
    if row is None:
        raise LookupError("no card with id {}".format(card_id))
    validated = _validate(card)
    row.data = validated
    for column, value in index_fields(validated).items():
        setattr(row, column, value)
    # The stored render no longer depicts this card.
    row.render_status = "pending"
    row.render_error = None
    db.add(row)
    db.flush()
    return row


def delete_card(db: Session, card_id: int) -> bool:
    row = db.get(CardRow, card_id)
    if row is None:
        return False
    db.delete(row)
    return True


def set_render_result(
    db: Session,
    card_id: int,
    *,
    png: Optional[str] = None,
    error: Optional[str] = None,
    at=None,
) -> None:
    """Record the outcome of a render attempt."""
    row = db.get(CardRow, card_id)
    if row is None:
        return
    if error:
        row.render_status = "error"
        row.render_error = error
    else:
        row.render_status = "done"
        row.render_error = None
        row.render_png = png
        row.rendered_at = at
    db.add(row)


# --- JSON import / export --------------------------------------------------


def import_json_files(
    db: Session,
    paths: Iterable[Path],
    *,
    replace_existing: bool = False,
) -> Tuple[List[str], List[str], List[str]]:
    """Import card JSON files. Returns (imported, skipped, errors) as name lists.

    A card whose ``Name`` already exists is skipped unless ``replace_existing``,
    so re-running an import is safe and does not silently duplicate the deck.
    Every file is validated; one bad file does not abort the rest, and the
    caller decides whether to commit.
    """
    imported: List[str] = []
    skipped: List[str] = []
    errors: List[str] = []

    for path in paths:
        try:
            card = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append("{}: unreadable: {}".format(Path(path).name, exc))
            continue

        name = card.get("Name")
        existing = find_by_name(db, name) if name else None
        if existing is not None and not replace_existing:
            skipped.append("{} (already stored as #{})".format(name, existing.id))
            continue

        try:
            if existing is not None:
                update_card(db, existing.id, card)
                existing.source_path = str(path).replace("\\", "/")
            else:
                create_card(db, card, source_path=str(path).replace("\\", "/"))
        except CardValidationError as exc:
            errors.append("{}: {}".format(Path(path).name, exc))
            continue
        imported.append(name or Path(path).stem)

    return imported, skipped, errors


def export_filename(row: CardRow) -> str:
    """The file a card exports to.

    An imported card keeps the filename it came in with. Four cards in the
    current deck were renamed without their file being renamed -- Magic_Sentry.json
    holds "Battledroid", Timeless_Horror.json holds "Chaos Overseer",
    Monster_in_a_Bottle.json holds "Bottled Monster", and Chaos_Imprisionment.json
    holds "Chaos Imprisonment". Deriving the name from ``Name`` would silently
    write a second file beside each of those rather than updating it.
    """
    if row.source_path:
        return Path(row.source_path).name
    stem = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in row.name)
    return "{}.json".format(stem)


def export_json_files(db: Session, out_dir: Path) -> List[Path]:
    """Write every stored card back out as JSON, in the normalised format.

    The store is the source of truth, but the JSON files are what git can diff,
    so a round trip has to exist from day one -- otherwise the game content
    quietly stops being versioned. Exporting over ``data/Mixed`` and running
    ``git diff`` is the integrity check that keeps the two honest, which only
    works while the round trip is byte-exact.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for row in list_cards(db):
        path = out_dir / export_filename(row)
        path.write_text(
            json.dumps(row.data, indent=4, ensure_ascii=False) + "\n",
            encoding="utf-8", newline="",
        )
        written.append(path)
    return written
