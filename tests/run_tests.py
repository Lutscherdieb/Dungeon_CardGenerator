"""The verify gate: prove the geometry is right and that every template still renders.

Run from anywhere::

    python tests/run_tests.py > tests/last-run.txt 2>&1

Exit code 0 means every check passed.  This is the command PROJECT.md names as
the verify method, and ``tests/last-run.txt`` is the evidence artifact whose
freshness the check-verify hook watches.

Three checks, in increasing cost:

1. ``check_profile_math``  -- the derivation reproduces MakePlayingCards' own
   published figures, including one for a size this project does not print.
2. ``check_no_stray_geometry`` -- no pixel measurement has reappeared outside
   the spec module.
3. ``check_renders`` -- one card of every type actually renders, and every
   written PNG satisfies its profile.  Covers all nine templates.
"""

from __future__ import annotations

import glob
import json
import os
import re
import shutil
import sys
import tempfile
import traceback
from collections import OrderedDict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))  # generate_card.py still lives at the repo root
os.chdir(REPO_ROOT)  # generate_card resolves templates/ and assets/ relative to cwd

from cardgen.spec import (  # noqa: E402
    MPC_BLEED_PX,
    MPC_SAFE_MARGIN_PX,
    SQUARE_3_5IN,
    Profile,
    assert_png,
    profile_for_type,
)

_failures: "list[str]" = []


def _fail(check: str, message: str) -> None:
    _failures.append("{}: {}".format(check, message))
    print("  FAIL  {}".format(message))


def _ok(message: str) -> None:
    print("  ok    {}".format(message))


# ---------------------------------------------------------------------------


def check_profile_math() -> None:
    """The derivation must match MakePlayingCards, including a size we never print."""
    print("\n[1/3] profile derivation vs the MPC published spec")

    # MPC states both figures as 36px per side at 300 DPI.  If these ever change
    # upstream, REFERENCES.md's comparison procedure says how to re-read them.
    if (MPC_BLEED_PX, MPC_SAFE_MARGIN_PX) != (36, 36):
        _fail("profile", "MPC constants are {}/{}, expected 36/36 per side".format(
            MPC_BLEED_PX, MPC_SAFE_MARGIN_PX))
    else:
        _ok("MPC constants: 36px bleed, 36px safe margin, per side")

    # The cross-check that makes the square numbers falsifiable: MPC publishes a
    # pixel figure for poker but not for 3.5in square, so the formula is proved
    # against a size this project does not print.
    poker = Profile(id="POKER_CHECK", label="poker cross-check", trim_w_in=2.5, trim_h_in=3.5)
    if poker.canvas != (822, 1122):
        _fail("profile", "poker cross-check: derivation gives {}, MPC publishes (822, 1122)"
              .format(poker.canvas))
    else:
        _ok("poker cross-check: 2.5x3.5in -> 822x1122, matches MPC's published figure")

    p = SQUARE_3_5IN
    expected = {"canvas": (1122, 1122), "trim": (1050, 1050), "safe": (978, 978)}
    for region, want in expected.items():
        got = p.box(region).size
        if got != want:
            _fail("profile", "{} region is {}, expected {}".format(region, got, want))
        else:
            _ok("{} region {}x{}".format(region, want[0], want[1]))

    # Box arithmetic must be internally consistent: each region centred in the last.
    if p.trim_box.left != p.bleed_px or p.canvas_w - p.trim_box.right != p.bleed_px:
        _fail("profile", "trim box is not centred in the canvas: {}".format(p.trim_box))
    elif p.safe_box.left != p.frame_inset or p.canvas_w - p.safe_box.right != p.frame_inset:
        _fail("profile", "safe box is not centred in the canvas: {}".format(p.safe_box))
    else:
        _ok("trim and safe boxes are centred in the canvas")

    # Every card type must resolve to a profile; none may resolve to None.
    types = _types_present()
    unresolved = [t for t in types if profile_for_type(t) is None]
    if unresolved:
        _fail("profile", "types with no profile: {}".format(", ".join(unresolved)))
    else:
        _ok("all {} card types resolve to a profile".format(len(types)))


# ---------------------------------------------------------------------------

