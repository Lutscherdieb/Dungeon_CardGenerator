# Card Generator

This project generates print-ready boardgame cards from JSON definitions, using HTML/CSS templates and Playwright for PNG rendering.

---

## 📦 Requirements

- Python 3.9 or newer
- Pip (comes with Python)
- Chromium installed by Playwright (see below)

---

## 🔧 Installation

Clone or copy the project, then install Python dependencies:

```bash
pip install -r requirements.txt
```
Install Chromium for Playwright:
```bash
python -m playwright install chromium
```

## Project Structure

```bash
project-root/
├── generate_card.py          # main generator script
├── style.css                 # global styles (shared across all card types)
├── assets/                   # icons, faction symbols, filters.svg, etc.
│   ├── demon.png
│   ├── undead.png
│   ├── wild.png
│   ├── magic.png
│   ├── all.png
│   ├── mana.png
│   ├── cards.png
│   ├── defence.png
│   ├── treasure.png
│   ├── movement.png
│   └── filters.svg
├── templates/                # all *_template.html files (per type)
│   ├── room_template.html
│   ├── spell_template.html
│   ├── hero_template.html
│   ├── creature_template.html
│   ├── research_template.html
│   ├── treasure_template.html
│   ├── overlord_template.html
│   └── trap_template.html
├── schemas/                  # JSON schema definitions
│   ├── room.schema.json
│   ├── spell.schema.json
│   ├── hero.schema.json
│   ├── creature.schema.json
│   ├── research.schema.json
│   ├── treasure.schema.json
│   ├── overlord.schema.json
│   └── trap.schema.json
├── backgrounds/              # per-card artwork
│   ├── Sanctuary.png
│   ├── Black_Emperor.png
│   └── ...
└── outputs/                  # auto-created, stores results
    └── 1754698284_45/        # timestamped folder with batch output
```

## Usage

Generate a batch of cards 
```bash
python generate_card.py data/mixed
```
Generate a single of card 
```bash
python generate_card.py data/mixed/Bear.json
```

Each run creates a timestamped output folder in outputs/, e.g.:
```bash
outputs/1754698284_45/
├── Bear.html
├── Bear.png
├── Bear_safezone.png
└── ...
```
Here 1754698284 is the UNIX timestamp, and 45 is the number of cards generated.

## Features

**Type detection** → JSON validated via per-type schema

**Multiple card types** → Room, Spell, Hero, Creature, Treasure, Trap, Overlord, Research

**Subtype support** → e.g. Room - Hearth

**Per-type + per-faction themes** → configurable via style.css with CSS variables

**Safe-zone, bleed, and crop handling** → ensures cards are print-ready at 300 DPI

**Inline icon replacement** → [Demon][Mana] in text auto-converts to <img> icons

**Preview grid** → preview.html shows all generated cards, grouped by type/subtype

**Batch subfolders** → every run gets its own unique output folder

## Notes
**Backgrounds**: 1122×1122 px @ 300 DPI (print-ready).

**Safe-zone**: 975×975 px.

**Bleed**: 75 px around the safe-zone.

**Slot icons**: 10 mm ≈ 118 px.

**Costs-box**: auto-shows if Mana > 0 or Cards > 0.

**Inline symbols**: scale with text size (using em units).

## Adding a new card type
1. Create a schema in schemas/ (e.g. mytype.schema.json).

2. Create a template in templates/ (e.g. mytype_template.html).

3. Add it to the Python mappings in generate_card.py:
```bash
TYPE_TO_TEMPLATE_FILE["mytype"] = "mytype_template.html"
SCHEMA_PATHS["mytype"] = "schemas/mytype.schema.json"
```
4. Add a theme block in style.css:
```bash
body[data-type="mytype"] {
  --frame-background: rgba(20, 20, 40, 0.65);
  --frame-border-color: #4a4aff;
  --frame-text-color: #fff;
  --slot-text-color: #fff;
}
```
```bash
{
  "Type": "MyType",
  "Name": "Example Card",
  "Description": "Custom rules [Demon][Wild]",
  "Mana": 2,
  "Cards": 1,
  "Background": "./backgrounds/example.png"
}
```
Create an example JSON:
## Quickstart Summary
```bash
git clone <your-repo>
cd project-root
pip install -r requirements.txt
python -m playwright install chromium

# Generate cards from data/mixed
python generate_card.py data/mixed
```
Result: print-ready .png and .html files in outputs/<timestamp>_<count>/.