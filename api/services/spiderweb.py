# api/services/spiderweb.py
import random

CANVAS = 1125
BLEED  = 75
SAFE   = 975
BORDER = 8

def _clamp(v, lo, hi):  # simple guardrail
    return max(lo, min(hi, v))

def _classify_endpoint(pt):
    """Return which outer side an endpoint lies on."""
    x, y = pt
    if y <= 0 + 1:            return "top"
    if y >= CANVAS - 1:       return "bottom"
    if x <= 0 + 1:            return "left"
    if x >= CANVAS - 1:       return "right"
    # Fallback: pick nearest edge
    d = {
        "top":    abs(y - 0),
        "bottom": abs(y - CANVAS),
        "left":   abs(x - 0),
        "right":  abs(x - CANVAS),
    }
    return min(d, key=d.get)

def _link_within_side(side, endpoints, max_links, rng):
    """
    Build short 3-point polylines that stay inside the outer bleed band for a given side.
    - top/bottom: y stays in [0 .. BLEED) or (CANVAS-BLEED .. CANVAS]
    - left/right: x stays in [0 .. BLEED) or (CANVAS-BLEED .. CANVAS]
    """
    if len(endpoints) < 2 or max_links <= 0:
        return []

    # Sort by primary axis so neighbors are spatially near
    if side in ("top", "bottom"):
        endpoints = sorted(endpoints, key=lambda p: p[0])  # by x
    else:
        endpoints = sorted(endpoints, key=lambda p: p[1])  # by y

    # Randomly pick disjoint neighbor pairs up to max_links
    idxs = list(range(len(endpoints) - 1))
    rng.shuffle(idxs)
    pairs = []
    used = set()
    for i in idxs:
        a_i, b_i = i, i + 1
        if a_i in used or b_i in used:
            continue
        pairs.append((endpoints[a_i], endpoints[b_i]))
        used.add(a_i); used.add(b_i)
        if len(pairs) >= max_links:
            break

    links = []
    for a, b in pairs:
        ax, ay = a
        bx, by = b
        if side == "top":
            # y=0 edge; raise a midpoint into the top band (0..BLEED)
            mid_y = rng.randint(2, BLEED - 4)
            mid_x = (ax + bx) / 2 + rng.randint(-10, 10)
            mid_x = _clamp(mid_x, 0, CANVAS)
            links.append([(ax, 0), (mid_x, mid_y), (bx, 0)])

        elif side == "bottom":
            # y=CANVAS edge; midpoint up into bottom band (CANVAS-BLEED..CANVAS)
            mid_y = CANVAS - rng.randint(2, BLEED - 4)
            mid_x = (ax + bx) / 2 + rng.randint(-10, 10)
            mid_x = _clamp(mid_x, 0, CANVAS)
            links.append([(ax, CANVAS), (mid_x, mid_y), (bx, CANVAS)])

        elif side == "left":
            # x=0 edge; midpoint into left band (0..BLEED)
            mid_x = rng.randint(2, BLEED - 4)
            mid_y = (ay + by) / 2 + rng.randint(-10, 10)
            mid_y = _clamp(mid_y, 0, CANVAS)
            links.append([(0, ay), (mid_x, mid_y), (0, by)])

        else:  # right
            # x=CANVAS edge; midpoint into right band (CANVAS-BLEED..CANVAS)
            mid_x = CANVAS - rng.randint(2, BLEED - 4)
            mid_y = (ay + by) / 2 + rng.randint(-10, 10)
            mid_y = _clamp(mid_y, 0, CANVAS)
            links.append([(CANVAS, ay), (mid_x, mid_y), (CANVAS, by)])

    return links

def generate_spiderweb_geometry(card: dict) -> dict:
    """
    Rays run outward in the bleed, and cross-links now *only* run within each side's band,
    never traversing across the safe-zone.
    """
    # Tier 1–4
    tier = int(card.get("Tier", 1) or 1)
    tier = max(1, min(4, tier))
    rng = random.Random(f"{card.get('Type','')}-{card.get('Name','')}-{tier}")

    sides = ("top", "right", "bottom", "left")
    lines = []

    # Tier tunables (match your previous feel)
    rays_by_tier   = {1: (16, 18),  2: (24, 28),  3: (34, 38), 4: (44, 48)}
    steps_by_tier  = {1: (5, 6),  2: (5, 6),  3: (6, 7),  4: (6, 7)}
    jitter_by_tier = {1: 23,      2: 25,      3: 27,      4: 29}

    safe_min = BLEED
    safe_max = BLEED + SAFE
    half = BORDER / 2.0

    # ---- RAYS (unchanged logic; safely outside safe-zone) ----
    for side in sides:
        min_r, max_r = rays_by_tier[tier]; rays = rng.randint(min_r, max_r)
        min_s, max_s = steps_by_tier[tier]
        jitter = jitter_by_tier[tier]

        if side in ("top", "bottom"):
            y0 = (safe_min - half) if side == "top" else (safe_max + half)
            y1 = 0 if side == "top" else CANVAS
            slots = [safe_min + (i + 0.5) * (SAFE / float(rays)) for i in range(rays)]
            for x in slots:
                steps = rng.randint(min_s, max_s)
                pts = [(x, y0)]
                for s in range(steps):
                    t = (s + 1) / (steps + 1)
                    y = y0 + t * (y1 - y0)
                    xj = _clamp(x + rng.randint(-jitter, jitter), 0, CANVAS)
                    y  = _clamp(y, 0, CANVAS)
                    pts.append((xj, y))
                pts.append((_clamp(x + rng.randint(-jitter, jitter), 0, CANVAS), y1))
                lines.append(pts)
        else:
            x0 = (safe_min - half) if side == "left" else (safe_max + half)
            x1 = 0 if side == "left" else CANVAS
            slots = [safe_min + (i + 0.5) * (SAFE / float(rays)) for i in range(rays)]
            for y in slots:
                steps = rng.randint(min_s, max_s)
                pts = [(x0, y)]
                for s in range(steps):
                    t = (s + 1) / (steps + 1)
                    x = x0 + t * (x1 - x0)
                    yj = _clamp(y + rng.randint(-jitter, jitter), 0, CANVAS)
                    x  = _clamp(x, 0, CANVAS)
                    pts.append((x, yj))
                pts.append((x1, _clamp(y + rng.randint(-jitter, jitter), 0, CANVAS)))
                lines.append(pts)

    # ---- CROSS-LINKS (new: stay within each side’s bleed band) ----
    endpoints = [ln[-1] for ln in lines]
    groups = {"top": [], "bottom": [], "left": [], "right": []}
    for p in endpoints:
        groups[_classify_endpoint(p)].append(p)

    # Total links per tier, distribute across sides by availability
    total_links = {1: 8, 2: 14, 3: 20, 4: 28}[tier]
    # weight by how many endpoints a side has
    counts = {side: len(groups[side]) for side in groups}
    total_pts = sum(counts.values()) or 1
    per_side = {side: max(0, int(round(total_links * (counts[side] / total_pts)))) for side in groups}

    cross_polylines = []
    for side in ("top", "bottom", "left", "right"):
        cross_polylines.extend(_link_within_side(side, groups[side], per_side[side], rng))

    return {"lines": lines, "cross": cross_polylines}
