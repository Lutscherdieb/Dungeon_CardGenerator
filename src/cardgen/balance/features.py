"""What a card costs, and what it gives -- both read off the card's own schema.

Nothing here lists field names. The generated JSON Schema says which properties
are integers, which are lists, and which are costs (``x-cost``, set on the model),
so a field added to ``cardgen.model`` becomes a balance feature on its own. That
is the same rule the gallery's form builder and filter panel follow, and it is
the reason this module did not need editing when Hero gained Treasure.

Two features are NOT card fields, because the thing they stand for is written in
prose and the stats cannot see it:

``has_ability``
    Whether the card prints any rules text at all. A Tier 1 Creature with an
    ability is not the same purchase as one without, and the difference is
    invisible to every numeric column.

``activation_cost``
    How many resource or creature-type tokens appear before the first ``:`` in
    the Description. Rules/Rules.txt:34 -- "Costs are defined in front of a ':'
    within the description of a card" -- so this is a real, countable second
    cost that the Mana/Cards/Food columns do not include.

Neither is a good proxy for how STRONG an ability is. That is the fit's
structural blind spot, and it is why every finding goes to a human who reads the
card text before ruling on it.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence, Tuple

#: Tokens that can appear as a cost in front of a ':' in a Description.
_TOKEN = re.compile(r"\[([A-Za-z]+)\]")


def cost_keys(schema: Dict[str, Any]) -> List[str]:
    """The properties marked ``x-cost`` in the card's schema, in schema order."""
    props = schema.get("properties", {})
    return [k for k in _ordered(schema) if props.get(k, {}).get("x-cost")]


def feature_keys(schema: Dict[str, Any]) -> List[str]:
    """Every property that describes what the card DOES, as a feature name.

    Integers become themselves; lists become a count. Costs, strings and the
    discriminating ``Type`` constant are excluded -- a cost is the target, and a
    string is not a number.
    """
    props = schema.get("properties", {})
    names = []
    for key in _ordered(schema):
        spec = props.get(key, {})
        if spec.get("x-cost") or spec.get("const") is not None:
            continue
        resolved = _deref(schema, spec)
        if resolved.get("type") == "integer":
            names.append(key)
        elif resolved.get("type") == "array":
            names.append("{}#".format(key))
        elif resolved.get("type") == "boolean":
            names.append(key)
        elif resolved.get("enum"):
            continue      # a category, not a magnitude; grouping handles Type
    return names + ["has_ability", "activation_cost"]


def cost_of(card: Dict[str, Any], schema: Dict[str, Any],
            weights: Dict[str, float]) -> float:
    """Total build cost: every ``x-cost`` field, times its resource weight."""
    return sum(float(card.get(key) or 0) * float(weights.get(key, 1.0))
               for key in cost_keys(schema))


def features_of(card: Dict[str, Any], names: Sequence[str]) -> List[float]:
    """The feature vector for a card, in the order `names` gives."""
    return [_feature(card, name) for name in names]


def activation_cost(description: str) -> int:
    """How many [Token]s sit in front of the first ':' in the card's text."""
    text = description or ""
    head, sep, _ = text.partition(":")
    if not sep:
        return 0
    # A colon far into the text is prose, not a cost line.
    if len(head) > 60:
        return 0
    return len(_TOKEN.findall(head))


def _feature(card: Dict[str, Any], name: str) -> float:
    if name == "has_ability":
        return 1.0 if (card.get("Description") or "").strip() else 0.0
    if name == "activation_cost":
        return float(activation_cost(card.get("Description") or ""))
    if name.endswith("#"):
        return float(len(card.get(name[:-1]) or []))
    value = card.get(name)
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    return float(value or 0)


def drop_constant(names: Sequence[str],
                  rows: Sequence[Sequence[float]]) -> Tuple[List[str], List[List[float]]]:
    """Remove features that never vary in this group.

    A column of identical values carries no information and makes the normal
    equations singular; keeping it would report a weight for something the data
    says nothing about. Every Room has the same Tier (none), for instance.
    """
    if not rows:
        return list(names), [list(r) for r in rows]
    keep = [j for j in range(len(names)) if len({row[j] for row in rows}) > 1]
    return [names[j] for j in keep], [[row[j] for j in keep] for row in rows]


def _ordered(schema: Dict[str, Any]) -> List[str]:
    order = schema.get("x-key-order")
    return list(order) if order else list(schema.get("properties", {}))


def _deref(schema: Dict[str, Any], node: Dict[str, Any]) -> Dict[str, Any]:
    ref = node.get("$ref")
    if not ref:
        return node
    return schema.get("$defs", {}).get(ref.replace("#/$defs/", ""), node)
