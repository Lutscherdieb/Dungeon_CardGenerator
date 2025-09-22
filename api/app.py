# api/app.py
import cherrypy, os
from cherrypy.lib.static import serve_file

from api.settings import Settings
from api.routes.cards import CardsAPI,RenderAPI

# NEW: create tables at startup
from api.db.base import Base
from api.db.session import engine          # uses CARDGEN_DB_URL or sqlite file
from api.db import models                  # ensure models are imported so tables exist
from api.services.render_queue import RENDER_QUEUE
from api.services.render_worker import render_card_worker

class Root:
    def __init__(self):
        self._s = Settings()

    @cherrypy.expose
    def index(self):
        index_path = os.path.join(self._s.preview_dir, "feed.html")
        return serve_file(index_path, content_type="text/html")

def cors():
    h = cherrypy.response.headers
    h['Access-Control-Allow-Origin'] = '*'
    h['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    h['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'

if __name__ == "__main__":
    # --- Create DB tables once on boot ---
    os.makedirs("./data", exist_ok=True)   # for sqlite default
    Base.metadata.create_all(bind=engine)  # <-- create tables
    # Start render worker
    RENDER_QUEUE.start(render_card_worker)

    s = Settings()

    cherrypy.config.update({
        'server.socket_host': '127.0.0.1',
        'server.socket_port': 8765,
        'tools.encode.on': True,
        'tools.encode.encoding': 'utf-8',
        'tools.cors.on': True,
        'log.screen': True,
        # Dev helpers
        'request.show_tracebacks': True,
    })
    cherrypy.tools.cors = cherrypy.Tool('before_finalize', cors, priority=60)

    conf = {
        '/assets':    {'tools.staticdir.on': True, 'tools.staticdir.dir': s.assets_dir},
        '/templates': {'tools.staticdir.on': True, 'tools.staticdir.dir': s.templates_dir},
        '/outputs':   {'tools.staticdir.on': True, 'tools.staticdir.dir': s.outputs_dir},
        '/preview':   {'tools.staticdir.on': True, 'tools.staticdir.dir': s.preview_dir},
        '/backgrounds': {'tools.staticdir.on': True, 'tools.staticdir.dir': os.path.abspath('./backgrounds')},
    }

    root = Root()
    root.api = Root()
    root.api.cards = CardsAPI()
    root.api.render = RenderAPI()

    cherrypy.quickstart(root, '/', config=conf)

