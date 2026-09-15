"""Conservative condition conflict checks, not a general language classifier."""

import re
import unicodedata


def condition_conflict(condition, description):
    """Flag explicit usage claims; avoid generic shop lists and negated 'used'."""
    text = unicodedata.normalize("NFC", description or "").replace("İ", "i").casefold()
    patterns = (
        r"\b(?:az|çox az|cox az)\s+(?:(?:və|ve)\s+(?:səliqəli|seliqeli)\s+)?(?:işlənib|islenib|işlənmiş|islenmis)\b",
        r"\b(?:\d+|bir)\s*(?:ay|il)\s+(?:işlənib|islenib|istifadə olunub|istifade olunub)\b",
        r"\b(?:like new|lightly used)\b",
    )
    return condition == "new" and any(re.search(pattern, text) for pattern in patterns)
