"""The stored row. The card itself is JSON; the columns beside it are an index.

Why not a column per card field
-------------------------------
Because the card shape already has an owner -- ``cardgen.model`` -- and giving
SQL a second opinion about it is how the earlier REST sketch ended up with a
``Card.as_dict`` that read three columns the table did not have. Every request
that listed cards raised ``AttributeError`` and returned 500, which is why that
branch's gallery could never load.

So the validated card is stored whole, in its JSON key spelling, and adding a
field to the model needs no schema change here at all. The scalar columns exist
only so the gallery can list, filter and sort without loading and parsing every
row -- and they are *derived* on write by ``index_fields`` rather than set by
callers, so they cannot disagree with the JSON they came from.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import JSON, DateTime, Integer, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CardRow(Base):
    """One card. ``data`` is authoritative; every other column is derived from it."""

    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # --- derived index columns: never set these directly, see index_fields ---
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    subtype: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    faction: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    tier: Mapped[Optional[int]] = mapped_column(Integer, index=True)

    # --- the card itself, in the same key spelling as the JSON files ---
    data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    # --- artwork ---
    #: The card's artwork, stored as bytes rather than as a path.
    #:
    #: A path made the user responsible for filenames, let the JSON and the file
    #: tree drift apart, and left orphans behind on rename. Bytes in the row mean
    #: the artwork moves with the card, an upload simply replaces it, and nothing
    #: can point at a file that is not there. The renderer wants bytes anyway --
    #: it base64-inlines the image into the card HTML either way.
    #:
    #: Deferred: the gallery lists 137 cards at a time and must not drag ~200MB
    #: of image data along to draw their names.
    artwork: Mapped[Optional[bytes]] = mapped_column(LargeBinary, deferred=True)
    artwork_mime: Mapped[Optional[str]] = mapped_column(String(64))
    #: The filename the image arrived with, so export can write it back out.
    artwork_filename: Mapped[Optional[str]] = mapped_column(String(255))
    artwork_width: Mapped[Optional[int]] = mapped_column(Integer)
    artwork_height: Mapped[Optional[int]] = mapped_column(Integer)
    artwork_bytes: Mapped[Optional[int]] = mapped_column(Integer)

    # --- provenance and render state ---
    #: Where this card was imported from, if it was. Null for cards authored
    #: in the gallery.
    source_path: Mapped[Optional[str]] = mapped_column(String(512))
    #: Repo-relative path of the full-bleed PNG -- the file that goes to MPC.
    #: The _trim and _safe siblings are derived from it by name.
    render_png: Mapped[Optional[str]] = mapped_column(String(512))
    render_status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    render_error: Mapped[Optional[str]] = mapped_column(Text)
    rendered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
        server_default=func.now(), nullable=False,
    )

    def as_dict(self) -> Dict[str, Any]:
        """The row as the API returns it: the card, plus store-level metadata.

        Every key here is backed by a real column or by ``data``. The predecessor
        of this method invented three (``png_full``, ``png_safe``, ``png_trim``)
        that were never columns, and every list request 500'd as a result.
        """
        return {
            "id": self.id,
            "card": self.data,
            "artwork": {
                "present": self.artwork_bytes is not None,
                "mime": self.artwork_mime,
                "filename": self.artwork_filename,
                "width": self.artwork_width,
                "height": self.artwork_height,
                "bytes": self.artwork_bytes,
            },
            "type": self.type,
            "name": self.name,
            "subtype": self.subtype,
            "faction": self.faction,
            "tier": self.tier,
            "source_path": self.source_path,
            "render": {
                "status": self.render_status,
                "png": self.render_png,
                "error": self.render_error,
                "at": self.rendered_at.isoformat() if self.rendered_at else None,
            },
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


#: The index columns, and how each is read out of a card dict. Adding a column
#: means adding one row here and nothing else -- callers never name them.
_INDEXED = {
    "type": "Type",
    "name": "Name",
    "subtype": "Subtype",
    "faction": "Faction",
    "tier": "Tier",
}


def index_fields(card: Dict[str, Any]) -> Dict[str, Any]:
    """The derived column values for a card dict, in JSON key spelling."""
    return {column: card.get(key) for column, key in _INDEXED.items()}
