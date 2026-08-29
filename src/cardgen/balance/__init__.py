"""Balance analysis: what a card costs against what the rest of the deck charges.

The split this package exists to keep: **the arithmetic is deterministic Python,
the judgment is not.** A least-squares fit can say that Moonfang costs three
less than its stats predict; only a person reading its rules text can say
whether that is a mistake or a drawback the numbers cannot see. So this package
produces evidence -- weights, residuals, ``n``, ``r2`` -- and the
``/card-balance`` skill puts each finding to the author and records the answer
in its own reference files, which this package then reads back on the next run.

    python -m cardgen.cli balance            # the readable report
    python -m cardgen.cli balance --json     # what the skill consumes
"""

from .config import DEFAULTS, MODEL_FILE, RULINGS_FILE, load_model, load_rulings
from .features import activation_cost, cost_keys, cost_of, feature_keys, features_of
from .linear import r_squared, ridge_fit
from .report import analyse, fit_group, findings_for, render_text

__all__ = [
    "DEFAULTS",
    "MODEL_FILE",
    "RULINGS_FILE",
    "activation_cost",
    "analyse",
    "cost_keys",
    "cost_of",
    "feature_keys",
    "features_of",
    "findings_for",
    "fit_group",
    "load_model",
    "load_rulings",
    "r_squared",
    "render_text",
    "ridge_fit",
]
