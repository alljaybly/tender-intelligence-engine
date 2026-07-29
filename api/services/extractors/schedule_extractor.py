"""
Schedule / timeline extraction from tender document text.

Detects references to:
- start dates and completion dates
- milestones
- delivery timelines
- phased delivery
"""
import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Date-like patterns
_DATE_PATTERNS = [
    re.compile(r"\b(\d{1,2})\s*(?:st|nd|rd|th)?\s*(january|february|march|april|may|june|july|august|september|october|november|december)\s*(\d{4})?\b", re.IGNORECASE),
    re.compile(r"\b(\d{4})[-/](\d{2})[-/](\d{2})\b"),  # 2026-05-13
    re.compile(r"\b(\d{2})[-/](\d{2})[-/](\d{4})\b"),  # 13/05/2026
]


def detect_schedule(text: str) -> Dict[str, Any]:
    """
    Scan document text for schedule / timeline references.

    Returns a dict with any detected fields:
    {
        "start_date": str | None,
        "completion_date": str | None,
        "has_milestones": bool,
        "milestone_count": int,
        "delivery_timeline": str | None,
        "phases_detected": int,
    }
    """
    if not text or not text.strip():
        logger.debug("[SCHEDULE] Empty text")
        return {}

    lower_text = text.lower()
    result: Dict[str, Any] = {}
    dates_found: list[str] = []

    # Collect all date references
    for pattern in _DATE_PATTERNS:
        for match in pattern.finditer(text):
            dates_found.append(match.group(0))

    # Detect milestones
    milestone_keywords = ["milestone", "phase", "deliverable", "stage"]
    milestone_count = sum(
        len(re.findall(re.escape(kw), lower_text))
        for kw in milestone_keywords
    )
    result["milestone_count"] = milestone_count
    result["has_milestones"] = milestone_count > 0

    # Detect delivery timeline phrasing
    timeline_match = re.search(
        r"(?:delivery|completion|implementation)\s*(?:timeline|period|schedule)?\s*[:\-]?\s*(.{0,100})",
        lower_text,
    )
    if timeline_match:
        snippet = timeline_match.group(1).strip()
        if len(snippet) > 5:
            result["delivery_timeline"] = snippet[:100]

    # Count phases
    phase_count = len(re.findall(r"\bphase\s+\d+\b", lower_text, re.IGNORECASE))
    result["phases_detected"] = phase_count

    # Store dates if found
    if dates_found:
        result["dates_detected"] = len(dates_found)
        result["date_references"] = dates_found[:5]  # Limit to 5

    if result:
        logger.info("[SCHEDULE] Detected: %s", result)
    else:
        logger.info("[SCHEDULE] No schedule data detected")

    return result