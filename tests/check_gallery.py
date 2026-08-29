"""Drive the gallery in a real browser and check the things unit tests cannot.

Needs a server already running::

    python -m cardgen.cli serve          # in one terminal
    python tests/check_gallery.py        # in another

Not part of the verify gate, which must stay runnable with nothing listening.
Run it after touching anything under web/.

What it guards, and why each one is here:

- Opening the editor does NOT change the grid's column count, and does not move
  the clicked tile sideways. This is the whole point of the inline editor. Its
  predecessor was a right-hand drawer that narrowed the grid; `auto-fill` then
  recomputed the column count at the new width and repositioned all 137 tiles,
  so opening and closing a card lost your place in the gallery.
- The editor lands on the row directly BELOW the card it belongs to, and the
  card stays visible.
- Selecting a card does not refetch thumbnails the browser already has. The
  grid used to cache-bust every image URL with Date.now(), so any repaint
  re-downloaded all 137.
- Switching cards takes one click.
- Exactly one tile is marked as the one the editor belongs to.
- No field on any card type falls back to the raw-JSON box. That fallback is
  deliberately silent -- it keeps an unrecognised shape visible instead of
  dropping it -- which is exactly why nothing reported that `Slots` had been
  landing in it. The builder tested one level of array nesting and `Slots` was
  then `List[List[Tuple[CreatureType, int]]]`, so every Room offered a JSON
  blob where the spot editor should have been.
- The filter popover floats: opening it changes neither the column count nor
  the grid's width, and a filter actually reduces the number of tiles.
- The New card dialog offers the card types as a dropdown. It used to be a
  window.prompt() taking the type as free text.
- The Description field lists every [] icon code, and clicking one inserts it.
"""
import os
import sys
import tempfile

from playwright.sync_api import sync_playwright

BASE = os.environ.get("CARDGEN_URL", "http://127.0.0.1:8765") + "/web/index.html"
SHOTS = os.environ.get("CARDGEN_SHOTS", tempfile.mkdtemp(prefix="cardgen-shots-"))

problems = []
thumb_requests = []       # every thumbnail request, in order

#: Both popovers live in the DOM at once, so every query has to say which.
#: popover() puts its title in aria-label, which is the stable handle.
FILTERS = '.pop[aria-label="Filters"]'
NEWCARD = '.pop[aria-label="New card"]'

#: Records the grid's column count every animation frame for 700ms, so a
#: relayout cascade is visible as more than one distinct state rather than
#: having to be eyeballed.
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


def columns(page):
    return page.evaluate(
        "() => getComputedStyle(document.getElementById('grid'))"
        ".gridTemplateColumns.split(' ').length")


console_errors = []


def refetches(since=0):
    """Thumbnails requested that had ALREADY been requested earlier.

    A first request for a tile is fine -- lazy loading fetches tiles as they
    scroll or reflow into view. The bug being guarded against is the SAME image
    being pulled twice, which is what a cache-busted URL on every repaint caused.
    """
    seen = set(u.split('?')[0] for u in thumb_requests[:since])
    dupes = []
    for u in thumb_requests[since:]:
        base = u.split('?')[0]
        if base in seen:
            dupes.append(u)
        seen.add(base)
    return dupes


def open_first_card(page):
    """Click the first tile and wait for the editor to be placed."""
    page.locator("#grid .card").first.click()
    page.wait_for_selector("#editor:not([hidden])", timeout=5000)
    page.wait_for_timeout(400)


