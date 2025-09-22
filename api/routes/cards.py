# api/routes/cards.py
import os
import json
import uuid
import shutil
import cherrypy
from cherrypy._cpreqbody import Part

from api.db.session import SessionLocal
from api.db.models import Card
from api.services.render_queue import RENDER_QUEUE

from api.static_paths import UPLOAD_BG_DIR


def _json_out(payload, status=200):
    cherrypy.response.headers['Content-Type'] = 'application/json; charset=utf-8'
    cherrypy.response.status = status
    return json.dumps(payload, ensure_ascii=False).encode('utf-8')

def _normalize_keys(d: dict) -> dict:
    # accept upper/lower key variants
    keymap = {
        "type":"type","subtype":"subtype","name":"name","faction":"faction","tier":"tier",
        "mana":"mana","cards":"cards","food":"food",
        "defence":"defence","defense":"defence",
        "health":"health","movement":"movement","treasure":"treasure",
        "roads":"roads","slots":"slots",
        "rules":"rules","description":"description",
        "background":"background","backgroundimage":"background",
        "source":"source_json_path","source_json_path":"source_json_path",
        "creatures": "creatures"
    }
    out = {}
    for k, v in (d or {}).items():
        kk = keymap.get(str(k).lower())
        if kk:
            out[kk] = v
    return out

def _filter_fields(d: dict):
    allowed = {
        "type","subtype","name","faction","tier",
        "mana","cards","food","defence","health","movement","treasure",
        "roads","slots","rules","description","background","source_json_path","creatures",
    }
    return {k: v for k, v in (d or {}).items() if k in allowed}

class CardsAPI:
    @cherrypy.expose
    def index(self, **params):
        """GET /api/cards  |  POST /api/cards"""
        method = cherrypy.request.method.upper()

        if method == 'GET':
            try:
                with SessionLocal() as db:
                    rows = db.query(Card).order_by(Card.id.desc()).all()
                    return _json_out([c.as_dict() for c in rows])
            except Exception as e:
                return _json_out({"error": str(e)}, 500)

        if method == 'POST':
            try:
                payload = json.loads(cherrypy.request.body.read().decode('utf-8') or "{}")
                payload = _normalize_keys(payload)
                with SessionLocal() as db:
                    c = Card(**_filter_fields(payload))
                    db.add(c)
                    db.commit()
                    cid = c.id
                # enqueue after commit (visible to worker)
                RENDER_QUEUE.enqueue(cid)
                return _json_out({"id": cid}, 201)
            except Exception as e:
                return _json_out({"error": str(e)}, 400)

        return _json_out({"error": "method not allowed"}, 405)

    @cherrypy.expose
    def importjson(self, **params):
        """
        POST /api/cards/importjson
        multipart/form-data with one or many .json files under 'files'.
        Creates ALL cards, commits once, THEN enqueues each for rendering.
        """
        if cherrypy.request.method.upper() != 'POST':
            return _json_out({"error": "method not allowed"}, 405)

        # collect Part objects (supports multiple inputs and folder picker)
        parts = []
        for k, v in cherrypy.request.params.items():
            if isinstance(v, Part):
                parts.append(v)
            elif isinstance(v, list):
                parts.extend([p for p in v if isinstance(p, Part)])

        created_ids, skipped, errors = [], 0, []
        try:
            with SessionLocal() as db:
                for p in parts:
                    try:
                        raw = p.file.read()
                        data = json.loads(raw.decode('utf-8'))
                        data = _normalize_keys(data)
                        c = Card(**_filter_fields(data))
                        db.add(c)
                        db.flush()          # assign ID without committing
                        created_ids.append(c.id)
                    except Exception as e:
                        skipped += 1
                        fname = getattr(p, 'filename', '?')
                        errors.append(f"{fname}: {e}")

                db.commit()  # make rows visible to worker

            # Enqueue ALL created IDs after commit
            for cid in created_ids:
                RENDER_QUEUE.enqueue(cid)

        except Exception as e:
            return _json_out({"error": f"import failed: {e}"}, 500)

        return _json_out({
            "imported": len(created_ids),
            "ids": created_ids,
            "skipped": skipped,
            "errors": errors
        })

    @cherrypy.expose
    def default(self, id, *vpath, **params):
        """
        GET /api/cards/{id}
        PUT /api/cards/{id}
        """
        method = cherrypy.request.method.upper()
        try:
            cid = int(id)
        except Exception:
            return _json_out({"error":"invalid id"}, 400)

        with SessionLocal() as db:
            c = db.query(Card).filter(Card.id == cid).first()
            if not c:
                return _json_out({"error":"not found"}, 404)

            if method == 'GET':
                return _json_out(c.as_dict())

            if method == 'PUT':
                try:
                    payload = json.loads(cherrypy.request.body.read().decode('utf-8') or "{}")
                    payload = _normalize_keys(payload)
                    for k, v in _filter_fields(payload).items():
                        setattr(c, k, v)
                    db.add(c); db.commit()
                    # auto-render on edit
                    RENDER_QUEUE.enqueue(c.id)
                    return _json_out({"ok": True, "id": c.id})
                except Exception as e:
                    return _json_out({"error": str(e)}, 400)

        return _json_out({"error":"method not allowed"}, 405)

    @cherrypy.expose
    def upload_bg(self, id, **params):
        """
        POST /api/cards/{id}/upload_bg   (multipart with 'file')
        Saves background file, updates card.background, enqueues render.
        """
        if cherrypy.request.method.upper() != 'POST':
            return _json_out({"error":"method not allowed"}, 405)

        # find first file part named file/background/bg
        part = None
        for k, v in cherrypy.request.params.items():
            if isinstance(v, Part) and k in ('file', 'background', 'bg'):
                part = v; break
            if isinstance(v, list):
                for p in v:
                    if isinstance(p, Part) and k in ('file', 'background', 'bg'):
                        part = p; break

        if not part:
            return _json_out({"error":"no file uploaded (use field name 'file')"}, 400)

        os.makedirs(UPLOAD_BG_DIR, exist_ok=True)
        ext = os.path.splitext(part.filename or "")[1] or ".png"
        fname = f"{uuid.uuid4().hex}{ext}"
        out_path = os.path.join(UPLOAD_BG_DIR, fname)

        with open(out_path, "wb") as out:
            shutil.copyfileobj(part.file, out)

        rel_for_html = "./" + os.path.relpath(out_path, ".").replace("\\","/")

        with SessionLocal() as db:
            c = db.query(Card).filter(Card.id == int(id)).first()
            if not c:
                return _json_out({"error":"not found"}, 404)
            c.background = rel_for_html
            db.add(c); db.commit()

        RENDER_QUEUE.enqueue(int(id))
        return _json_out({"background": rel_for_html})

class RenderAPI:
    @cherrypy.expose
    def status(self, id=None):
        if id is None:
            return _json_out({"error":"missing id"}, 400)
        st = RENDER_QUEUE.status.get(int(id), "unknown")
        return _json_out({"id": int(id), "status": st})
