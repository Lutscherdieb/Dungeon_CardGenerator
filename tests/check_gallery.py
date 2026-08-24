"""Drive the gallery in a real browser and check the things unit tests cannot.

Needs a server already running::

    python -m cardgen.cli serve          # in one terminal
    python tests/check_gallery.py        # in another

Not part of the verify gate, which must stay runnable with nothing listening.
Run it after touching anything under web/.

What it guards, and why each one is here:

- The drawer opens, closes and animates. It once could not be closed at all:
  `.panel { display: flex }` beats the UA rule for the [hidden] attribute, so
  toggling `hidden` did nothing and the X looked dead.
- Selecting a card does not refetch thumbnails the browser already has. The
  grid used to cache-bust every image URL with Date.now(), so any repaint
  re-downloaded all 137. Lazy first-loads are fine and are not counted.
- Switching cards takes one click, and the grid is pushed aside rather than
  hidden under the panel.
- Exactly one tile is marked as the one the panel belongs to.
"""
import os
import sys
import tempfile

from playwright.sync_api import sync_playwright

BASE = os.environ.get("CARDGEN_URL", "http://127.0.0.1:8765") + "/web/index.html"
SHOTS = os.environ.get("CARDGEN_SHOTS", tempfile.mkdtemp(prefix="cardgen-shots-"))

problems = []
thumb_requests = []       # every thumbnail request, in order
console_errors = []


