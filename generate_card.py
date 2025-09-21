import os
import sys
import json
import base64
import re
import argparse
import time
import hashlib, random
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright
from PIL import Image  # pip install pillow
from jsonschema import validate as js_validate, ValidationError


# =========================
# Size profiles (300 DPI)
# =========================
SIZE_PROFILES = {
    # 3.5" x 3.5" (trim), 1/8" bleed each side -> 1125x1125 full; safe = trim - 1/8" margin each side
    "SQUARE_3_5IN": {
        "bleed": (1125, 1125),
        "crop": (75, 75, 1050, 1050),  # left, top, right, bottom within full
        "trim":  (38, 38, 1088, 1088),   # (left, top, right, bottom) -> 1050×1050
    },
    # add more profiles later (e.g., standard TCG)
}


# =========================
# Template & schema registry
# =========================
# All templates live directly under templates/ and are named <type>_template.html
TEMPLATES_DIR = "templates"

TYPE_TO_TEMPLATE_FILE = {
    "room":     "room_template.html",
    "spell":    "spell_template.html",
    "research": "research_template.html", 
    "hero": "hero_template.html", 
    "trap": "trap_template.html",
    "creature": "creature_template.html",
    "treasure": "treasure_template.html",
    "overlord": "overlord_template.html",
}

TYPE_TO_SIZE = {
    "room":     "SQUARE_3_5IN",
    "spell":    "SQUARE_3_5IN",
    "research": "SQUARE_3_5IN",
    "hero": "SQUARE_3_5IN",
    "trap": "SQUARE_3_5IN",
    "creature": "SQUARE_3_5IN",
    "treasure": "SQUARE_3_5IN",
    "overlord": "SQUARE_3_5IN",
}

SCHEMA_PATHS = {
    "room":     "schemas/room.schema.json",
    "spell":    "schemas/spell.schema.json",
    "research": "schemas/research.schema.json",
    "hero": "schemas/hero.schema.json",
    "trap": "schemas/trap.schema.json",
    "creature": "schemas/creature.schema.json",
    "treasure": "schemas/treasure.schema.json",
    "overlord": "schemas/overlord.schema.json",
}



# =========================
# Inline symbol replacement
# =========================
TOKEN_TO_ICON = {
    "undead":   "undead.png",
    "demon":    "demon.png",
    "wild":     "wild.png",
    "magic":    "magic.png",
    "all":      "all.png",
    "mana":     "mana.png",
    "treasure": "treasure.png",
    "cards":    "cards.png",
    "defence":  "defence.png",
    "health": "health.png",
    "hero": "hero.png",
    "spell": "spell.png",
    "trap": "trap.png",
    "research": "research.png",
    "movement": "movement.png",
    "food": "food.png",
    "chaos": "chaos.png"

}

# [  token  ] with optional spaces, case-insensitive
_symbol_pattern = re.compile(
    r"\[\s*(undead|demon|wild|magic|all|mana|treasure|cards|defence|health|hero|spell|trap|research|movement|food|chaos)\s*\]",
    re.IGNORECASE
)

def replace_symbols_in_rules(text: str) -> str:
    """
    Replace bracketed tokens (e.g., [Undead]) with inline <img> tags.
    Works inside longer text like 'aaa[Demon]zzz'. Case/space tolerant.
    Returns the transformed HTML string.
    """
    if not isinstance(text, str):
        return text

    def _sub(m: re.Match) -> str:
        key = m.group(1).lower()
        filename = TOKEN_TO_ICON.get(key)
        if not filename:
            return m.group(0)
        # Root-relative thanks to <base href="{{ base_href }}">
        return f'<img src="assets/{filename}" alt="{key.title()}" class="inline-symbol icon-glow">'

    new_text, n = _symbol_pattern.subn(_sub, text)
    print(f"[Rules] Replacements: {n}")
    if n == 0:
        preview = text[:120].replace("\n", " ")
        print(f"[Rules] No tokens found in: {preview!r}")
    return new_text


