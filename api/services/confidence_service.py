"""
Confidence Service — Computes composite confidence scores from pipeline results.

Factors:
  - text_extraction_quality (0–1): based on text length, OCR usage
  - boq_completeness (0–1): based on BOQ item count, rate/amount coverage
  - pricing_assumptions_level (0–1): based on pricing method (boq_based > estimated)
  - ocr_usage_penalty (0–1): penalty for OCR fallback
  - missing_fields_penalty (0–1): penalty for missing key fields (sector, duration, etc.)

Output:
  {
    "confidence_score": float (0–1),
    "confidence_label": "low|medium|high",
    "breakdown": {
      "extraction": float,
      "boq": float,
      "pricing": float,
      "ocr_penalty": float
    }
  }

RULE:
  Do NOT inflate confidence artificially.
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def compute_composite_confidence(result_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute a composite confidence score from processing result data.

    Args:
        result_data: The full ProcessingResult as a dict

    Returns:
        Dict with confidence_score, confidence_label, and breakdown
    """
    # ── Factor 1: Text extraction quality ────────────────────────────
    extraction_score = _compute_extraction_quality(result_data)

    # ── Factor 2: BOQ completeness ───────────────────────────────────
    boq_score = _compute_boq_completeness(result_data)

    # ── Factor 3: Pricing assumptions level ──────────────────────────
    pricing_score = _compute_pricing_quality(result_data)

    # ── Factor 4: OCR usage penalty ──────────────────────────────────
    ocr_penalty = _compute_ocr_penalty(result_data)

    # ── Factor 5: Missing fields penalty ─────────────────────────────
    missing_penalty = _compute_missing_fields_penalty(result_data)

    # ── Composite calculation ────────────────────────────────────────
    base_score = (extraction_score * 0.30 +
                  boq_score * 0.25 +
                  pricing_score * 0.25)

    # Apply penalties
    penalty = max(ocr_penalty, missing_penalty)
    final_score = max(0.0, base_score * (1.0 - penalty))

    # ── Determine label ──────────────────────────────────────────────
    if final_score >= 0.8:
        label = "high"
    elif final_score >= 0.5:
        label = "medium"
    else:
        label = "low"

    logger.debug(
        "[CONFIDENCE] Score=%.2f label=%s extraction=%.2f boq=%.2f "
        "pricing=%.2f ocr_penalty=%.2f missing_penalty=%.2f",
        final_score, label, extraction_score, boq_score,
        pricing_score, ocr_penalty, missing_penalty,
    )

    return {
        "confidence_score": round(final_score, 3),
        "confidence_label": label,
        "breakdown": {
            "extraction": round(extraction_score, 3),
            "boq": round(boq_score, 3),
            "pricing": round(pricing_score, 3),
            "ocr_penalty": round(ocr_penalty, 3),
            "missing_penalty": round(missing_penalty, 3),
        },
    }


def _compute_extraction_quality(result_data: Dict[str, Any]) -> float:
    """Score text extraction quality (0–1)."""
    full_text = result_data.get("full_text")
    text_length = result_data.get("text_length") or 0

    if not full_text or text_length == 0:
        return 0.0

    # Score based on text length
    if text_length >= 10000:
        length_score = 1.0
    elif text_length >= 5000:
        length_score = 0.85
    elif text_length >= 1000:
        length_score = 0.6
    elif text_length >= 200:
        length_score = 0.3
    else:
        length_score = 0.1

    return length_score


def _compute_boq_completeness(result_data: Dict[str, Any]) -> float:
    """Score BOQ completeness (0–1)."""
    boq_items = result_data.get("boq_items", [])

    if not boq_items:
        return 0.0

    if not isinstance(boq_items, list):
        return 0.0

    item_count = len(boq_items)
    if item_count == 0:
        return 0.0

    # Score based on item count
    if item_count >= 30:
        count_score = 1.0
    elif item_count >= 15:
        count_score = 0.8
    elif item_count >= 5:
        count_score = 0.5
    else:
        count_score = 0.3

    # Check rate/amount coverage
    items_with_rates = sum(1 for i in boq_items if i.get("rate") is not None)
    items_with_amounts = sum(1 for i in boq_items if i.get("amount") is not None)

    rate_coverage = items_with_rates / item_count if item_count > 0 else 0
    amount_coverage = items_with_amounts / item_count if item_count > 0 else 0

    # Combined score (count + coverage)
    coverage_score = (rate_coverage * 0.5 + amount_coverage * 0.5)
    boq_confidence = result_data.get("boq_confidence", "")
    confidence_multiplier = 1.0
    if boq_confidence == "High":
        confidence_multiplier = 1.0
    elif boq_confidence == "Medium":
        confidence_multiplier = 0.75
    elif boq_confidence == "Low":
        confidence_multiplier = 0.5
    else:
        confidence_multiplier = 0.4

    return (count_score * 0.4 + coverage_score * 0.6) * confidence_multiplier


def _compute_pricing_quality(result_data: Dict[str, Any]) -> float:
    """Score pricing quality (0–1)."""
    pricing_result = result_data.get("pricing_result")
    if not pricing_result:
        return 0.0

    # Check pricing method
    method = pricing_result.get("price_reliability", "")
    if method == "boq_based":
        method_score = 1.0
    elif method == "estimated":
        method_score = 0.6
    elif method == "low":
        method_score = 0.3
    else:
        method_score = 0.5

    # Check if key fields are present
    has_total = pricing_result.get("total_monthly") is not None or \
                pricing_result.get("final_contract_value") is not None
    has_vat = pricing_result.get("vat") is not None

    completeness = 0.0
    if has_total:
        completeness += 0.6
    if has_vat:
        completeness += 0.4

    return method_score * (0.5 + completeness * 0.5)


def _compute_ocr_penalty(result_data: Dict[str, Any]) -> float:
    """Compute penalty for OCR usage (0 = no penalty, 1 = max penalty)."""
    extraction_method = result_data.get("extraction_method", "")
    warnings = result_data.get("warnings", [])

    # Check extraction method for OCR indication
    if "ocr" in extraction_method.lower():
        return 0.15  # 15% penalty for OCR

    # Check warnings for OCR
    for warning in warnings:
        if "ocr" in warning.lower():
            return 0.15

    return 0.0


def _compute_missing_fields_penalty(result_data: Dict[str, Any]) -> float:
    """Compute penalty for missing key fields (0 = no penalty, 1 = max penalty)."""
    penalties = 0.0
    total_checks = 0

    # Check sector
    total_checks += 1
    if not result_data.get("detected_sector"):
        penalties += 1.0

    # Check duration
    total_checks += 1
    if result_data.get("detected_duration_months") is None:
        penalties += 0.5  # Partial penalty

    # Check locations
    total_checks += 1
    locations = result_data.get("detected_locations", [])
    if not locations:
        penalties += 0.3

    # Check workforce
    total_checks += 1
    workforce = result_data.get("detected_workforce", {})
    if not workforce:
        penalties += 0.5

    # Check pricing result
    total_checks += 1
    if not result_data.get("pricing_result"):
        penalties += 1.0

    if total_checks == 0:
        return 0.0

    # Normalize to 0–1
    return min(1.0, penalties / total_checks)