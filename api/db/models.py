# api/db/models.py
from sqlalchemy import Column, Integer, String, Text, JSON  # <-- add JSON
from api.db.base import Base

class Card(Base):
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # identity
    type = Column(String(32), nullable=False)
    subtype = Column(String(32))
    name = Column(String(200))

    # tags
    faction = Column(String(32))
    tier = Column(Integer)

    # costs / stats
    mana = Column(Integer, default=0)
    cards = Column(Integer, default=0)
    food = Column(Integer, default=0)

    defence = Column(Integer, default=0)
    health  = Column(Integer, default=0)
    movement= Column(Integer, default=0)
    treasure= Column(Integer, default=0)
    creatures = Column(JSON, nullable=True)

    # JSON columns (now!)
    roads = Column(JSON)   # e.g. ["N","S"]
    slots = Column(JSON)   # e.g. [{ "1": [["All",0]] }, ...]  OR the newer shape

    # text & media
    rules = Column(Text)
    description = Column(Text)
    background = Column(String(512))
    source_json_path = Column(String(512))
    last_png_path    = Column(String(512))

    def as_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "subtype": self.subtype,
            "name": self.name,
            "faction": self.faction,
            "tier": self.tier,
            "mana": self.mana,
            "cards": self.cards,
            "food": self.food,
            "defence": self.defence,
            "health": self.health,
            "movement": self.movement,
            "treasure": self.treasure,
            "roads": self.roads,   # already Python (list/dict) via JSON type
            "slots": self.slots,
            "rules": self.rules,
            "description": self.description,
            "background": self.background,
            "source_json_path": self.source_json_path,
            "last_png_path": self.last_png_path,
            "creatures": self.creatures,
            # optional presence flags for images
            "has_full": self.png_full is not None,
            "has_safe": self.png_safe is not None,
            "has_trim": self.png_trim is not None,
        }
