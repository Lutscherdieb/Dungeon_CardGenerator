"""Render a stored card through the same pipeline the CLI uses.

There is exactly one renderer. The abandoned REST branch grew a second one --
``api/services/rendering.py``, with its own Jinja environment, its own Playwright
call that screenshotted the raw canvas with no crop at all, and duplicate copies
of the spiderweb and inline-icon code. It was dead (only the worker was wired
up) but it was the kind of dead code the next session edits by mistake.

So this module resolves paths and updates the store, and delegates every pixel
to ``generate_card``.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    # generate_card.py still lives at the repo root; it moves under render/ next.
    sys.path.insert(0, str(REPO_ROOT))

#: Where gallery renders land. One directory per card so a re-render replaces
#: its predecessor instead of accumulating timestamped copies.
GALLERY_OUT = Path("out") / "gallery"

#: Where uploaded artwork lands, alongside the existing hand-placed art so the
#: two follow one convention.
ARTWORK_DIR = Path("backgrounds")

#: Grid thumbnail edge, in pixels. The gallery grid shows cards at ~190px; without
#: this it would pull 137 full-size PNGs (~1.6MB each) to draw them.
THUMB_PX = 420


def safe_stem(name: str) -> str:
    """A filename-safe stem, matching the convention the existing files use."""
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (name or "card"))


def render_dir_for(card_id: int) -> Path:
    return GALLERY_OUT / str(card_id)


def render_card(card_id: int, card: Dict, *, artwork: "Optional[tuple]" = None,
                repo_root: Optional[Path] = None) -> Dict[str, str]:
    """Render one card to PNG. Returns repo-relative paths keyed by region.

    ``artwork`` is ``(bytes, mime)`` straight from the store -- the image is a
    property of the card, not a path the renderer has to go looking for.

    Raises whatever the pipeline raises -- including ``GeometryError`` if any
    written image does not match its print profile. The caller records the
    failure; nothing wrong ever reaches the gallery silently.
    """
    import generate_card  # late: pulls in playwright

    root = Path(repo_root or REPO_ROOT)
    out_dir = root / render_dir_for(card_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = safe_stem(card.get("Name"))
    html_path, output_name, profile = generate_card.generate_html(
        None, "", str(out_dir), card_data=card, artwork=artwork
    )
    full = generate_card.generate_png_from_html(html_path, str(out_dir), output_name, profile)
    safe = generate_card.generate_safezone_png(full, str(out_dir), output_name, profile)
    trim = generate_card.generate_trim_png(full, str(out_dir), output_name, profile)
    thumb = _write_thumb(trim, out_dir, output_name)

    # The intermediate HTML carries the artwork base64-inlined, so it runs about
    # 2MB per card -- 270MB across the deck, for a file the renderer regenerates
    # on demand. Drop it once the PNGs it produced have passed their assertions.
    Path(html_path).unlink(missing_ok=True)

    def rel(path) -> str:
        return Path(path).resolve().relative_to(root).as_posix()

    return {"stem": stem, "canvas": rel(full), "safe": rel(safe),
            "trim": rel(trim), "thumb": rel(thumb)}


def _write_thumb(source, out_dir: Path, output_name: str) -> Path:
    """A small grid thumbnail beside the print files. Never used for print."""
    from PIL import Image

    target = out_dir / "{}_thumb.png".format(output_name)
    with Image.open(source) as im:
        im.load()
        im.thumbnail((THUMB_PX, THUMB_PX), Image.LANCZOS)
        im.save(target, format="PNG", optimize=True)
    return target


def render_and_record(db, card_id: int, *, repo_root: Optional[Path] = None) -> Optional[str]:
    """Render a stored card and write the outcome back to its row.

    Returns the repo-relative full-bleed PNG path, or None if the render failed
    (the failure is recorded on the row, not raised).
    """
    from ..store import get_artwork, get_card, set_render_result

    row = get_card(db, card_id)
    if row is None:
        raise LookupError("no card with id {}".format(card_id))

    try:
        result = render_card(card_id, row.data,
                             artwork=get_artwork(db, card_id), repo_root=repo_root)
    except Exception as exc:
        set_render_result(db, card_id, error="{}: {}".format(type(exc).__name__, exc))
        db.commit()
        return None

    set_render_result(db, card_id, png=result["canvas"], at=datetime.now(timezone.utc))
    db.commit()
    return result["canvas"]
