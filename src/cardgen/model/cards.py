"""The card definition -- one model, from which the schemas and the DB derive.

Why this module exists
----------------------
The shape of a card was previously written down three times: eight hand-kept
JSON Schemas in ``schemas/``, the Jinja context each template happens to expect,
and a SQLAlchemy model on the abandoned REST branch.  They had already drifted:
``Type`` was required by five schemas and optional in three, ``additionalProperties``
was ``false`` in four and ``true`` in four, and the two splits did not line up.
``Food`` was declared in all eight and used by one card out of 137.

One model now owns the shape.  ``schemas.py`` emits the JSON Schemas from it and
the store derives its columns from it, so a field cannot exist in one place and
not another.

Field naming
------------
Python attributes are snake_case; every one carries a capitalised alias matching
the JSON and the Jinja context (``Name``, ``Defence``, ``Roads``).  The alias is
generated, not listed -- every field name is a single lowercase word, so
``str.capitalize`` is the whole rule.  ``model_dump(by_alias=True)`` therefore
produces exactly the dict the templates already read.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, List, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


def _json_alias(field_name: str) -> str:
    """JSON keys are the field name capitalised. Derived, never enumerated."""
    return field_name.capitalize()


class CreatureType(str, Enum):
    """The game's creature types, plus the wildcard.

    A closed set defined by the game itself (Rules/Rules.txt, "Basic Creature
    Type Boons"), not by anything in this repo -- so it is enumerated here on
    purpose rather than derived from the asset directory, which also holds
    resource and stat icons.
    """

    DEMON = "Demon"
    UNDEAD = "Undead"
    MAGIC = "Magic"
    WILD = "Wild"
    ALL = "All"


class Direction(str, Enum):
    """Room exits. Order matters for rendering; the data is already NESW-sorted."""

    N = "N"
    E = "E"
    S = "S"
    W = "W"


class RoomSubtype(str, Enum):
    BASIC = "Basic"
    HEARTH = "Hearth"


Tier = Annotated[int, Field(ge=1, le=4)]

#: How much treasure a card carries: on a Room, what it holds; on a Hero, what
#: it drops as loot when slain. One definition used by both, so the two cannot
#: drift apart.
#:
#: NOT named ``Treasure`` -- that is already the name of a card type class in
#: this module, and with ``from __future__ import annotations`` the shadowing
#: would only surface if pydantic ever re-resolved the annotation.
TreasureCount = Annotated[int, Field(default=0, ge=0)]


class CardBase(BaseModel):
    """Fields every card type carries."""

    model_config = ConfigDict(
        alias_generator=_json_alias,
        populate_by_name=True,
        extra="forbid",
        use_enum_values=False,
    )

    name: str = Field(min_length=1)

    #: The three resources a card costs to play or build.
    #:
    #: ``x-cost`` marks them in the generated JSON Schema, which is what lets
    #: cardgen.balance separate "what this card costs" from "what it does"
    #: without keeping its own list of field names -- the same derive-rather-
    #: than-enumerate rule the gallery's form and filter panel follow.
    mana: int = Field(ge=0, json_schema_extra={"x-cost": True})
    cards: int = Field(ge=0, json_schema_extra={"x-cost": True})

    #: Kept in 2026-08-24 although only one card used it then. Vindicated on
    #: 2026-08-29: the author rebalanced Mana into Food across the deck and it
    #: is now a live cost on 78 of 137 cards.
    food: int = Field(default=0, ge=0, json_schema_extra={"x-cost": True})

    #: The card's printed rules text. Rooms used to call this field "Rules" and
    #: the other seven types "Description"; unified on the game's own word --
    #: Rules/Rules.txt:34 says "Costs are defined in front of a ':' within the
    #: description of a card."
    description: str = ""

    #: Ships in the starting deck. Printed as a small corner stamp so a starter
    #: card is recognisable at a glance without dominating the face.
    #:
    #: On CardBase rather than on the deck-buildable types alone: the flag is
    #: derived into every schema, form and filter from here, so a ninth card
    #: type cannot be added and forget it.
    starter: bool = False


#: Defence is deliberately unbounded. It reads as a modifier as well as a stat --
#: Shark_Tank is a Room with Defence -1 -- and a ``ge=0`` guess here rejected that
#: card outright. Bound a field only where the data shows the bound, or where a
#: negative is meaningless (health, movement, tier, and the cost fields).
Defence = int


class _Fighter(CardBase):
    """Shared stat block for the types that occupy the board and fight."""

    defence: Defence
    movement: int = Field(ge=0)
    health: int = Field(ge=0)


class Creature(_Fighter):
    type: Literal["Creature"]
    faction: CreatureType
    tier: Tier


class Hero(_Fighter):
    type: Literal["Hero"]
    tier: Tier
    #: How many Treasures this hero drops as loot when slain.
    treasure: TreasureCount


class Overlord(_Fighter):
    type: Literal["Overlord"]
    #: The Overlord's starting creature pool -- 8 or 9 entries in current data.
    creatures: List[CreatureType] = Field(default_factory=list)


class Room(CardBase):
    type: Literal["Room"]
    subtype: RoomSubtype
    defence: Defence
    #: How much treasure this room holds.
    treasure: TreasureCount
    roads: List[Direction] = Field(default_factory=list)
    #: One entry per creature spot the room offers, in print order.
    #:
    #: Was List[List[Tuple[CreatureType, int]]] until 2026-08-29 -- groups of
    #: (type, number) pairs. The grouping was layout, not data (the third group
    #: was empty on all 23 rooms), and the number was 0 on every spot in the
    #: store once the author cleared the two Sacred Hain exceptions. Both were
    #: dropped; see tools/migrate_20260829_flatten_slots_add_starter_treasure.py.
    slots: List[CreatureType] = Field(default_factory=list)


class _TieredSpellLike(CardBase):
    """Types that are just text plus a tier: Spell, Trap, Research, Treasure."""

    tier: Tier


class Spell(_TieredSpellLike):
    type: Literal["Spell"]


class Trap(_TieredSpellLike):
    type: Literal["Trap"]


class Research(_TieredSpellLike):
    type: Literal["Research"]


class Treasure(_TieredSpellLike):
    type: Literal["Treasure"]


Card = Annotated[
    Union[Creature, Hero, Overlord, Room, Spell, Trap, Research, Treasure],
    Field(discriminator="type"),
]

#: Every concrete card class, keyed by the lowercase type name. Derived from the
#: union so a new type cannot be added to one and forgotten in the other.
CARD_TYPES = {
    m.model_fields["type"].annotation.__args__[0].lower(): m
    for m in Card.__origin__.__args__  # type: ignore[attr-defined]
}


def card_type_names() -> "list[str]":
    """Lowercase names of every registered card type."""
    return sorted(CARD_TYPES)


def model_for_type(card_type: str):
    """The model class for a card type name, case-insensitively."""
    key = (card_type or "").strip().lower()
    try:
        return CARD_TYPES[key]
    except KeyError:
        raise ValueError(
            "unknown card type {!r}; known: {}".format(card_type, ", ".join(card_type_names()))
        ) from None


def parse_card(data: dict):
    """Validate a raw card dict (JSON key spelling) into its concrete model.

    Interchange-only keys are dropped first, so a card JSON file straight off
    disk validates without the caller having to know which keys are transport.
    """
    card, _ = split_transport(data)
    model = model_for_type(card.get("Type") or card.get("type") or "")
    return model.model_validate(card)


#: Keys that appear in card JSON files but are NOT part of the card.
#:
#: Artwork belongs to the card in the store, as bytes -- not as a path a human
#: has to keep pointing at the right file. "Background" survives only as an
#: interchange detail: import reads it to find the image to load, export writes
#: the image out and emits it again, so the JSON files stay a complete,
#: git-diffable copy of the deck. Nothing at render time consults it.
TRANSPORT_KEYS = ("Background",)


def split_transport(data: dict) -> "tuple[dict, dict]":
    """Separate a card JSON file into (card fields, interchange-only fields)."""
    transport = {k: data[k] for k in TRANSPORT_KEYS if k in data}
    card = {k: v for k, v in data.items() if k not in transport}
    return card, transport


#: Key order for exported JSON. Not cosmetic: cards are hand-edited, and the
#: order below is the one the author already writes -- measured across the deck,
#: where 46 of 47 Creatures, 13 of 13 Heroes and 23 of 23 Rooms agree. Matching
#: it keeps `export the store over data/Mixed && git diff` a usable integrity
#: check instead of a wall of reordering. A key missing from this tuple is not
#: dropped, it sorts to the end.
_JSON_KEY_ORDER = (
    "Type", "Subtype", "Name", "Faction", "Tier", "Starter",
    "Description",
    "Mana", "Cards", "Food",
    "Defence", "Treasure", "Movement", "Health",
    "Creatures", "Roads", "Slots",
    "Background",
)
_ORDER_INDEX = {key: i for i, key in enumerate(_JSON_KEY_ORDER)}


def to_json_dict(card: BaseModel) -> dict:
    """The card as the JSON files and the Jinja templates spell it."""
    dumped = card.model_dump(by_alias=True, mode="json")
    return {
        key: dumped[key]
        for key in sorted(dumped, key=lambda k: (_ORDER_INDEX.get(k, len(_ORDER_INDEX)), k))
    }
