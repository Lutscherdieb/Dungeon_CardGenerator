"""The ``[Token]`` codes a card's Description may use, and their icons.

One home for the list. It used to be written twice inside ``generate_card.py``
-- once as ``TOKEN_TO_ICON`` and once as a hand-typed alternation inside the
regex. The two agreed, but only by inspection: adding a token to the dict
without editing the regex would have made it silently print as literal text,
which is the kind of failure nobody reports because nothing errors.

The pattern is now derived from the dict's keys, and ``/api/meta/tokens`` serves
the same dict to the gallery, so the legend under the Description field cannot
list a code the renderer does not substitute.
"""

from __future__ import annotations

import re
from typing import Dict, List

#: Token -> icon filename under ``assets/``. The token is what the author types
#: between square brackets; matching is case- and space-insensitive.
TOKEN_TO_ICON: Dict[str, str] = {
    # creature types
    "undead": "undead.png",
    "demon": "demon.png",
    "wild": "wild.png",
    "magic": "magic.png",
    "all": "all.png",
    # resources
    "mana": "mana.png",
    "cards": "cards.png",
    "food": "food.png",
    "treasure": "treasure.png",
    "chaos": "chaos.png",
    # stats
    "defence": "defence.png",
    "health": "health.png",
    "movement": "movement.png",
    # card types
    "hero": "hero.png",
    "spell": "spell.png",
    "trap": "trap.png",
    "research": "research.png",
}


def _pattern() -> "re.Pattern[str]":
    """``[ token ]`` for every known token, case- and space-tolerant.

    Longest first so no token can be swallowed by a shorter one that happens to
    be its prefix. No token has that shape today; sorting costs nothing and
    means adding one that does cannot introduce the bug.
    """
    alternation = "|".join(re.escape(t) for t in sorted(TOKEN_TO_ICON, key=len, reverse=True))
    return re.compile(r"\[\s*(" + alternation + r")\s*\]", re.IGNORECASE)


SYMBOL_PATTERN = _pattern()


def token_list() -> List[Dict[str, str]]:
    """Every code as the gallery shows it: the text to type, and its icon."""
    return [
        {"code": "[{}]".format(token.capitalize()), "token": token, "icon": icon}
        for token, icon in TOKEN_TO_ICON.items()
    ]


def replace_symbols_in_rules(text: str) -> str:
    """Replace bracketed tokens (e.g. ``[Undead]``) with inline ``<img>`` tags.

    Works inside longer text like ``aaa[Demon]zzz``. Case and space tolerant.
    Returns the transformed HTML string; a non-string is passed straight back.
    """
    if not isinstance(text, str):
        return text

    def _sub(match: "re.Match[str]") -> str:
        key = match.group(1).lower()
        filename = TOKEN_TO_ICON.get(key)
        if not filename:
            return match.group(0)
        # Root-relative thanks to <base href="{{ base_href }}"> in the templates.
        return '<img src="assets/{}" alt="{}" class="inline-symbol icon-glow">'.format(
            filename, key.title())

    new_text, n = SYMBOL_PATTERN.subn(_sub, text)
    print("[Text] Icon replacements: {}".format(n))
    if n == 0:
        preview = text[:120].replace("\n", " ")
        print("[Text] No tokens found in: {!r}".format(preview))
    return new_text