def refetches(since=0):
    """Thumbnails requested that had ALREADY been requested earlier.

    A first request for a tile is fine -- lazy loading fetches tiles as they
    scroll or reflow into view, and opening the drawer narrows the grid. The
    bug being guarded against is the SAME image being pulled twice, which is
    what a cache-busted URL on every repaint caused.
    """
    seen = set(u.split('?')[0] for u in thumb_requests[:since])
    dupes = []
    for u in thumb_requests[since:]:
        base = u.split('?')[0]
        if base in seen:
            dupes.append(u)
        seen.add(base)
    return dupes


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        page.on("pageerror", lambda e: console_errors.append("pageerror: %s" % e))
        page.on("console", lambda m: console_errors.append("console.%s: %s" % (m.type, m.text))
                if m.type == "error" else None)
        page.on("request", lambda r: thumb_requests.append(r.url)
                if "_thumb.png" in r.url else None)

        page.goto(BASE, wait_until="networkidle")
        page.wait_for_selector("#grid .card", timeout=15000)

        tiles = page.locator("#grid .card").count()
        print("tiles rendered: %d" % tiles)
        if tiles < 8:
            problems.append("only %d tiles -- import some cards first" % tiles)

        # --- drawer starts closed -----------------------------------------
        panel_open = page.locator("#panel").evaluate("el => el.classList.contains('open')")
        box = page.locator("#panel").bounding_box()
        print("on load: panel .open=%s  x=%s" % (panel_open, box and round(box["x"])))
        if panel_open:
            problems.append("panel is open on load")
        if box and box["x"] < 1439:
            problems.append("closed panel is on screen at x=%s (should be off the right edge)" % box["x"])
        page.screenshot(path=SHOTS + "/01-grid.png")

        # --- open a card ---------------------------------------------------
        mark = len(thumb_requests)
        page.locator("#grid .card").first.click()
        page.wait_for_selector("#panel.open", timeout=5000)
        page.wait_for_timeout(600)
        box = page.locator("#panel").bounding_box()
        print("after click: panel .open=True  x=%s (viewport 1440, panel 560)" % round(box["x"]))
        if abs(box["x"] - 880) > 2:
            problems.append("open panel not flush right: x=%s" % box["x"])

        fields = page.locator("#form-fields .field").count()
        title = page.locator("#panel-title").inner_text()
        print("panel title: %r, form fields: %d" % (title, fields))
        if fields == 0:
            problems.append("form rendered no fields")
        page.screenshot(path=SHOTS + "/02-drawer-open.png")

        # --- the grid must NOT refetch itself -------------------------------
        page.wait_for_timeout(3000)  # longer than the 1.2s poll interval
        dupes = refetches(mark)
        print("thumbnail requests after opening a card: %d total, %d of them refetches"
              % (len(thumb_requests) - mark, len(dupes)))
        if dupes:
            problems.append("selecting a card refetched %d already-loaded thumbnails"
                            % len(dupes))

        # --- close with the X ------------------------------------------------
        page.locator("#btn-close").click()
        page.wait_for_timeout(500)
        still_open = page.locator("#panel").evaluate("el => el.classList.contains('open')")
        box = page.locator("#panel").bounding_box()
        aria = page.locator("#panel").get_attribute("aria-hidden")
        print("after X: .open=%s  x=%s  aria-hidden=%s" % (still_open, box and round(box["x"]), aria))
        if still_open:
            problems.append("X did not remove .open")
        if box and box["x"] < 1439:
            problems.append("panel still on screen after X (x=%s)" % box["x"])
        if aria != "true":
            problems.append("aria-hidden not restored after close")
        page.screenshot(path=SHOTS + "/03-closed.png")

        # --- transition is actually declared ---------------------------------
        dur = page.locator("#panel").evaluate(
            "el => getComputedStyle(el).transitionDuration")
        print("panel transition-duration: %s" % dur)
        if dur.startswith("0s"):
            problems.append("panel has no transition")

        # --- reopening a second card still must not refetch the grid ----------
        mark = len(thumb_requests)
        page.locator("#grid .card").nth(3).click()
        page.wait_for_selector("#panel.open", timeout=5000)
        page.wait_for_timeout(2500)
        dupes = refetches(mark)
        print("second open: %d requests, %d refetches"
              % (len(thumb_requests) - mark, len(dupes)))
        if dupes:
            problems.append("second open refetched %d thumbnails" % len(dupes))

        # --- switching cards must take ONE click, not two --------------------
        before = page.locator("#panel-title").inner_text()
        page.locator("#grid .card").nth(7).click()
        page.wait_for_timeout(500)
        after = page.locator("#panel-title").inner_text()
        still_open = page.locator("#panel").evaluate("el => el.classList.contains('open')")
        print("switch card in one click: %r -> %r (open=%s)" % (before, after, still_open))
        if before == after or not still_open:
            problems.append("clicking another card did not switch the panel in one click")

        # --- the grid is pushed aside, not covered ---------------------------
        pad = page.locator("#grid").evaluate("el => getComputedStyle(el).paddingRight")
        last = page.locator("#grid .card").last.bounding_box()
        print("grid padding-right while open: %s; last tile right edge: %s"
              % (pad, last and round(last["x"] + last["width"])))
        if last and last["x"] + last["width"] > 881:
            problems.append("grid content runs under the open panel")

        # --- the open card is marked in the grid -------------------------------
        sel = page.locator("#grid .card.selected")
        n = sel.count()
        name = sel.first.locator(".meta strong").inner_text() if n else None
        print("selected tiles: %d (%r); panel: %r" % (n, name, after))
        if n != 1:
            problems.append("expected exactly 1 selected tile, found %d" % n)
        elif name not in after:
            problems.append("selected tile %r is not the card in the panel %r" % (name, after))

        # --- Escape closes too -------------------------------------------------
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
        if page.locator("#panel").evaluate("el => el.classList.contains('open')"):
            problems.append("Escape did not close the drawer")
        if page.locator("#grid .card.selected").count():
            problems.append("selection survived closing the drawer")

        browser.close()

    print()
    if console_errors:
        print("JS ERRORS:")
        for e in console_errors[:12]:
            print("   " + e)
        problems.append("%d JS error(s) in the console" % len(console_errors))
    else:
        print("no JS errors")

    print()
    if problems:
        print("FAILED:")
        for p_ in problems:
            print("  - " + p_)
        return 1
    print("screenshots: %s" % SHOTS)
    print("PASSED - drawer opens, closes and animates; grid does not refetch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