# =========================
# Validation helpers
# =========================
def validate_assets(project_root: Path):
    """
    Ensure required root assets exist so templates render correctly.
    Adjust this list as your project evolves.
    """
    required_files = [
        project_root / "style.css",                  # stylesheet at project root

        # roads arrow
        project_root / "assets/arrow_up.png",

        # stat icons
        project_root / "assets/mana.png",
        project_root / "assets/cards.png",
        project_root / "assets/defence.png",
        project_root / "assets/treasure.png",
        project_root / "assets/movement.png", 
        project_root / "assets/health.png",

        # slot/symbol icons
        project_root / "assets/demon.png",
        project_root / "assets/undead.png",
        project_root / "assets/magic.png",
        project_root / "assets/wild.png",
        project_root / "assets/all.png",
    ]

    missing = [str(p) for p in required_files if not p.exists()]
    if missing:
        print("\n[ERROR] Missing required files for template rendering:")
        for m in missing:
            print(f"  - {m}")
        print("\nPlease add the missing files to your project before running again.")
        sys.exit(1)

def _rng_from_seed(seed: str) -> random.Random:
    h = hashlib.sha256(seed.encode("utf-8")).digest()
    # use first 8 bytes to create a deterministic int
    seed_int = int.from_bytes(h[:8], "big")
    return random.Random(seed_int)

def _gen_spider_side(side: str, tier: int, rng: random.Random,
                     canvas=1125, bleed=75, safe=975,
                     min_rays=12, max_rays=30,
                     steps_tier=( (2,3), (3,4), (4,6) ),
                     jitter_x=22, jitter_y=22):
    """
    side: 'top'|'bottom'|'left'|'right'
    Returns: list of paths (each: {'pts': [(x,y), ...]})
    Rays start at the safe-zone edge and step into the bleed with angular L segments.
    """
    # number of rays grows with tier
    rays = rng.randint(min_rays + tier, max_rays + 2 * tier)

    # safe-zone bounds
    safe_min = bleed
    safe_max = bleed + safe

    paths = []

    if side in ("top", "bottom"):
        # y coords
        y_start = safe_min if side == "top" else safe_max
        y_end   = 0 if side == "top" else canvas
        # x slots across the frame
        slots = [safe_min + (i + 0.5) * (safe / (rays + 0.0)) for i in range(rays)]
        for x0 in slots:
            steps = rng.randint(*steps_tier[tier-1])  # how many interior bends
            pts = [(x0, y_start)]
            # walk outward in steps (hard angles)
            for s in range(steps):
                # progress toward y_end
                t = (s + 1) / (steps + 1)
                y = y_start + t * (y_end - y_start)
                x = x0 + rng.randint(-jitter_x, jitter_x)
                pts.append((x, y))
            pts.append((x0 + rng.randint(-jitter_x, jitter_x), y_end))
            paths.append({"pts": pts})
    else:
        # left/right => x varies to edge, y spans safe edge
        x_start = safe_min if side == "left" else safe_max
        x_end   = 0 if side == "left" else canvas
        slots = [safe_min + (i + 0.5) * (safe / (rays + 0.0)) for i in range(rays)]
        for y0 in slots:
            steps = rng.randint(*steps_tier[tier-1])
            pts = [(x_start, y0)]
            for s in range(steps):
                t = (s + 1) / (steps + 1)
                x = x_start + t * (x_end - x_start)
                y = y0 + rng.randint(-jitter_y, jitter_y)
                pts.append((x, y))
            pts.append((x_end, y0 + rng.randint(-jitter_y, jitter_y)))
            paths.append({"pts": pts})

    return paths

def _gen_cross_links(side: str, paths: list, rng: random.Random, link_prob=0.0, max_links=6):
    """
    Create short cross links between nearby rays within the bleed.
    Returns: list of segments [{'a':(x1,y1),'b':(x2,y2)}]
    """
    links = []
    n = len(paths)
    if n < 2:
        return links
    # try between adjacent rays
    attempts = 0
    while len(links) < max_links and attempts < max_links * 4:
        i = rng.randrange(0, n-1)
        p1 = paths[i]["pts"]
        p2 = paths[i+1]["pts"]
        # pick a step index (skip endpoints to avoid the frame)
        if len(p1) > 2 and len(p2) > 2 and rng.random() < link_prob:
            k = rng.randrange(1, min(len(p1), len(p2)))
            a = p1[k]
            b = p2[k]
            # slight jitter so lines aren’t parallel/perfect
            ax, ay = a[0] + rng.randint(-6, 6), a[1] + rng.randint(-6, 6)
            bx, by = b[0] + rng.randint(-6, 6), b[1] + rng.randint(-6, 6)
            links.append({"a": (ax, ay), "b": (bx, by)})
        attempts += 1
    return links

