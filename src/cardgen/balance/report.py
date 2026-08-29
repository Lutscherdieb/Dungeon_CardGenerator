"""Fit a cost model per card type and report the cards that do not fit it.

The claim this module makes is narrow and worth stating plainly: **a card's
printed cost should be predictable from its printed numbers, and one that is not
deserves a look.** It does not know what an ability is worth, what the metagame
is, or what the designer intended. Every finding is a question, not a verdict --
which is why the skill that drives this puts each one to the author and records
the answer.

Every group therefore reports ``n`` and ``r2`` beside its findings. A fit over
ten Treasures explaining 30% of the variance is a weak instrument, and saying so
is the difference between evidence and a confident-sounding number.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .config import DEFAULTS
from .features import cost_keys, cost_of, drop_constant, feature_keys, features_of
from .linear import r_squared, ridge_fit, stdev

#: A group smaller than this cannot support a fit at all.
MIN_GROUP = 5


def fit_group(cards: Sequence[Dict[str, Any]], schema: Dict[str, Any],
              config: Dict[str, Any]) -> Dict[str, Any]:
    """Fit one card type. Returns the model plus a residual per card.

    ``cards`` are raw card dicts in JSON key spelling, all of one type.
    """
    weights_cfg = config.get("weights", {})
    ignore = set(config.get("ignore_features", {}).get(_type_of(cards), []))
    pinned = {k: float(v) for k, v in weights_cfg.get(_type_of(cards), {}).items()}

    names = [n for n in feature_keys(schema) if n not in ignore]
    rows = [features_of(card, names) for card in cards]
    names, rows = drop_constant(names, rows)

    costs = [cost_of(card, schema, config.get("cost_weights", {})) for card in cards]

    # An author-pinned weight is held fixed: its contribution comes out of the
    # target and the remaining features are fitted against what is left. That
    # makes "I say Health is worth 0.5" a statement the fit obeys rather than
    # argues with.
    free = [j for j, name in enumerate(names) if name not in pinned]
    residual_target = [
        costs[i] - sum(pinned[names[j]] * rows[i][j]
                       for j in range(len(names)) if names[j] in pinned)
        for i in range(len(cards))
    ]
    free_rows = [[row[j] for j in free] for row in rows]

    note = None
    if len(cards) < MIN_GROUP:
        note = "only {} cards -- too few to fit; costs are listed, not judged".format(len(cards))
        fitted, intercept = [0.0] * len(free), (
            sum(residual_target) / len(cards) if cards else 0.0)
    else:
        if len(cards) < len(free) + 3:
            note = ("{} cards against {} features -- the fit is underdetermined, "
                    "read the weights as a hint".format(len(cards), len(free)))
        fitted, intercept = ridge_fit(free_rows, residual_target)

    weights = dict(pinned)
    for slot, j in enumerate(free):
        weights[names[j]] = fitted[slot]

    predicted = [
        intercept + sum(weights[names[j]] * rows[i][j] for j in range(len(names)))
        for i in range(len(cards))
    ]
    residuals = [costs[i] - predicted[i] for i in range(len(cards))]

    return {
        "type": _type_of(cards),
        "n": len(cards),
        "features": names,
        "weights": {name: round(weights[name], 3) for name in names},
        "pinned": sorted(pinned),
        "intercept": round(intercept, 3),
        "r2": round(r_squared(costs, predicted), 3),
        "residual_sigma": round(stdev(residuals), 3),
        "cost_fields": cost_keys(schema),
        "cost_weights": {k: float(config.get("cost_weights", {}).get(k, 1.0))
                         for k in cost_keys(schema)},
        "note": note,
        "cards": [
            {
                "name": card.get("Name"),
                "tier": card.get("Tier"),
                "cost": round(costs[i], 2),
                "expected": round(predicted[i], 2),
                "residual": round(residuals[i], 2),
            }
            for i, card in enumerate(cards)
        ],
    }


def findings_for(group: Dict[str, Any], config: Dict[str, Any],
                 rulings: Optional[Dict[str, Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """The cards in a fitted group whose cost the model does not explain."""
    rulings = rulings or {}
    sigma = group["residual_sigma"]
    if group["n"] < MIN_GROUP or sigma <= 0:
        return []

    z_limit = float(config.get("threshold_z", DEFAULTS["threshold_z"]))
    abs_limit = float(config.get("threshold_abs", DEFAULTS["threshold_abs"]))

    out = []
    for card in group["cards"]:
        z = card["residual"] / sigma
        if abs(z) < z_limit or abs(card["residual"]) < abs_limit:
            continue
        ruling = rulings.get(card["name"])
        out.append({
            **card,
            "type": group["type"],
            "z": round(z, 2),
            "direction": "overcosted" if card["residual"] > 0 else "undercosted",
            "n": group["n"],
            "r2": group["r2"],
            "accepted": bool(ruling),
            "ruling": ruling.get("reason") if ruling else None,
        })
    out.sort(key=lambda f: -abs(f["z"]))
    return out


def analyse(cards_by_type: Dict[str, List[Dict[str, Any]]],
            schemas: Dict[str, Dict[str, Any]],
            config: Dict[str, Any],
            rulings: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Fit every card type and collect the findings."""
    groups, findings = [], []
    for card_type in sorted(cards_by_type):
        schema = schemas[card_type.lower()]
        group = fit_group(cards_by_type[card_type], schema, config)
        groups.append(group)
        findings.extend(findings_for(group, config, rulings))
    findings.sort(key=lambda f: -abs(f["z"]))
    return {"groups": groups, "findings": findings}


