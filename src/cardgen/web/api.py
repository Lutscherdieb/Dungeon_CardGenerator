"""The JSON API the gallery talks to.

Every write goes through ``cardgen.store.repo``, so a card cannot reach the
database without passing the model, and the derived columns cannot disagree with
the stored JSON. The handlers here do routing, file handling and error shaping --
no validation logic of their own.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Callable, Dict

import cherrypy

from ..model import card_type_names
from ..model.schemas import schema_for
from ..render import ARTWORK_DIR, REPO_ROOT, render_dir_for, safe_stem
from ..spec import check_artwork, profile_for_type
from ..store import (
    CardValidationError,
    SessionLocal,
    create_card,
    delete_card,
    get_card,
    list_cards,
    update_card,
)
from .queue import RENDER_QUEUE

#: Image types the artwork upload accepts. Playwright renders whatever Chromium
#: can display; this list is the intersection with what Pillow can measure for
#: the resolution warning.
ALLOWED_ART_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def _body() -> Dict[str, Any]:
    raw = cherrypy.request.body.read().decode("utf-8") or "{}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise cherrypy.HTTPError(400, "body is not valid JSON: {}".format(exc))
    if not isinstance(parsed, dict):
        raise cherrypy.HTTPError(400, "body must be a JSON object")
    return parsed


def _by_method(handlers: Dict[str, Callable[[], Any]]):
    """Dispatch on the request method, or 405 with the methods that do exist.

    The predecessor repeated `if method == 'GET': ... if method == 'POST': ...`
    in every handler and returned a hand-built 405 dict at the bottom of each.
    """
    method = cherrypy.request.method.upper()
    handler = handlers.get(method)
    if handler is None:
        cherrypy.response.headers["Allow"] = ", ".join(sorted(handlers))
        raise cherrypy.HTTPError(405, "method not allowed")
    return handler()


def _card_id(raw: str) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise cherrypy.HTTPError(400, "card id must be an integer")


def _require(row, card_id: int):
    if row is None:
        raise cherrypy.HTTPError(404, "no card with id {}".format(card_id))
    return row


def _enqueue(card_id: int) -> None:
    RENDER_QUEUE.enqueue(card_id)


class CardsAPI:
    """/api/cards"""

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def index(self, **params):
        return _by_method({"GET": self._list, "POST": self._create})

    def _list(self):
        with SessionLocal() as db:
            rows = list_cards(db, card_type=cherrypy.request.params.get("type"))
            return {"cards": [self._row_view(r) for r in rows]}

    def _create(self):
        payload = _body()
        with SessionLocal() as db:
            try:
                row = create_card(db, payload)
            except CardValidationError as exc:
                raise cherrypy.HTTPError(422, str(exc))
            db.commit()
            card_id = row.id
        _enqueue(card_id)
        cherrypy.response.status = 201
        return {"id": card_id}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def default(self, card_id, *rest, **params):
        cid = _card_id(card_id)
        sub = rest[0] if rest else None

        if sub is None:
            return _by_method({
                "GET": lambda: self._get(cid),
                "PUT": lambda: self._update(cid),
                "DELETE": lambda: self._delete(cid),
            })
        if sub == "artwork":
            return _by_method({"POST": lambda: self._artwork(cid)})
        if sub == "render":
            return _by_method({
                "POST": lambda: self._render(cid),
                "GET": lambda: self._render_status(cid),
            })
        raise cherrypy.HTTPError(404, "unknown sub-resource {!r}".format(sub))

    # -- single card -------------------------------------------------------

    def _row_view(self, row) -> Dict[str, Any]:
        view = row.as_dict()
        live = RENDER_QUEUE.status(row.id)
        if live:
            view["render"]["queue"] = live
        directory = render_dir_for(row.id).as_posix()
        stem = safe_stem(row.name)
        view["render"]["urls"] = {
            "canvas": "/{}/{}.png".format(directory, stem),
            "trim": "/{}/{}_trim.png".format(directory, stem),
            "safe": "/{}/{}_safe.png".format(directory, stem),
        }
        return view

    def _get(self, cid: int):
        with SessionLocal() as db:
            return self._row_view(_require(get_card(db, cid), cid))

    def _update(self, cid: int):
        payload = _body()
        card = payload.get("card", payload)
        with SessionLocal() as db:
            _require(get_card(db, cid), cid)
            try:
                update_card(db, cid, card)
            except CardValidationError as exc:
                raise cherrypy.HTTPError(422, str(exc))
            db.commit()
        _enqueue(cid)
        return {"ok": True, "id": cid}

    def _delete(self, cid: int):
        with SessionLocal() as db:
            if not delete_card(db, cid):
                raise cherrypy.HTTPError(404, "no card with id {}".format(cid))
            db.commit()
        return {"ok": True, "id": cid}

    # -- artwork -----------------------------------------------------------

    def _artwork(self, cid: int):
        part = cherrypy.request.params.get("file")
        if part is None or not hasattr(part, "file"):
            raise cherrypy.HTTPError(400, "no file uploaded (field name must be 'file')")

        suffix = Path(part.filename or "").suffix.lower()
        if suffix not in ALLOWED_ART_SUFFIXES:
            raise cherrypy.HTTPError(415, "unsupported image type {!r}; allowed: {}".format(
                suffix or "(none)", ", ".join(sorted(ALLOWED_ART_SUFFIXES))))

        with SessionLocal() as db:
            row = _require(get_card(db, cid), cid)
            card = dict(row.data)
            card_type = row.type

            # Artwork is named after the card, matching the convention the
            # hand-placed backgrounds already follow.
            art_dir = REPO_ROOT / ARTWORK_DIR
            art_dir.mkdir(parents=True, exist_ok=True)
            target = art_dir / "{}{}".format(safe_stem(row.name), suffix)
            with open(target, "wb") as out:
                shutil.copyfileobj(part.file, out)

            warnings = check_artwork(str(target), profile_for_type(card_type))

            card["Background"] = "./{}/{}".format(ARTWORK_DIR.as_posix(), target.name)
            try:
                update_card(db, cid, card)
            except CardValidationError as exc:
                raise cherrypy.HTTPError(422, str(exc))
            db.commit()

        _enqueue(cid)
        return {"ok": True, "background": card["Background"], "warnings": warnings}

    # -- render ------------------------------------------------------------

    def _render(self, cid: int):
        with SessionLocal() as db:
            _require(get_card(db, cid), cid)
        _enqueue(cid)
        return {"ok": True, "id": cid, "status": RENDER_QUEUE.status(cid)}

    def _render_status(self, cid: int):
        with SessionLocal() as db:
            row = _require(get_card(db, cid), cid)
            return {
                "id": cid,
                "status": row.render_status,
                "queue": RENDER_QUEUE.status(cid),
                "error": row.render_error,
                "png": row.render_png,
            }


class MetaAPI:
    """/api/meta -- what the gallery needs to build its form."""

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def types(self, **params):
        return {"types": card_type_names()}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def schema(self, card_type=None, **params):
        if not card_type:
            return {"schemas": {t: schema_for(t) for t in card_type_names()}}
        key = card_type.strip().lower()
        if key not in card_type_names():
            raise cherrypy.HTTPError(404, "unknown card type {!r}".format(card_type))
        return schema_for(key)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def profile(self, card_type="room", **params):
        p = profile_for_type(card_type)
        return {
            "id": p.id,
            "label": p.label,
            "dpi": p.dpi,
            "canvas": list(p.canvas),
            "trim": [p.trim_w, p.trim_h],
            "safe": [p.safe_w, p.safe_h],
            "artwork_min": [p.safe_w, p.safe_h],
        }
