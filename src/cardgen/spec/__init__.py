"""Print geometry: the one place any card pixel measurement may come from.

Import from here rather than reaching into the submodules::

    from cardgen.spec import Profile, profile_for_type, css_style_tag, assert_png
"""

from .css import css_style_tag, css_variables
from .profiles import (
    DEFAULT_PROFILE,
    MPC_BLEED_PX,
    MPC_DPI,
    MPC_SAFE_MARGIN_PX,
    PROFILES,
    SQUARE_3_5IN,
    Box,
    Profile,
    profile_by_id,
    profile_for_type,
)
from .verify import GeometryError, artwork_warnings, assert_png, check_artwork

__all__ = [
    "Box",
    "DEFAULT_PROFILE",
    "GeometryError",
    "MPC_BLEED_PX",
    "MPC_DPI",
    "MPC_SAFE_MARGIN_PX",
    "PROFILES",
    "Profile",
    "SQUARE_3_5IN",
    "artwork_warnings",
    "assert_png",
    "check_artwork",
    "css_style_tag",
    "css_variables",
    "profile_by_id",
    "profile_for_type",
]
