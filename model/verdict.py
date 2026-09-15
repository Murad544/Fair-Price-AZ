"""Condition-specific verdicts for the future API and UI."""

import math


def verdict(predicted: float, actual: float, condition: str) -> str:
    if condition not in ("used", "new"):
        raise ValueError("Condition must be used or new")
    if not math.isfinite(predicted) or predicted <= 0 or not math.isfinite(actual) or actual <= 0:
        raise ValueError("Prices must be positive and finite")
    diff_pct = (actual - predicted) / predicted * 100
    threshold = 15 if condition == "used" else 5
    if diff_pct > threshold:
        return f"Overpriced by {diff_pct:.0f}%"
    if diff_pct < -threshold:
        return f"Good deal — {abs(diff_pct):.0f}% below predicted"
    return "Fair price"
