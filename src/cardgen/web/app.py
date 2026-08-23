"""The local gallery server.

Localhost, single user, no authentication -- a deliberate non-goal in PROJECT.md.
The bind address is not configurable to 0.0.0.0 from here on purpose: opening
this to a network would need auth first, and making it a flag invites doing it
without.
"""

from __future__ import annotations

import json
from pathlib import Path

import cherrypy

from ..render import REPO_ROOT, render_and_record
from ..store import SessionLocal, init_db
from .api import CardsAPI, MetaAPI
from .queue import RENDER_QUEUE

WEB_DIR = REPO_ROOT / "web"
DEFAULT_PORT = 8765


def _json_error(status, message, traceback, version):
    """Errors come back as JSON, so the frontend never has to parse an HTML page."""
    cherrypy.response.headers["Content-Type"] = "application/json; charset=utf-8"
    return json.dumps({"error": message, "status": status}, ensure_ascii=False)


def _render_worker(card_id: int) -> None:
    """Queue worker: render one stored card and record the outcome."""
    with SessionLocal() as db:
        render_and_record(db, card_id)


class Root:
    @cherrypy.expose
    def index(self):
        raise cherrypy.HTTPRedirect("/web/index.html")


def build_config() -> dict:
    """Static mounts. Every directory the rendered HTML references must be here.

    A card page resolves ``assets/...`` and ``backgrounds/...`` from the repo
    root, so those two are served under the same names the templates use.
    """
    def static(path: Path) -> dict:
        return {"tools.staticdir.on": True, "tools.staticdir.dir": str(path)}

    return {
        "/": {
            "error_page.default": _json_error,
            "tools.encode.on": True,
            "tools.encode.encoding": "utf-8",
        },
        # CherryPy treats a class with an `index` method as a directory and
        # 301s /api/cards to /api/cards/. Harmless for a GET, but a redirected
        # POST is not guaranteed to keep its method or body.
        "/api": {"tools.trailing_slash.on": False},
        "/web": static(WEB_DIR),
        "/assets": static(REPO_ROOT / "assets"),
        "/backgrounds": static(REPO_ROOT / "backgrounds"),
        "/out": static(REPO_ROOT / "out"),
        "/style.css": {
            "tools.staticfile.on": True,
            "tools.staticfile.filename": str(REPO_ROOT / "style.css"),
        },
    }


def build_app() -> Root:
    root = Root()
    root.api = Root()
    root.api.cards = CardsAPI()
    root.api.meta = MetaAPI()
    return root


def serve(port: int = DEFAULT_PORT, *, block: bool = True) -> None:
    init_db()
    RENDER_QUEUE.start(_render_worker)

    cherrypy.config.update({
        "server.socket_host": "127.0.0.1",
        "server.socket_port": port,
        "engine.autoreload.on": False,
        "log.screen": True,
    })
    cherrypy.tree.mount(build_app(), "/", build_config())
    cherrypy.engine.start()
    print("\nCardGenerator gallery: http://127.0.0.1:{}/web/index.html\n".format(port))
    if block:
        cherrypy.engine.block()


def stop() -> None:
    RENDER_QUEUE.stop()
    cherrypy.engine.exit()


if __name__ == "__main__":
    serve()
