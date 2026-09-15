"""Report the used-phone primary metric and condition-specific diagnostics."""

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def metrics_by_condition(actual, predicted, conditions):
    actual, predicted, conditions = np.asarray(actual), np.asarray(predicted), np.asarray(conditions)
    result = {}
    for condition in ("used", "new", "all"):
        mask = np.ones(len(actual), dtype=bool) if condition == "all" else conditions == condition
        y, p = actual[mask], predicted[mask]
        result[condition] = None if not len(y) else {
            "n": len(y), "mae_azn": float(mean_absolute_error(y, p)),
            "rmse_azn": float(np.sqrt(mean_squared_error(y, p))),
            "r2": float(r2_score(y, p)) if len(y) > 1 and np.var(y) > 0 else None,
            "bias_azn": float(np.mean(p - y)),
            "mae_pct_mean_price": float(mean_absolute_error(y, p) / np.mean(y) * 100),
        }
    return result
