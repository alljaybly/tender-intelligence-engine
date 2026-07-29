"""
Summary Builder — Clean output normalization layer.

Builds a consistent, normalized summary from processing results for:
  - UI consumption (executive view)
  - PDF report generation
  - Excel export consistency

Removes noise fields but preserves ALL honest data (warnings, failures, etc.).
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .confidence_service import compute_composite_confidence

logger = logging.getLogger(__name__)


def build_clean_summary(result_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a clean, normalized summary from a processing result dict.

    This is a PRESENTATION LAYER function.
    It does NOT remove, fabricate, or alter real data.
    It only normalizes structure and removes internal noise fields.

    Args:
        result_data: The full ProcessingResult as a dict

    Returns:
        Clean structured summary dict suitable for UI and PDF
    """
    status = result_data.get("status", "unknown")
    filename = result_data.get("filename", "Unknown")
    job_id = result_data.get("job_id", "")

    # ── Compute confidence ───────────────────────────────────────────
    confidence = compute_composite_confidence(result_data)

    # ── Executive summary data ───────────────────────────────────────
    pricing_result = result_data.get("pricing_result") or {}
    total_contract_value = None
    if pricing_result:
        total_contract_value = (
            pricing_result.get("final_contract_value") or
            pricing_result.get("total_annual") or
            pricing_result.get("total_monthly")
        )

    summary: Dict[str, Any] = {
        # Metadata
        "job_id": job_id,
        "filename": filename,
        "status": status,
        "sector": result_data.get("detected_sector"),
        "duration_months": result_data.get("detected_duration_months"),
        "locations": result_data.get("detected_locations", []),
        "created_at": result_data.get("created_at") or result_data.get("created_at_raw"),

        # Confidence
        "confidence": confidence,

        # Executive summary (for quick decision-making)
        "executive_summary": {
            "total_contract_value": total_contract_value,
            "duration_months": result_data.get("detected_duration_months"),
            "workforce_total": _get_workforce_total(result_data),
            "pricing_confidence": confidence["confidence_label"],
            "processing_status": status,
            "sector": result_data.get("detected_sector"),
            "boq_item_count": len(result_data.get("boq_items", []) or []),
        },

        # Pricing summary
        "pricing": {
            "result": pricing_result,
            "status": result_data.get("pricing_status"),
            "confidence": _extract_pricing_confidence(pricing_result),
            "method": pricing_result.get("price_reliability", "N/A") if pricing_result else "N/A",
            "unavailable_reason": result_data.get("pricing_unavailable_reason"),
        },

        # Workforce summary
        "workforce": {
            "data": result_data.get("detected_workforce", {}),
            "total_workers": _get_workforce_total(result_data),
            "categories": result_data.get("detected_workforce", {}).get("work_categories", []),
        },

        # BOQ summary
        "boq": {
            "item_count": len(result_data.get("boq_items", []) or []),
            "confidence": result_data.get("boq_confidence"),
            "items_with_rates": _count_with_rates(result_data),
            "items_with_amounts": _count_with_amounts(result_data),
        },

        # Key risks and flags
        "risks": {
            "warnings": result_data.get("warnings", []),
            "failed_stages": result_data.get("failed_stages", []),
            "completed_stages": result_data.get("completed_stages", []),
            "has_warnings": len(result_data.get("warnings", []) or []) > 0,
            "has_failed_stages": len(result_data.get("failed_stages", []) or []) > 0,
            "is_partial": status == "partial_success",
            "is_failed": status == "failed",
            "is_completed": status == "completed",
            "ocr_used": _detect_ocr_usage(result_data),
        },

        # Raw data (for technical view)
        "raw": {
            "extraction_method": result_data.get("extraction_method"),
            "pipeline_version": result_data.get("pipeline_version"),
            "metadata": result_data.get("metadata", {}),
            "text_length": result_data.get("text_length", 0),
        },

        # Schedule (if available)
        "schedule": result_data.get("detected_schedule", {}),

        # Retry metadata
        "retry": result_data.get("retry_metadata", {}),
    }

    return summary


def _get_workforce_total(result_data: Dict[str, Any]) -> Optional[int]:
    """Extract total workers from workforce data."""
    workforce = result_data.get("detected_workforce", {})
    if workforce:
        total = workforce.get("total_workers")
        if total is not None:
            try:
                return int(total)
            except (ValueError, TypeError):
                pass
    return None


def _count_with_rates(result_data: Dict[str, Any]) -> int:
    """Count BOQ items that have rate data."""
    items = result_data.get("boq_items", []) or []
    return sum(1 for i in items if i.get("rate") is not None)


def _count_with_amounts(result_data: Dict[str, Any]) -> int:
    """Count BOQ items that have amount data."""
    items = result_data.get("boq_items", []) or []
    return sum(1 for i in items if i.get("amount") is not None)


def _extract_pricing_confidence(pricing_result: Optional[Dict[str, Any]]) -> str:
    """Extract the most meaningful confidence label from pricing."""
    if not pricing_result:
        return "N/A"
    return (
        pricing_result.get("confidence") or
        pricing_result.get("price_reliability") or
        "Estimated"
    )


def _detect_ocr_usage(result_data: Dict[str, Any]) -> bool:
    """Detect if OCR was used during extraction."""
    extraction_method = result_data.get("extraction_method", "")
    if extraction_method and "ocr" in extraction_method.lower():
        return True
    warnings = result_data.get("warnings", [])
    for warning in warnings:
        if "ocr" in warning.lower():
            return True
    return False