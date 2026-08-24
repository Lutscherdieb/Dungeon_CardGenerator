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
- Opening the drawer relayouts the grid ONCE. Animating the grid's padding
  walked it through 6 -> 5 -> 4 columns in 180ms, because auto-fill recomputes
  the column count at every intermediate width; the middle state lasted 16ms
  and read as a flicker.
"""
import os
import sys
import tempfile

from playwright.sync_api import sync_playwright

BASE = os.environ.get("CARDGEN_URL", "http://127.0.0.1:8765") + "/web/index.html"
SHOTS = os.environ.get("CARDGEN_SHOTS", tempfile.mkdtemp(prefix="cardgen-shots-"))

problems = []
thumb_requests = []       # every thumbnail request, in order

#: Records the grid's column count every animation frame for 700ms, so a
#: relayout cascade during the drawer transition is visible as more than one
#: distinct state rather than having to be eyeballed.
COLUMN_SAMPLER = """
() => {
  const grid = document.getElementById('grid');
  window.__samples = [];
  const t0 = performance.now();
  (function tick() {
    const cs = getComputedStyle(grid);
    window.__samples.push({
      t: Math.round(performance.now() - t0),
      cols: cs.gridTemplateColumns.split(' ').length,
      pad: cs.paddingRight,
    });
    if (performance.now() - t0 < 700) requestAnimationFrame(tick);
  })();
}
"""


def column_states(page):
    """The distinct column counts the grid passed through, in order."""
    steps, last = [], None
    for sample in page.evaluate("() => window.__samples"):
        if sample["cols"] != last:
            steps.append(sample)
            last = sample["cols"]
    return steps
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

        # Geometry is measured, never predicted. documentElement.clientWidth is
        # NOT the containing block for a position:fixed panel once
        # scrollbar-gutter reserves space -- it read 1440 while the panel's own
        # right edge sat at 1425. So the panel is checked against itself: open
        # position and width are recorded, and "closed" means it has travelled
        # its full width to the right of that.

        tiles = page.locator("#grid .card").count()
        print("tiles rendered: %d" % tiles)
        if tiles < 8:
            problems.append("only %d tiles -- import some cards first" % tiles)

        # --- drawer starts closed -----------------------------------------
        panel_open = page.locator("#panel").evaluate("el => el.classList.contains('open')")
        load_x = page.locator("#panel").bounding_box()["x"]
        print("on load: panel .open=%s  x=%s" % (panel_open, round(load_x)))
        if panel_open:
            problems.append("panel is open on load")
        page.screenshot(path=SHOTS + "/01-grid.png")

        # --- open a card ---------------------------------------------------
        mark = len(thumb_requests)
        page.locator("#grid .card").first.click()
        page.wait_for_selector("#panel.open", timeout=5000)
        page.wait_for_timeout(600)
        box = page.locator("#panel").bounding_box()
        open_x, panel_w = box["x"], box["width"]
        open_right = open_x + panel_w
        print("open: x=%d width=%d right edge=%d" % (open_x, panel_w, open_right))
        # Now the load-time position can be judged: fully clear of the right edge.
        if load_x < open_right - 1:
            problems.append("panel was %spx on screen at load" % round(open_right - load_x))

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
        print("after X: .open=%s  x=%s (open was %d)  aria-hidden=%s"
              % (still_open, box and round(box["x"]), open_x, aria))
        if still_open:
            problems.append("X did not remove .open")
        if box and box["x"] < open_right - 1:
            problems.append("panel only slid %spx of its %spx width after X"
                            % (round(box["x"] - open_x), round(panel_w)))
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
        if last and last["x"] + last["width"] > open_x + 1:
            problems.append("grid content runs under the open panel (right edge %s > %s)"
                            % (round(last["x"] + last["width"]), open_x))

        # --- the open card is marked in the grid -------------------------------
        sel = page.locator("#grid .card.selected")
        n = sel.count()
        name = sel.first.locator(".meta strong").inner_text() if n else None
        print("selected tiles: %d (%r); panel: %r" % (n, name, after))
        if n != 1:
            problems.append("expected exactly 1 selected tile, found %d" % n)
        elif name not in after:
            problems.append("selected tile %r is not the card in the panel %r" % (name, after))

        # --- the grid must relayout once, not cascade --------------------------
        page.locator("#btn-close").click()
        page.wait_for_timeout(500)
        page.evaluate(COLUMN_SAMPLER)
        page.locator("#grid .card").first.click()
        page.wait_for_timeout(900)
        steps = column_states(page)
        print("grid column states while the drawer opened: %s"
              % " -> ".join("%dcol@%dms" % (s["cols"], s["t"]) for s in steps))
        if len(steps) > 2:
            problems.append(
                "grid relayouts through %d column counts while the drawer opens "
                "(should be at most 2: before and after)" % len(steps))

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
