"""Ridge-regularised least squares, in pure Python.

Why not numpy: the whole problem is at most a dozen features over at most fifty
rows, and adding a compiled dependency to a card generator to solve a 12x12
system would be the wrong trade. Normal equations plus Gaussian elimination with
partial pivoting is forty lines and exact enough at this size.

Why ridge and not plain OLS: the groups are small (Treasure has ten cards) and
the features are correlated -- a Tier 3 Creature has more Health *and* more
Defence -- so X'X is close to singular and an unregularised solve produces huge
cancelling weights that fit the sample and mean nothing. A small penalty keeps
the weights in a range a human can read as a point-buy table.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

#: Ridge penalty. Small: enough to keep a near-singular system solvable, not
#: enough to visibly shrink a weight the data actually supports.
DEFAULT_RIDGE = 0.5


def solve(matrix: List[List[float]], rhs: List[float]) -> List[float]:
    """Gaussian elimination with partial pivoting. Raises on a singular system."""
    n = len(matrix)
    aug = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]

    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-12:
            raise ValueError("singular system at column {}".format(col))
        aug[col], aug[pivot] = aug[pivot], aug[col]
        for row in range(col + 1, n):
            factor = aug[row][col] / aug[col][col]
            if factor:
                for k in range(col, n + 1):
                    aug[row][k] -= factor * aug[col][k]

    out = [0.0] * n
    for row in range(n - 1, -1, -1):
        total = aug[row][n] - sum(aug[row][k] * out[k] for k in range(row + 1, n))
        out[row] = total / aug[row][row]
    return out


def ridge_fit(rows: Sequence[Sequence[float]], target: Sequence[float],
              ridge: float = DEFAULT_RIDGE) -> Tuple[List[float], float]:
    """Fit ``target ~ intercept + rows . weights``. Returns (weights, intercept).

    Columns are centred before the solve and the intercept recovered afterwards,
    so the penalty never falls on the intercept -- penalising it would bias every
    prediction toward zero, which for a cost is meaningless.
    """
    n = len(rows)
    if n == 0:
        return [], 0.0
    p = len(rows[0])
    if p == 0:
        return [], sum(target) / n

    means = [sum(row[j] for row in rows) / n for j in range(p)]
    y_mean = sum(target) / n
    centred = [[row[j] - means[j] for j in range(p)] for row in rows]
    y = [value - y_mean for value in target]

    gram = [[sum(centred[i][a] * centred[i][b] for i in range(n)) for b in range(p)]
            for a in range(p)]
    for j in range(p):
        gram[j][j] += ridge
    moment = [sum(centred[i][j] * y[i] for i in range(n)) for j in range(p)]

    weights = solve(gram, moment)
    intercept = y_mean - sum(weights[j] * means[j] for j in range(p))
    return weights, intercept


def r_squared(actual: Sequence[float], predicted: Sequence[float]) -> float:
    """1 - SS_res/SS_tot. Returns 0.0 when every actual value is identical."""
    n = len(actual)
    if n == 0:
        return 0.0
    mean = sum(actual) / n
    ss_tot = sum((v - mean) ** 2 for v in actual)
    ss_res = sum((a - p) ** 2 for a, p in zip(actual, predicted))
    return 0.0 if ss_tot < 1e-12 else 1.0 - ss_res / ss_tot


def stdev(values: Sequence[float]) -> float:
    """Population standard deviation. 0.0 for fewer than two values."""
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    return (sum((v - mean) ** 2 for v in values) / n) ** 0.5
