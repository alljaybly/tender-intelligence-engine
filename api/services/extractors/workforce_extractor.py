"""
Workforce requirement extraction from tender document text.

Extracts references to:
- total number of workers
- skilled / unskilled workers
- supervisors / managers
- shifts per day
- hours per day / per week
"""
import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def detect_workforce(text: str) -> Dict[str, Any]:
    """
    Scan document text for workforce-related information.

    Returns a dict with any detected fields:
    {
        "total_workers": int | None,
        "skilled_workers": int | None,
        "unskilled_workers": int | None,
        "supervisors": int | None,
        "shifts_per_day": int | None,
        "hours_per_day": float | None,
        "days_per_week": int | None,
    }
    """
    if not text or not text.strip():
        logger.debug("[WORKFORCE] Empty text")
        return {}

    lower_text = text.lower()
    result: Dict[str, Any] = {}

    # Total workers: "N workers" / "staff of N" / "N staff"
    _extract_number(
        lower_text,
        r"(\d+)\s*(?:workers?|staff|personnel|employees?)",
        "total_workers",
        result,
    )

    # Skilled workers
    _extract_number(
        lower_text,
        r"(\d+)\s*(?:skilled|qualified|trained)\s*(?:workers?|staff|personnel)",
        "skilled_workers",
        result,
    )

    # Unskilled / general workers
    _extract_number(
        lower_text,
        r"(\d+)\s*(?:unskilled|general|labor(?:u)?r(?:ers)?)\s*(?:workers?|staff|personnel)",
        "unskilled_workers",
        result,
    )

    # Supervisors / managers
    _extract_number(
        lower_text,
        r"(\d+)\s*(?:supervisors?|managers?|foremen?|team leaders?)",
        "supervisors",
        result,
    )

    # Shifts per day
    _extract_number(
        lower_text,
        r"(\d+)\s*(?:shifts?\s+(?:per\s+)?day|shifts?\s+daily)",
        "shifts_per_day",
        result,
    )

    # Hours per day
    _extract_float(
        lower_text,
        r"(\d+(?:\.\d+)?)\s*(?:hours?\s+(?:per\s+)?day|hourly\s+day)",
        "hours_per_day",
        result,
    )

    # Hours per week
    _extract_float(
        lower_text,
        r"(\d+(?:\.\d+)?)\s*(?:hours?\s+(?:per\s+)?week|weekly\s+hours)",
        "hours_per_week",
        result,
    )

    # Days per week
    _extract_number(
        lower_text,
        r"(\d+)\s*(?:days?\s+(?:per\s+)?week)",
        "days_per_week",
        result,
    )

    if result:
        logger.info("[WORKFORCE] Detected: %s", result)
    else:
        logger.info("[WORKFORCE] No workforce data detected")

    return result


def _extract_number(text: str, pattern: str, key: str, result: Dict[str, Any]) -> None:
    """Helper: find the first match of a numeric pattern and store it."""
    match = re.search(pattern, text)
    if match:
        result[key] = int(match.group(1))
        logger.debug("[WORKFORCE] %s = %d (matched '%s')", key, result[key], match.group(0))


def _extract_float(text: str, pattern: str, key: str, result: Dict[str, Any]) -> None:
    """Helper: find the first match of a float pattern and store it."""
    match = re.search(pattern, text)
    if match:
        result[key] = float(match.group(1))
        logger.debug("[WORKFORCE] %s = %.1f (matched '%s')", key, result[key], match.group(0))