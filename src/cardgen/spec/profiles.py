"""Print geometry -- the single source of truth for every card pixel measurement.

Why this module exists
----------------------
Before it, the card canvas size was hardcoded in four independent places:
``SIZE_PROFILES`` in generate_card.py, the ``canvas``/``bleed``/``safe``
defaults of ``_gen_spider_side``, the ``body``/``.safe-zone`` rules in
style.css, and the ``viewBox`` of templates/_spiderweb.html.  Changing a card
size therefore meant a synchronised edit across Python, CSS and an SVG
template, with nothing to catch a mismatch.  That is why the four disagreed,
and why the canvas had drifted to 1125px against a published spec of 1122px.

**Nothing downstream may hardcode a card pixel size.  Ask a Profile.**

Where the numbers come from
---------------------------
MakePlayingCards' own published specification, not a template we measured:

    https://www.makeplayingcards.com/faq-photo.aspx
      "The Safe Area is highlighted with a red dotted line and is 36 pixels
       each side based on a 300DPI image."
      "There is an additional 72 pixels removed from each dimension
       (36 pixels each side based on a 300DPI image)"

So at 300 DPI, per side: 36px of bleed outside the trim line, then a further
36px of safe margin inside it.  Cross-checked against MPC's own poker figure
-- 2.5x3.5in uploads at 822x1122 -- which is exactly ``trim_in * 300 + 72`` on
each axis.  Our square profile applies the same formula, so adding a size
later is one row in ``PROFILES``, not a code change.

The three regions, outermost first
----------------------------------
    canvas  what we render and what MPC wants uploaded   (trim + 2*bleed)
    trim    the finished card, where the cutter aims     (trim_in * dpi)
    safe    keep art and text inside this                (trim - 2*safe_margin)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

# MakePlayingCards' press specification at 300 DPI.  Both figures are per side.
MPC_DPI = 300
MPC_BLEED_PX = 36        # outside the trim line -- cut tolerance, guillotined off
MPC_SAFE_MARGIN_PX = 36  # inside the trim line -- nothing important may enter this band


@dataclass(frozen=True)
class Box:
    """An axis-aligned pixel region in PIL's (left, top, right, bottom) convention."""

    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def size(self) -> Tuple[int, int]:
        return (self.width, self.height)

    def as_pil(self) -> Tuple[int, int, int, int]:
        """The 4-tuple ``PIL.Image.crop`` expects."""
        return (self.left, self.top, self.right, self.bottom)


@dataclass(frozen=True)
class Profile:
    """One printable card format.  Every measurement below is derived, never stored."""

    id: str
    label: str
    trim_w_in: float
    trim_h_in: float
    dpi: int = MPC_DPI
    bleed_px: int = MPC_BLEED_PX
    safe_margin_px: int = MPC_SAFE_MARGIN_PX

    def __post_init__(self) -> None:
        # A trim edge that does not land on a whole pixel would make every
        # derived box off by half a pixel and blur the cut line.
        for axis, inches in (("width", self.trim_w_in), ("height", self.trim_h_in)):
            exact = inches * self.dpi
            if abs(exact - round(exact)) > 1e-9:
                raise ValueError(
                    "profile {!r}: trim {} {}in at {}dpi is {}px, not a whole pixel".format(
                        self.id, axis, inches, self.dpi, exact
                    )
                )

    # -- trim: the finished card -------------------------------------------
    @property
    def trim_w(self) -> int:
        return round(self.trim_w_in * self.dpi)

    @property
    def trim_h(self) -> int:
        return round(self.trim_h_in * self.dpi)

    # -- canvas: what we render, what MPC receives -------------------------
    @property
    def canvas_w(self) -> int:
        return self.trim_w + 2 * self.bleed_px

    @property
    def canvas_h(self) -> int:
        return self.trim_h + 2 * self.bleed_px

    @property
    def canvas(self) -> Tuple[int, int]:
        return (self.canvas_w, self.canvas_h)

    # -- frame_inset: canvas edge -> safe zone ------------------------------
    @property
    def frame_inset(self) -> int:
        """Bleed band plus safe margin: canvas edge to safe zone.

        This is the number the CSS ``.safe-zone`` margin uses.  It is NOT the
        bleed -- the old ``--bleed-size: 75px`` conflated the two, which is how
        a 3px error survived unnoticed.
        """
        return self.bleed_px + self.safe_margin_px

    # -- safe: where content is allowed ------------------------------------
    @property
    def safe_w(self) -> int:
        return self.trim_w - 2 * self.safe_margin_px

    @property
    def safe_h(self) -> int:
        return self.trim_h - 2 * self.safe_margin_px

    # -- boxes within the canvas -------------------------------------------
    @property
    def canvas_box(self) -> Box:
        return Box(0, 0, self.canvas_w, self.canvas_h)

    @property
    def trim_box(self) -> Box:
        b = self.bleed_px
        return Box(b, b, b + self.trim_w, b + self.trim_h)

    @property
    def safe_box(self) -> Box:
        i = self.frame_inset
        return Box(i, i, i + self.safe_w, i + self.safe_h)

    def box(self, region: str) -> Box:
        """Look a region up by name: ``canvas``, ``trim`` or ``safe``."""
        regions = {"canvas": self.canvas_box, "trim": self.trim_box, "safe": self.safe_box}
        try:
            return regions[region]
        except KeyError:
            raise ValueError(
                "unknown region {!r}; expected one of {}".format(region, ", ".join(sorted(regions)))
            ) from None

    def describe(self) -> str:
        """One-line summary for render reports and docs."""
        return (
            "{}: {} @ {}dpi -- canvas {}x{}, trim {}x{}, safe {}x{} "
            "(bleed {}px, safe margin {}px, both per side)".format(
                self.id, self.label, self.dpi,
                self.canvas_w, self.canvas_h,
                self.trim_w, self.trim_h,
                self.safe_w, self.safe_h,
                self.bleed_px, self.safe_margin_px,
            )
        )


SQUARE_3_5IN = Profile(
    id="SQUARE_3_5IN",
    label='3.5in x 3.5in square (MPC "Large Square")',
    trim_w_in=3.5,
    trim_h_in=3.5,
)

PROFILES = {p.id: p for p in (SQUARE_3_5IN,)}
DEFAULT_PROFILE = SQUARE_3_5IN

# Per-type overrides.  Deliberately empty: every card type is square, confirmed
# 2026-08-24.  Rules/Cardtypes.txt lists Overlord and Creature as "tcg format",
# which is an idea that was left open, not a spec -- do not implement it from
# that file alone.  When a type really does change format, add its row here and
# a Profile above; nothing else in the codebase needs to know.
_TYPE_TO_PROFILE: Dict[str, Profile] = {}


def profile_for_type(card_type: str) -> Profile:
    """The print format for a card type.  Unlisted types get ``DEFAULT_PROFILE``."""
    return _TYPE_TO_PROFILE.get((card_type or "").strip().lower(), DEFAULT_PROFILE)


def profile_by_id(profile_id: str) -> Profile:
    """Look a profile up by id, with a listing of the known ids on failure."""
    try:
        return PROFILES[profile_id]
    except KeyError:
        raise ValueError(
            "unknown profile {!r}; known: {}".format(profile_id, ", ".join(sorted(PROFILES)))
        ) from None
