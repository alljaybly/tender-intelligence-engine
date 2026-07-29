"""
Contract duration extraction via regex patterns in tender text.

Searches for patterns like:
- "period of [N] months"
- "[N]-year contract"
- "duration: [N] [weeks/months/years]"
- etc.
"""
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Patterns that indicate duration, ordered by specificity. Each accepted
# pattern captures a numeric token followed by month/months/year/years/period.
_DURATION_PATTERNS = [
    # Explicit "period of X months" or "period of X year(s)"
    re.compile(r"period\s+of\s+(\d+(?:\.\d+)?)\s*(month|months|year|years|period)\b", re.IGNORECASE),
    # "duration: X months/years"
    re.compile(r"duration\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(month|months|year|years|period)\b", re.IGNORECASE),
    # "X-month contract" / "X-year contract"
    re.compile(r"(\d+(?:\.\d+)?)\s*[- ](month|months|year|years|period)\s+contract", re.IGNORECASE),
    # "contract period X months/years"
    re.compile(r"contract\s+period\s*(?:of\s+)?(\d+(?:\.\d+)?)\s*(month|months|year|years|period)\b", re.IGNORECASE),
    # "initial period: X months"
    re.compile(r"initial\s+period\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(month|months|year|years|period)\b", re.IGNORECASE),
    # "valid for X months"
    re.compile(r"valid\s+for\s+(\d+(?:\.\d+)?)\s*(month|months|year|years|period)\b", re.IGNORECASE),
    # "X year(s)" near "contract"
    re.compile(r"(\d+(?:\.\d+)?)\s*(year|years)\s+(?:period|contract|term)", re.IGNORECASE),
    # "term: X months"
    re.compile(r"term\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(month|months|year|years|period)\b", re.IGNORECASE),
    # "X months" within 20 chars of "appointment" or "engagement"
    re.compile(r"appointment\s+(?:period\s+)?(?:of\s+)?(\d+(?:\.\d+)?)\s+(month|months|year|years|period)\b", re.IGNORECASE),
    # Fallback: "X months" or "X years" (we'll take the last one found)
    re.compile(r"(\d+(?:\.\d+)?)\s+(month|months|year|years|period)\b", re.IGNORECASE),
]


def _has_currency_marker(text: str, start: int) -> bool:
    """Reject duration candidates whose numeric token is formatted as a Rand price."""
    prefix = text[max(0, start - 4):start]
    return bool(re.search(r"[Rr]\s*$", prefix))


def detect_duration(text: str) -> Optional[int]:
    """
    Scan document text for contract duration references.

    Returns the detected duration in months.
    """
    if not text or not text.strip():
        logger.debug("[DURATION] Empty text")
        return None

    values_months: list[int] = []

    for pattern in _DURATION_PATTERNS:
        for match in pattern.finditer(text):
            if _has_currency_marker(text, match.start(1)):
                logger.debug("[DURATION] Rejected currency-like token '%s'", match.group(0))
                continue

            value_float = float(match.group(1))
            # Check if unit is year — multiply
            unit = match.group(2).lower()
            if unit.startswith("year"):
                value_float *= 12
            value = int(value_float) if value_float.is_integer() else round(value_float)
            values_months.append(value)
            logger.debug("[DURATION] Matched '%s' -> %d months", match.group(0), value)

    if not values_months:
        logger.info("[DURATION] No duration detected")
        return None

    # Return the most commonly cited value (mode), or the largest if unique
    from collections import Counter
    counter = Counter(values_months)
    most_common = counter.most_common(1)[0][0]
    logger.info("[DURATION] Detected %d months (from %d matches)", most_common, len(values_months))
    return most_common
