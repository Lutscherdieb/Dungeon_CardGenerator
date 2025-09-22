import re

# Map tokens in text → icon filenames
TOKEN_MAP = {
    "Undead": "undead.png",
    "Demon":  "demon.png",
    "Wild":   "wild.png",
    "Magic":  "magic.png",
    "All":    "all.png",
    "Mana":   "mana.png",
    "Cards":  "cards.png",
    "Hero":   "hero.png",
    "Spell":  "spell.png",
    "Food":   "food.png",
}

_pat = re.compile(r'\[(%s)\]' % '|'.join(map(re.escape, TOKEN_MAP.keys())))

def replace_inline_symbols(text: str) -> str:
    def _rep(m):
        t = m.group(1)
        return f'<img class="inline-symbol icon-glow" src="assets/{TOKEN_MAP[t]}" alt="{t}"/>'
    return _pat.sub(_rep, text or "")
