import os, datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import sync_playwright
from api.settings import Settings
from api.services.inline_icons import replace_inline_symbols
from api.services.spiderweb import generate_spiderweb_geometry

s = Settings()
env = Environment(loader=FileSystemLoader(s.templates_dir), autoescape=select_autoescape(['html']))

def render_card_to_disk(card) -> dict:
    # Build Jinja context from Card model
    ctx = {
        "Type": (card.type or "").capitalize(),
        "Subtype": card.subtype or "",
        "Name": card.name or "",
        "Faction": card.faction or "",
        "Tier": card.tier or 1,
        "Mana": card.mana or 0,
        "Cards": card.cards or 0,
        "Food": card.food or 0,
        "Defence": card.defence,
        "Health": card.health,
        "Movement": card.movement,
        "Treasure": card.treasure,
        "Roads": card.roads or [],
        "Slots": card.slots or [],
        "Background": card.background or "",
        "Rules": replace_inline_symbols(card.rules or ""),
        "Description": replace_inline_symbols(card.description or ""),
        "base_href": "/"  # resolve assets from project root
    }
    if card.type in ("creature","hero","treasure","research","spell","trap"):
        ctx["Spiderweb"] = generate_spiderweb_geometry({
            "Type": card.type, "Name": card.name, "Faction": card.faction or "",
            "Background": card.background or "", "Tier": card.tier or 1
        })

    template_file = f"{(card.type or 'room').lower()}_template.html"
    tpl = env.get_template(template_file)
    html = tpl.render(**ctx)

    stamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(s.outputs_dir, stamp)
    os.makedirs(out_dir, exist_ok=True)

    html_path = os.path.join(out_dir, f"{card.id}_{card.type}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    png_path = os.path.join(out_dir, f"{card.id}_{card.type}.png")

    # Render to PNG
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width":1125, "height":1125, "deviceScaleFactor":1})
        page.goto("file://" + html_path)
        page.wait_for_load_state("networkidle")
        page.screenshot(path=png_path)
        browser.close()

    return {"html": html_path, "png": png_path}