#: Any of these appearing outside the spec module means a second source of truth
#: has been reintroduced.  Both the current values and the wrong historical ones
#: are listed, so a revert is caught as loudly as a fresh hardcode.
_GEOMETRY_LITERALS = re.compile(r"\b(1122|1050|978|1125|975|822)\b")

_SCANNED = ("style.css", "templates", "src", "generate_card.py")
_EXEMPT_DIR = os.path.join("src", "cardgen", "spec")


def check_no_stray_geometry() -> None:
    """No pixel measurement may live outside cardgen.spec."""
    print("\n[2/3] no geometry literals outside cardgen.spec")

    hits = []
    for target in _SCANNED:
        paths = [target] if os.path.isfile(target) else glob.glob(
            os.path.join(target, "**", "*"), recursive=True)
        for path in paths:
            if not os.path.isfile(path):
                continue
            if os.path.normpath(path).startswith(_EXEMPT_DIR):
                continue
            if path.endswith((".pyc", ".png", ".ttf")):
                continue
            try:
                text = open(path, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                if _GEOMETRY_LITERALS.search(line):
                    hits.append("{}:{}: {}".format(path, lineno, line.strip()[:100]))

    # tests/ is excluded from _SCANNED on purpose: this very file names the
    # numbers, and so must any test that checks them.
    if hits:
        for h in hits:
            _fail("geometry", h)
    else:
        _ok("no geometry literals in {}".format(", ".join(_SCANNED)))


# ---------------------------------------------------------------------------


def _types_present() -> "list[str]":
    """Card types actually present in the data -- never a hardcoded list."""
    types = set()
    for path in glob.glob(os.path.join("data", "Mixed", "*.json")):
        try:
            types.add(str(json.load(open(path, encoding="utf-8")).get("Type", "")).strip())
        except Exception:
            continue
    return sorted(t for t in types if t)


def _one_card_per_type() -> "OrderedDict[str, str]":
    """One representative card file per type, plus a Room with each subtype.

    Subtypes get their own entry because ``room`` + ``hearth`` diverts to a
    different template, and a per-type sample alone would never exercise it.
    """
    chosen: "OrderedDict[str, str]" = OrderedDict()
    for path in sorted(glob.glob(os.path.join("data", "Mixed", "*.json"))):
        try:
            data = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        t = str(data.get("Type", "")).strip()
        if not t:
            continue
        sub = str(data.get("Subtype", "")).strip()
        key = "{} - {}".format(t, sub) if sub else t
        chosen.setdefault(key, path)
    return chosen


def check_renders() -> None:
    """Render one card of every type; every written PNG must satisfy its profile."""
    print("\n[3/3] render one card per type, assert every PNG")

    import generate_card  # imported late: pulls in playwright

    samples = _one_card_per_type()
    if not samples:
        _fail("render", "no card data found under data/Mixed/")
        return

    out_dir = tempfile.mkdtemp(prefix="cardgen-verify-")
    try:
        for label, json_path in samples.items():
            try:
                html, name, profile = generate_card.generate_html(json_path, "", out_dir)
                full = generate_card.generate_png_from_html(html, out_dir, name, profile)
                safe = generate_card.generate_safezone_png(full, out_dir, name, profile)
                trim = generate_card.generate_trim_png(full, out_dir, name, profile)
                # generate_* already assert; re-assert here so a future refactor
                # that drops the internal check still fails this gate.
                assert_png(full, profile, "canvas")
                assert_png(safe, profile, "safe")
                assert_png(trim, profile, "trim")
                _ok("{:<18} {:<16} canvas/trim/safe all match {}".format(
                    label, os.path.basename(json_path), profile.id))
            except Exception as exc:
                _fail("render", "{} ({}): {}".format(label, os.path.basename(json_path), exc))
                traceback.print_exc()
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


# ---------------------------------------------------------------------------


def main() -> int:
    print("CardGenerator verify gate")
    print("repo: {}".format(REPO_ROOT))
    print(SQUARE_3_5IN.describe())

    check_profile_math()
    check_no_stray_geometry()
    check_renders()

    print("\n" + "=" * 72)
    if _failures:
        print("FAILED -- {} check(s) did not pass:".format(len(_failures)))
        for f in _failures:
            print("  - {}".format(f))
        return 1
    print("PASSED -- all checks green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