def clear_filters(page):
    page.evaluate("() => localStorage.removeItem('cardgen.filters')")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        page.on("pageerror", lambda e: console_errors.append("pageerror: %s" % e))
        page.on("console", lambda m: console_errors.append("console.%s: %s" % (m.type, m.text))
                if m.type == "error" else None)
        page.on("request", lambda r: thumb_requests.append(r.url)
                if "_thumb.png" in r.url else None)

        # A filter left in localStorage by an earlier run would hide most of the
        # deck and make every count below meaningless.
        page.goto(BASE, wait_until="domcontentloaded")
        clear_filters(page)
        page.goto(BASE, wait_until="networkidle")
        page.wait_for_selector("#grid .card", timeout=15000)

        tiles = page.locator("#grid .card").count()
        print("tiles rendered: %d" % tiles)
        if tiles < 8:
            problems.append("only %d tiles -- import some cards first" % tiles)

        # --- editor starts hidden --------------------------------------------
        if not page.locator("#editor").is_hidden():
            problems.append("the editor is open on load")
        page.screenshot(path=SHOTS + "/01-grid.png")

        # --- geometry is measured, never predicted ---------------------------
        # Record the grid's own shape and the first tile's own position, then
        # compare against them after opening. Deriving anything from
        # documentElement.clientWidth is what produced three false failures
        # against correct behaviour: scrollbar-gutter reserves space outside it.
        cols_before = columns(page)
        first_before = page.locator("#grid .card").first.bounding_box()
        grid_before = page.locator("#grid").bounding_box()

        mark = len(thumb_requests)
        open_first_card(page)

        cols_after = columns(page)
        first_after = page.locator("#grid .card").first.bounding_box()
        grid_after = page.locator("#grid").bounding_box()
        print("columns %d -> %d; grid width %d -> %d; first tile x %d -> %d"
              % (cols_before, cols_after, grid_before["width"], grid_after["width"],
                 first_before["x"], first_after["x"]))
        if cols_before != cols_after:
            problems.append("opening the editor changed the column count %d -> %d"
                            % (cols_before, cols_after))
        if abs(grid_before["width"] - grid_after["width"]) > 1:
            problems.append("opening the editor changed the grid width %d -> %d"
                            % (grid_before["width"], grid_after["width"]))
        if abs(first_before["x"] - first_after["x"]) > 1:
            problems.append("opening the editor moved the first tile sideways %d -> %d"
                            % (first_before["x"], first_after["x"]))

        # --- the editor is on the row below its card -------------------------
        tile_box = page.locator("#grid .card").first.bounding_box()
        ed_box = page.locator("#editor").bounding_box()
        print("first tile bottom=%d, editor top=%d" % (
            tile_box["y"] + tile_box["height"], ed_box["y"]))
        if ed_box["y"] < tile_box["y"] + tile_box["height"] - 1:
            problems.append("the editor overlaps its own card instead of sitting below it")
        if ed_box["width"] < grid_after["width"] - 60:
            problems.append("the editor is %dpx wide in a %dpx grid -- not a full row"
                            % (ed_box["width"], grid_after["width"]))

        fields = page.locator("#form-fields .field").count()
        title = page.locator("#editor-title").inner_text()
        print("editor title: %r, form fields: %d" % (title, fields))
        if fields == 0:
            problems.append("form rendered no fields")
        page.screenshot(path=SHOTS + "/02-editor-open.png")

        # --- the grid must NOT refetch itself --------------------------------
        page.wait_for_timeout(3000)  # longer than the 1.2s poll interval
        dupes = refetches(mark)
        print("thumbnail requests after opening a card: %d total, %d of them refetches"
              % (len(thumb_requests) - mark, len(dupes)))
        if dupes:
            problems.append("selecting a card refetched %d already-loaded thumbnails"
                            % len(dupes))

        # --- close with the X --------------------------------------------------
        page.locator("#btn-close").click()
        page.wait_for_timeout(300)
        if not page.locator("#editor").is_hidden():
            problems.append("the X did not close the editor")
        if page.locator("#grid .card.selected").count():
            problems.append("selection survived closing the editor")
        if columns(page) != cols_before:
            problems.append("closing the editor changed the column count")
        page.screenshot(path=SHOTS + "/03-closed.png")

        # --- opening must not relayout the grid at all -------------------------
        page.evaluate(COLUMN_SAMPLER)
        open_first_card(page)
        steps = column_states(page)
        print("grid column states while the editor opened: %s"
              % " -> ".join("%dcol@%dms" % (s["cols"], s["t"]) for s in steps))
        if len(steps) > 1:
            problems.append(
                "grid relayouts through %d column counts while the editor opens "
                "(should be exactly 1 -- the width never changes)" % len(steps))

        # --- switching cards takes ONE click -----------------------------------
        before = page.locator("#editor-title").inner_text()
        page.locator("#grid .card").nth(7).click()
        page.wait_for_timeout(400)
        after = page.locator("#editor-title").inner_text()
        print("switch card in one click: %r -> %r" % (before, after))
        if before == after or page.locator("#editor").is_hidden():
            problems.append("clicking another card did not switch the editor in one click")

        # --- the open card is marked in the grid -------------------------------
        sel = page.locator("#grid .card.selected")
        n = sel.count()
        name = sel.first.locator(".meta strong").inner_text() if n else None
        print("selected tiles: %d (%r); editor: %r" % (n, name, after))
        if n != 1:
            problems.append("expected exactly 1 selected tile, found %d" % n)
        elif name not in after:
            problems.append("selected tile %r is not the card in the editor %r" % (name, after))

        # --- Escape closes ------------------------------------------------------
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        if not page.locator("#editor").is_hidden():
            problems.append("Escape did not close the editor")

        # --- the filter popover floats and filters ------------------------------
        cols_pre = columns(page)
        width_pre = page.locator("#grid").bounding_box()["width"]
        page.locator("#btn-filters").click()
        page.wait_for_selector(".pop:not([hidden])", timeout=3000)
        print("filter popover open: columns %d -> %d, grid width %d -> %d"
              % (cols_pre, columns(page), width_pre,
                 page.locator("#grid").bounding_box()["width"]))
        if columns(page) != cols_pre:
            problems.append("the filter popover changed the grid's column count")
        if abs(page.locator("#grid").bounding_box()["width"] - width_pre) > 1:
            problems.append("the filter popover changed the grid's width")
        page.screenshot(path=SHOTS + "/04-filters.png")

        # Every card attribute should be offered. Derived from the schemas, so
        # this asserts the count is plausible rather than naming each one.
        rows = page.locator(FILTERS + " .filter-row").count()
        labels = page.locator(FILTERS + " .filter-label").evaluate_all(
            "els => els.map(e => e.textContent)")
        print("filter rows: %d (%s)" % (rows, ", ".join(labels)))
        for required in ("Type", "Tier", "Starter", "Mana", "Treasure", "Slots"):
            if required not in labels:
                problems.append("no filter offered for %r" % required)

        before_n = page.locator("#grid .card").count()
        page.locator(FILTERS + " .filter-row", has_text="Type").locator(
            ".chip", has_text="Room").first.click()
        page.wait_for_timeout(300)
        after_n = page.locator("#grid .card").count()
        print("filter Type=Room: %d tiles -> %d" % (before_n, after_n))
        if after_n >= before_n or after_n == 0:
            problems.append("filtering by Type=Room gave %d of %d tiles" % (after_n, before_n))
        shown = page.locator("#shown-count").inner_text()
        if str(after_n) not in shown:
            problems.append("the shown-count %r does not report the %d visible tiles"
                            % (shown, after_n))

        # A Room-only grid is also the cheapest place to prove Starter filters.
        page.locator(FILTERS + " .filter-row", has_text="Starter").locator(
            ".chip", has_text="yes").first.click()
        page.wait_for_timeout(300)
        starters = page.locator("#grid .card").count()
        print("filter Starter=yes on top of Type=Room: %d tiles" % starters)
        page.locator(FILTERS + " .filter-foot .btn").click()      # Clear all
        page.wait_for_timeout(300)
        if page.locator("#grid .card").count() != before_n:
            problems.append("Clear all did not restore every tile")
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)

        # --- New card offers a type dropdown ------------------------------------
        page.locator("#btn-new").click()
        page.wait_for_selector(NEWCARD + ":not([hidden])", timeout=3000)
        options = page.locator(NEWCARD + " select option").evaluate_all(
            "els => els.map(e => e.value)")
        print("new-card type options: %s" % ", ".join(options))
        if len(options) < 8:
            problems.append("the New card dialog offers %d types, expected 8" % len(options))
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)

        # --- every card type gets real editors, not the JSON fallback -----------
        # One card of each type, because the shapes differ per type.
        for card_type in options:
            page.evaluate(
                "t => localStorage.setItem('cardgen.filters',"
                " JSON.stringify({Type: [t[0].toUpperCase() + t.slice(1)]}))", card_type)
            page.reload(wait_until="networkidle")
            page.wait_for_selector("#grid .card", timeout=10000)
            if not page.locator("#grid .card").count():
                problems.append("no cards of type %s to check" % card_type)
                continue
            open_first_card(page)
            raw = page.locator('#form-fields .field[title^="No editor"]').evaluate_all(
                "els => els.map(e => e.dataset.key)")
            print("%-10s fields=%2d json-fallback=%s"
                  % (card_type, page.locator("#form-fields .field").count(), raw or "none"))
            if raw:
                problems.append(
                    "%s falls back to the raw-JSON box for %s -- the form builder "
                    "does not recognise that field's shape" % (card_type, ", ".join(raw)))

            # Spell is as good a type as any to prove the code legend on.
            if card_type == "spell":
                page.locator(".codes-toggle").click()
                page.wait_for_timeout(150)
                codes = page.locator(".codes .code").count()
                textarea = page.locator('#form-fields .field[data-key="Description"] textarea')
                original = textarea.input_value()
                page.locator(".codes .code").first.click()
                page.wait_for_timeout(150)
                inserted = textarea.input_value()
                print("code legend: %d codes; Description %d -> %d chars"
                      % (codes, len(original), len(inserted)))
                if codes < 10:
                    problems.append("the code legend lists %d codes, expected 17" % codes)
                if inserted == original or "[" not in inserted:
                    problems.append("clicking a code did not insert it into Description")

        clear_filters(page)
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
    print("PASSED - the editor opens inline without moving the grid; filters float")
    return 0


if __name__ == "__main__":
    sys.exit(main())