def generate_spiderweb_geometry(card_dict: dict) -> dict:
    """
    Deterministic (seeded) geometry from card data.
    Only used for Creatures (but you can reuse for others).
    Returns:
      {
        'top':    {'rays': [ {'pts':[(x,y),...]}, ... ], 'links': [ {'a':(x,y),'b':(x,y)}, ... ]},
        'bottom': {...},
        'left':   {...},
        'right':  {...}
      }
    """
    tier = int(card_dict.get("Tier", 1))
    # Create a stable seed so the same card always draws the same web
    seed_src = f"web::{card_dict.get('Type')}::{card_dict.get('Name')}::{card_dict.get('Faction','')}::{card_dict.get('Background','')}::{tier}"
    rng = _rng_from_seed(seed_src)

    geom = {}
    for side in ("top", "bottom", "left", "right"):
        rays = _gen_spider_side(side, tier, rng)
        links = _gen_cross_links(side, rays, rng)
        geom[side] = {"rays": rays, "links": links}
    return geom

def load_schema(project_root: Path, rel_path: str) -> dict:
    with open(project_root / rel_path, "r", encoding="utf-8") as f:
        return json.load(f)


def detect_type(card_data: dict, project_root: Path) -> str:
    """
    Prefer explicit card_data['Type'] (case-insensitive).
    Validate against its schema. If missing/invalid, fall back to trying all schemas.
    """
    explicit = card_data.get("Type")
    if isinstance(explicit, str):
        key = explicit.strip().lower()
        if key not in SCHEMA_PATHS:
            raise ValueError(
                f"Type '{explicit}' not registered. Known types: {', '.join(sorted(SCHEMA_PATHS.keys()))}"
            )
        schema = load_schema(project_root, SCHEMA_PATHS[key])
        try:
            js_validate(instance=card_data, schema=schema)
            print(f"[TYPE] Detected via field: {key}")
            return key
        except ValidationError as e:
            # Show the exact reason so it’s easy to fix
            raise ValueError(
                f"JSON failed schema validation for type '{explicit}': {e.message}"
            ) from e

    # Fallback: try all schemas in registry (also case-insensitive names)
    errors = []
    for card_type, schema_rel in SCHEMA_PATHS.items():
        schema = load_schema(project_root, schema_rel)
        try:
            js_validate(instance=card_data, schema=schema)
            print(f"[TYPE] Detected via schemas: {card_type}")
            return card_type
        except ValidationError as e:
            errors.append((card_type, e.message))

    details = "; ".join([f"{t}: {msg}" for t, msg in errors[:3]])  # avoid wall of text
    raise ValueError(f"Could not detect card type: JSON did not match any known schema. Hints: {details}")

def write_preview_grid(batch_dir: str, items: list, title: str = "Card Preview") -> str:
    """
    Render templates/preview_grid.html into <batch_dir>/preview.html
    using the collected items metadata.
    """
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    tpl = env.get_template("preview_grid.html")

    html = tpl.render(title=title, items=items)

    out_path = os.path.join(batch_dir, "preview.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[PREVIEW] Wrote grid: {out_path}")
    return out_path

# =========================
# Transform / normalize
# =========================
def transform_context(card_data: dict, card_type: str) -> dict:
    """
    Normalize raw JSON into the context templates expect.
    Common fixes + per-type tweaks go here.
    """
    data = dict(card_data)

    # Normalize Roads to a lowercase set for easy checks in templates
    roads = data.get("Roads", [])
    if isinstance(roads, list):
        data["RoadsSet"] = {str(r).strip().lower() for r in roads}
    else:
        data["RoadsSet"] = set()

    # Replace tokens with inline icons in Rules and Description (as applicable)
    if isinstance(data.get("Rules"), str):
        data["Rules"] = replace_symbols_in_rules(data["Rules"])
    if isinstance(data.get("Description"), str):
        data["Description"] = replace_symbols_in_rules(data["Description"])

    return data


