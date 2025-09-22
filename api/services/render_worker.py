# api/services/render_worker.py
from __future__ import annotations
import os
import json
from pathlib import Path

from api.db.session import SessionLocal
from api.db.models import Card
from api.static_paths import OUTPUTS_API_DIR, PROJECT_ROOT

# Reuse your existing render pipeline + schema info
from generate_card import (
    generate_html,
    generate_png_from_html,
    generate_safezone_png,
    generate_trim_png,
    SCHEMA_PATHS,
    load_schema,
)

def _project_rel(p: str | Path) -> str:
    p = Path(p)
    rel = os.path.relpath(p, PROJECT_ROOT)
    return "./" + rel.replace("\\", "/")

def _card_to_json_payload(c: Card) -> dict:
    # Start with superset; we'll filter by schema right after
    return {
        "Type":        (c.type or "").strip(),
        "Subtype":     (c.subtype or ""),
        "Name":        c.name or "",
        "Faction":     (c.faction or ""),
        "Tier":        c.tier if c.tier is not None else 0,

        "Mana":        c.mana or 0,
        "Cards":       c.cards or 0,
        "Food":        c.food or 0,
        "Defence":     c.defence or 0,
        "Health":      c.health or 0,
        "Movement":    c.movement or 0,
        "Treasure":    c.treasure or 0,

        "Roads":       c.roads or [],
        "Slots":       c.slots or [],

        "Rules":       c.rules or "",
        "Description": c.description or "",
        "Background":  c.background or "",
        "Creatures": c.creatures or [], 
        "Source":      c.source_json_path or "",
    }

def _schema_for_type(card_type: str) -> dict:
    key = (card_type or "").strip().lower()
    schema_path = SCHEMA_PATHS.get(key)
    if not schema_path:
        # Fallback: room
        schema_path = SCHEMA_PATHS.get("room")
    return load_schema(PROJECT_ROOT, schema_path)

def _filter_by_schema(payload: dict, schema: dict) -> dict:
    """
    Keep only keys listed in schema['properties'] (respects additionalProperties:false).
    """
    allowed = set((schema or {}).get("properties", {}).keys())
    return {k: v for k, v in payload.items() if k in allowed}

def render_card_worker(card_id: int) -> str:
    OUTPUTS_API_DIR.mkdir(parents=True, exist_ok=True)
    tmp_dir = OUTPUTS_API_DIR / "tmp_json"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    with SessionLocal() as db:
        card = db.query(Card).filter(Card.id == card_id).first()
        if not card:
            raise RuntimeError(f"Card id {card_id} not found")

        # 1) Build payload and filter it by schema of its Type
        raw_payload = _card_to_json_payload(card)
        schema = _schema_for_type(raw_payload.get("Type"))
        payload = _filter_by_schema(raw_payload, schema)

        # 2) Write temp JSON
        safe_base = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (payload.get("Name") or f"card_{card.id}"))
        tmp_json_path = tmp_dir / f"{card.id}_{safe_base}.json"
        with open(tmp_json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        # 3) HTML → PNG(s)
        html_path, output_name, size_key = generate_html(str(tmp_json_path), "", str(OUTPUTS_API_DIR))
        full_png = generate_png_from_html(html_path, str(OUTPUTS_API_DIR), output_name, size_key)

        # Optional crops
        try:
            safe_png = generate_safezone_png(full_png, str(OUTPUTS_API_DIR), output_name, size_key)
        except Exception:
            safe_png = None
        try:
            trim_png = generate_trim_png(full_png, str(OUTPUTS_API_DIR), output_name, size_key)
        except Exception:
            trim_png = None

        # 4) Prefer trim > full > safe
        chosen = trim_png or full_png or safe_png
        if not chosen:
            raise RuntimeError("Render pipeline produced no PNGs")

        rel_chosen = _project_rel(chosen)

        # 5) Update DB
        card.last_png_path = rel_chosen
        db.add(card)
        db.commit()

        return rel_chosen
