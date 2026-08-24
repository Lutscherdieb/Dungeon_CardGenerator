"""Refuse to emit a card image whose measurements are wrong.

This is an invariant of the render pipeline, not a test suite.  A test can be
skipped, can go unrun for months, and only ever covers the cards someone
remembered to add.  ``assert_png`` runs on every single image the renderer
writes, so a wrong-sized card cannot reach the ``out/`` directory at all --
which is the whole promise of the project.

The measurements it checks come from ``profiles.py``; this module knows no
numbers of its own.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

from PIL import Image

from .profiles import Profile


class GeometryError(AssertionError):
    """A rendered image does not match the print profile it claims to satisfy."""


def _dpi_of(image: Image.Image) -> Optional[Tuple[float, float]]:
    """The image's stored DPI, or ``None`` when the file carries no metadata."""
    dpi = image.info.get("dpi")
    if not dpi:
        return None
    try:
        return (float(dpi[0]), float(dpi[1]))
    except (TypeError, ValueError, IndexError):
        return None


def assert_png(path: str, profile: Profile, region: str, *, require_dpi: bool = True) -> None:
    """Raise ``GeometryError`` unless the PNG at ``path`` matches ``profile``'s ``region``.

    ``region`` is ``canvas``, ``trim`` or ``safe``.  ``require_dpi`` may be
    turned off for intermediate files that Pillow has not stamped yet --
    never for a file that is going to MakePlayingCards.
    """
    expected_w, expected_h = profile.box(region).size

    with Image.open(path) as im:
        actual_w, actual_h = im.size
        dpi = _dpi_of(im)

    if (actual_w, actual_h) != (expected_w, expected_h):
        raise GeometryError(
            "{}: {} region is {}x{}px but profile {} requires {}x{}px. "
            "Nothing may hardcode a size -- check that the renderer took its "
            "viewport and crop box from cardgen.spec.profiles.".format(
                os.path.basename(path), region, actual_w, actual_h,
                profile.id, expected_w, expected_h,
            )
        )

    if require_dpi:
        if dpi is None:
            raise GeometryError(
                "{}: no DPI metadata. MakePlayingCards reads the stored DPI; save "
                "with dpi=({}, {}).".format(os.path.basename(path), profile.dpi, profile.dpi)
            )
        if round(dpi[0]) != profile.dpi or round(dpi[1]) != profile.dpi:
            raise GeometryError(
                "{}: DPI metadata is {}x{} but profile {} requires {}.".format(
                    os.path.basename(path), dpi[0], dpi[1], profile.id, profile.dpi
                )
            )


def artwork_warnings(width: int, height: int, profile: Profile) -> "list[str]":
    """Warnings about artwork of the given size.  Never raises.

    Artwork fills the safe zone, so anything smaller on either axis gets
    upscaled and prints soft.  Returns a list of human-readable warnings --
    empty means the image is fine.  This is advisory by design: the user asked
    to be warned about low resolution, not blocked by it.

    Takes dimensions rather than a path because artwork lives in the store as
    bytes; the web upload has already measured it, and there is no file to
    reopen.  This is the one place the wording lives.
    """
    warnings: "list[str]" = []
    need_w, need_h = profile.safe_w, profile.safe_h
    if width < need_w or height < need_h:
        warnings.append(
            "artwork is {}x{}px but the {} safe zone is {}x{}px -- it will be "
            "upscaled and print soft".format(width, height, profile.id, need_w, need_h)
        )
    return warnings


def check_artwork(path: str, profile: Profile) -> "list[str]":
    """``artwork_warnings`` for an image on disk, for the file-based CLI."""
    try:
        with Image.open(path) as im:
            width, height = im.size
    except Exception as exc:  # unreadable, truncated, or not an image at all
        return ["could not read image: {}".format(exc)]
    return artwork_warnings(width, height, profile)