# =========================
# Single-card pipeline
# =========================
def generate_html(card_data_path: str, _templates_dir_unused: str, output_dir: str):
    with open(card_data_path, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    project_root = Path(__file__).resolve().parent
    validate_assets(project_root)

    # 1) Detect & validate type on the RAW data (no extras yet!)
    detected_type = detect_type(raw, project_root)
    template_filename = TYPE_TO_TEMPLATE_FILE[detected_type]
    subtype = (raw.get("Subtype") or "").strip().lower()
    if detected_type == "room" and subtype == "hearth":
        template_filename = "room_hearth_template.html"
    size_key = TYPE_TO_SIZE[detected_type]

    # 2) Now enrich AFTER validation
    #    Embed background if file path provided (optional)
    enriched = dict(raw)
    bg_path = enriched.get("Background")
    if bg_path and os.path.exists(bg_path):
        with open(bg_path, 'rb') as img_file:
            enriched['background_b64'] = base64.b64encode(img_file.read()).decode('utf-8')
    else:
        enriched['background_b64'] = None

    # 3) Transform context (adds RoadsSet, runs inline replacements, etc.)
    ctx = transform_context(enriched, detected_type)
    if detected_type in ("creature", "hero"):
        ctx["Spiderweb"] = generate_spiderweb_geometry(ctx)
    base_href = project_root.as_uri() + "/"
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template(template_filename)
    rendered_html = template.render(**ctx, base_href=base_href)

    os.makedirs(output_dir, exist_ok=True)
    safe_name = re.sub(r'[^A-Za-z0-9_-]', '_', ctx.get('Name', 'card'))
    html_path = os.path.join(output_dir, f"{safe_name}.html")
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(rendered_html)

    print(f"[HTML] Generated: {html_path}")
    return html_path, safe_name, size_key



def generate_png_from_html(html_path: str, output_dir: str, output_name: str, size_key: str):
    """Generate full-bleed PNG from HTML using Playwright (Chromium)."""
    width, height = SIZE_PROFILES[size_key]["bleed"]
    os.makedirs(output_dir, exist_ok=True)
    png_path = os.path.join(output_dir, f"{output_name}.png")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height})
        page.goto(f"file://{os.path.abspath(html_path)}", wait_until="networkidle")
        try:
            page.wait_for_load_state("networkidle")
        except:
            pass
        page.screenshot(path=png_path, clip={"x": 0, "y": 0, "width": width, "height": height})
        browser.close()

    print(f"[PNG] Full bleed generated: {png_path}")
    return png_path


def generate_safezone_png(full_png_path: str, output_dir: str, output_name: str, size_key: str):
    """Crop the safe zone from a full-bleed PNG (saves as *_safe.png at 300 DPI)."""
    left, top, right, bottom = SIZE_PROFILES[size_key]["crop"]
    os.makedirs(output_dir, exist_ok=True)
    safe_png_path = os.path.join(output_dir, f"{output_name}_safe.png")

    with Image.open(full_png_path) as im:
        cropped = im.crop((left, top, right, bottom))
        if cropped.mode not in ("RGB", "RGBA"):
            cropped = cropped.convert("RGBA")
        cropped.save(safe_png_path, format="PNG", dpi=(300, 300))

    print(f"[PNG] Safe zone generated: {safe_png_path}")
    return safe_png_path


def generate_trim_png(full_png_path: str, output_dir: str, output_name: str, size_key: str):
    """
    Crop the TRIM area (no bleed; not the smaller safe-zone) from a full-bleed PNG.
    Saves as *_trim.png at 300 DPI.
    """
    if "trim" not in SIZE_PROFILES[size_key]:
        raise ValueError(f"No trim bounds defined for size profile '{size_key}'.")

    left, top, right, bottom = SIZE_PROFILES[size_key]["trim"]
    os.makedirs(output_dir, exist_ok=True)
    trim_png_path = os.path.join(output_dir, f"{output_name}_trim.png")

    with Image.open(full_png_path) as im:
        trimmed = im.crop((left, top, right, bottom))
        if trimmed.mode not in ("RGB", "RGBA"):
            trimmed = trimmed.convert("RGBA")
        trimmed.save(trim_png_path, format="PNG", dpi=(300, 300))

    print(f"[PNG] Trim area generated: {trim_png_path}")
    return trim_png_path
# =========================
# Batch helpers
# =========================
def list_json_files(folder_path: str):
    p = Path(folder_path)
    return sorted([str(fp) for fp in p.glob("*.json")])


def make_batch_dir(base_output_dir: str, count: int) -> str:
    ts = int(time.time())
    batch_name = f"{ts}_{count}"
    batch_dir = os.path.join(base_output_dir, batch_name)
    os.makedirs(batch_dir, exist_ok=True)
    return batch_dir