def render_text(result: Dict[str, Any]) -> str:
    """The human-readable report. The --json form is what the skill consumes."""
    lines = []
    for group in result["groups"]:
        # Spell out a reweighted resource: "Mana + Cards + 0.5*Food" is the
        # difference between reading the report and misreading it.
        costs = " + ".join(
            key if group["cost_weights"].get(key, 1.0) == 1.0
            else "{:g}*{}".format(group["cost_weights"][key], key)
            for key in group["cost_fields"])
        lines.append("=" * 72)
        lines.append("{}  n={}  r2={}  residual sigma={}".format(
            group["type"], group["n"], group["r2"], group["residual_sigma"]))
        lines.append("  cost = {}".format(costs))
        if group["note"]:
            lines.append("  NOTE: {}".format(group["note"]))
        lines.append("  expected cost = {}".format(_formula(group)))
        if group["pinned"]:
            lines.append("  pinned by the author: {}".format(", ".join(group["pinned"])))
        lines.append("")

    lines.append("=" * 72)
    open_findings = [f for f in result["findings"] if not f["accepted"]]
    accepted = [f for f in result["findings"] if f["accepted"]]
    lines.append("{} finding(s) to judge, {} already accepted".format(
        len(open_findings), len(accepted)))
    lines.append("")
    for f in open_findings:
        lines.append("  {:<22} {:<9} T{:<3} cost {:>5}  expected {:>6}  {:+.2f} ({:+.2f} sigma)  {}".format(
            f["name"][:22], f["type"], f["tier"] if f["tier"] else "-",
            f["cost"], f["expected"], f["residual"], f["z"], f["direction"]))
    if accepted:
        lines.append("")
        lines.append("  already ruled on (see references/rulings.md):")
        for f in accepted:
            lines.append("    {:<22} {}".format(f["name"][:22], f["ruling"] or ""))
    return "\n".join(lines)


def _formula(group: Dict[str, Any]) -> str:
    parts = ["{:.2f}".format(group["intercept"])]
    for name, weight in sorted(group["weights"].items(), key=lambda kv: -abs(kv[1])):
        if abs(weight) < 0.005:
            continue
        parts.append("{:+.2f}*{}".format(weight, name))
    return " ".join(parts)


def _type_of(cards: Sequence[Dict[str, Any]]) -> str:
    return cards[0].get("Type") if cards else ""
