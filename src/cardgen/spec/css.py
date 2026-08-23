"""Hand the print geometry to CSS, so style.css never restates a pixel size.

style.css used to carry ``body{width:1125px}``, ``.safe-zone{width:975px;
margin:75px}`` and ``--bleed-size:75px`` as literals.  Those are the same
numbers ``profiles.py`` derives, maintained by hand in a second language --
which is exactly how they drifted apart from the spec.

Every rendered card page now gets the block below injected into its ``<head>``
*after* the ``style.css`` link, so the variables win.  style.css declares no
geometry of its own: if this block is missing the layout collapses visibly,
which is the intended failure mode.  A silent fallback would just recreate the
drift.
"""

from __future__ import annotations

from .profiles import Profile

#: The CSS custom properties every card page needs.  Keep the names in step
#: with the ones style.css reads -- ``grep -n 'var(--canvas\|var(--safe\|
#: var(--frame-inset\|var(--trim' style.css`` lists the consumers.
_TEMPLATE = """\
:root {{
  /* Generated from cardgen.spec.profiles -- do not hand-edit, do not restate in style.css. */
  --profile-id: "{id}";
  --canvas-w: {canvas_w}px;
  --canvas-h: {canvas_h}px;
  --trim-w: {trim_w}px;
  --trim-h: {trim_h}px;
  --safe-w: {safe_w}px;
  --safe-h: {safe_h}px;
  --bleed-px: {bleed}px;          /* outside the trim line */
  --safe-margin-px: {safe_margin}px;    /* inside the trim line */
  --frame-inset: {frame_inset}px;       /* canvas edge -> safe zone = bleed + safe margin */
}}"""


def css_variables(profile: Profile) -> str:
    """The ``:root`` block for ``profile``, without a surrounding ``<style>`` tag."""
    return _TEMPLATE.format(
        id=profile.id,
        canvas_w=profile.canvas_w,
        canvas_h=profile.canvas_h,
        trim_w=profile.trim_w,
        trim_h=profile.trim_h,
        safe_w=profile.safe_w,
        safe_h=profile.safe_h,
        bleed=profile.bleed_px,
        safe_margin=profile.safe_margin_px,
        frame_inset=profile.frame_inset,
    )


def css_style_tag(profile: Profile) -> str:
    """``css_variables`` wrapped in a ``<style>`` element, ready for a template."""
    return "<style>\n{}\n</style>".format(css_variables(profile))