def process_single(json_path: str, _templates_dir_ignored: str, out_dir: str,
                   want_html: bool, want_png: bool, want_safe: bool, want_trim: bool):
    html_path = None
    safe_name = None
    full_png_path = None
    size_key = None

    if want_html or want_png or want_safe or want_trim:
        html_path, safe_name, size_key = generate_html(json_path, _templates_dir_ignored, out_dir)

    if want_png or want_safe or want_trim:
        full_png_path = generate_png_from_html(html_path, out_dir, safe_name, size_key)

    safe_png_path = None
    if want_safe:
        if not full_png_path:
            full_png_path = os.path.join(out_dir, f"{safe_name}.png")
        safe_png_path = generate_safezone_png(full_png_path, out_dir, safe_name, size_key)

    trim_png_path = None
    if want_trim:
        if not full_png_path:
            full_png_path = os.path.join(out_dir, f"{safe_name}.png")
        trim_png_path = generate_trim_png(full_png_path, out_dir, safe_name, size_key)

    # labels
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            j = json.load(f)
        typ = str(j.get("Type", "")).strip()
        name = str(j.get("Name", "")).strip()
        subtype = str(j.get("Subtype", "")).strip()
        faction = str(j.get("Faction", "")).strip()

        # unified subgroup key for preview
        t_lower = typ.lower()
        if t_lower == "room":
            subgroup = subtype
        elif t_lower == "creature":
            subgroup = faction
        else:
            subgroup = ""

    except Exception:
        typ, name, subtype = "", safe_name or "card", ""


    # relpaths from batch dir
    rel_html = os.path.relpath(html_path, out_dir) if html_path else None
    rel_png  = os.path.relpath(full_png_path, out_dir) if full_png_path else None
    rel_safe = os.path.relpath(safe_png_path, out_dir) if safe_png_path else None
    rel_trim = os.path.relpath(trim_png_path, out_dir) if trim_png_path else None
    rel_json = os.path.relpath(json_path, out_dir)

    return {
        "type": typ,
        "name": name,
        "html": rel_html,
        "png": rel_png,
        "safe_png": rel_safe,
        "trim_png": rel_trim,   # <— NEW
        "json": rel_json,
        "subtype": subtype,     # keep original fields (optional)
        "faction": faction,     # "
        "subgroup": subgroup,   # <-- use this for grouping

    }



# =========================
# CLI
# =========================
def parse_args():
    ap = argparse.ArgumentParser(description="Generate boardgame card HTML/PNG with schema-based type detection.")
    ap.add_argument("--input", "-i", default="card_data.json",
                    help="Path to a .json file OR a folder with multiple JSON files")
    ap.add_argument("--template-dir", "-t", default="templates",
                    help="(Ignored) kept for backward compatibility")
    ap.add_argument("--output-dir", "-o", default="output", help="Output directory")

    ap.add_argument("--html", action="store_true", help="Generate HTML only")
    ap.add_argument("--png", action="store_true", help="Generate full-bleed PNG")
    ap.add_argument("--safe", action="store_true", help="Generate cropped safe-zone PNG")
    ap.add_argument("--trim", action="store_true", help="Generate cropped TRIM-area PNG (no bleed)")
    ap.add_argument("--all", action="store_true", help="Generate HTML + full PNG + safe PNG")

    return ap.parse_args()


def main():
    args = parse_args()

    # default to --all if nothing specified
    if not (args.trim or args.html or args.png or args.safe or args.all):
        args.all = True

    want_html = args.html or args.all
    want_png  = args.png  or args.all
    want_safe = args.safe or args.all
    want_trim = args.trim or args.all

    if os.path.isdir(args.input):
        json_files = list_json_files(args.input)
        if not json_files:
            raise SystemExit(f"No .json files found in folder: {args.input}")

        batch_dir = make_batch_dir(args.output_dir, len(json_files))
        print(f"[BATCH] Processing {len(json_files)} file(s) → {batch_dir}")

        items = []
        for jp in json_files:
            item = process_single(jp, args.template_dir, batch_dir, want_html, want_png, want_safe,want_trim)
            items.append(item)

        # Build preview grid
        write_preview_grid(batch_dir, items, title="Card Type Preview")

        print("[BATCH] Done.")

    else:
        # single file mode → write directly to output_dir
        process_single(args.input, args.template_dir, args.output_dir, want_html, want_png, want_safe,want_trim)


if __name__ == "__main__":
    main()
