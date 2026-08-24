"""Artwork lives in the store as bytes. Drive the real UI and prove it.

Needs a server already running::

    python -m cardgen.cli serve          # in one terminal
    python tests/check_artwork.py        # in another

Creates a throwaway card, exercises upload / save / re-upload, then deletes it
in a finally block. Not part of the verify gate: it needs a server, and it
writes to the store.

What it guards:

- No Background path field exists in the form. Artwork is a property of the
  card, not a path a human maintains.
- An upload puts the bytes in the row, with the right mime and dimensions.
- Saving the form cannot revert the artwork. It could before: the upload
  rewrote a Background path server-side, the open form still held the old one,
  and the next save put it back.
- A second upload replaces the first rather than accumulating.
- Artwork below the safe zone warns but is still accepted.
- The card re-renders after the artwork changes.
"""
import json
import os
import sys
import tempfile
import urllib.request

from PIL import Image
from playwright.sync_api import sync_playwright

import os as _os

BASE = _os.environ.get("CARDGEN_URL", "http://127.0.0.1:8765")
API = BASE + "/api"
PAGE = BASE + "/web/index.html"
NAME = "Zzz Artwork Probe"

problems = []


def call(path, method="GET", payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(API + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read() or "{}")


def art_summary(card_id):
    a = call("/cards/%d" % card_id)["artwork"]
    return {k: a[k] for k in ("present", "mime", "width", "height", "bytes")}


def main():
    tmp = tempfile.gettempdir()
    first = os.path.join(tmp, "probe_art_1.jpg")
    second = os.path.join(tmp, "probe_art_2.png")
    Image.new("RGB", (1200, 1200), (200, 60, 20)).save(first, quality=90)
    Image.new("RGB", (500, 500), (10, 90, 160)).save(second)   # below the safe zone

    cid = call("/cards", "POST", {
        "Type": "Spell", "Name": NAME, "Tier": 1, "Description": "probe",
        "Mana": 1, "Cards": 1, "Food": 0})["id"]
    print("created card #%d" % cid)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(PAGE, wait_until="networkidle")
            page.wait_for_selector("#grid .card", timeout=15000)
            page.locator('#grid [data-id="%d"]' % cid).click()
            page.wait_for_selector("#panel.open", timeout=5000)
            page.wait_for_timeout(500)

            # 1. No path field anywhere in the form.
            fields = page.evaluate(
                "() => [...document.querySelectorAll('#form-fields .field')]"
                ".map(f => f.dataset.key)")
            print("form fields: %s" % fields)
            if "Background" in fields:
                problems.append("a Background path field is still in the form")

            print("artwork before upload: %s" % art_summary(cid))
            if art_summary(cid)["present"]:
                problems.append("a brand new card already claims artwork")

            # 2. Upload puts bytes in the store.
            page.locator("#art-file").set_input_files(first)
            page.locator("#btn-art").click()
            page.wait_for_timeout(2500)
            after_upload = art_summary(cid)
            print("artwork after upload:  %s" % after_upload)
            print("panel shows: %r" % page.locator("#art-meta").inner_text())
            if not after_upload["present"] or after_upload["mime"] != "image/jpeg":
                problems.append("upload did not store the image: %s" % after_upload)
            if after_upload["width"] != 1200:
                problems.append("stored dimensions wrong: %s" % after_upload)

            # 3. Saving the form must not disturb it -- artwork is not a field.
            page.locator("#btn-save").click()
            page.wait_for_timeout(3000)
            after_save = art_summary(cid)
            print("artwork after Save & render: %s" % after_save)
            if after_save != after_upload:
                problems.append("saving the form changed the artwork: %s -> %s"
                                % (after_upload, after_save))

            # 4. A second upload overwrites rather than accumulating, and warns.
            page.locator("#art-file").set_input_files(second)
            page.locator("#btn-art").click()
            page.wait_for_timeout(2500)
            after_second = art_summary(cid)
            warn = ""
            if not page.locator("#art-warning").is_hidden():
                warn = page.locator("#art-warning").inner_text()
            print("artwork after 2nd upload: %s" % after_second)
            print("low-resolution warning: %r" % warn)
            if after_second["bytes"] == after_upload["bytes"]:
                problems.append("second upload did not replace the first")
            if after_second["mime"] != "image/png" or after_second["width"] != 500:
                problems.append("second upload not stored correctly: %s" % after_second)
            if "print soft" not in warn:
                problems.append("no low-resolution warning for 500x500 artwork")

            # 5. The rendered card must actually use the new artwork.
            page.wait_for_timeout(4000)
            status = call("/cards/%d/render" % cid)
            print("render after artwork change: %s" % status["status"])
            if status["status"] != "done":
                problems.append("re-render after upload did not finish: %s" % status)

            if errors:
                problems.append("JS errors: %s" % errors[:3])
            browser.close()
    finally:
        call("/cards/%d" % cid, "DELETE")
        for f in (first, second):
            if os.path.exists(f):
                os.remove(f)
        print("deleted probe card #%d" % cid)

    print()
    if problems:
        print("FAILED:")
        for x in problems:
            print("  - " + x)
        return 1
    print("PASSED - artwork is stored bytes, upload replaces it, saving cannot revert it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
