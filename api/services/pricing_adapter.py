"""
Pricing integration adapter.

Translates extracted pipeline data into the exact format expected by
PricingEngine.calculate(tender_data, rates_found, debate_result).

Rules:
  - Does NOT fabricate rates_found or debate_result if unavailable
  - Does NOT pass fake defaults for missing required inputs
  - Propagates PricingError payloads for structured failure reporting
  - Logs clear pricing start/success/failure messages
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from ..schemas.pricing import PricingInput

logger = logging.getLogger(__name__)


def _build_tender_data(pricing_input: PricingInput) -> Dict[str, Any]:
    """Convert a PricingInput Pydantic model into the tender_data dict
    expected by PricingEngine.calculate().

    Rules:
      - Only includes fields that were explicitly provided (no defaults for None)
      - Sets _cost_source and _extraction_notes for the engine's strict policy
    """
    tender_data: Dict[str, Any] = {}

    # ── Core required fields ───────────────────────────────────────
    if pricing_input.sector:
        tender_data["sector"] = pricing_input.sector

    if pricing_input.cost_per_hour is not None:
        tender_data["cost_per_hour"] = pricing_input.cost_per_hour
        # Mark the source for the engine's strict cost_source policy
        tender_data["_cost_source"] = pricing_input.cost_source

    # ── Duration ───────────────────────────────────────────────────
    if pricing_input.duration_months is not None:
        tender_data["duration_months"] = pricing_input.duration_months
        tender_data["duration"] = {"months": pricing_input.duration_months}

    # ── Workforce ──────────────────────────────────────────────────
    if pricing_input.workforce is not None:
        tender_data["workforce"] = pricing_input.workforce

    # ── Requirements ───────────────────────────────────────────────
    if pricing_input.requirements is not None:
        tender_data["requirements"] = pricing_input.requirements

    # ── Scope ──────────────────────────────────────────────────────
    if pricing_input.scope is not None:
        tender_data["scope"] = pricing_input.scope

    # ── Location ───────────────────────────────────────────────────
    if pricing_input.location is not None:
        tender_data["location"] = pricing_input.location

    # ── Extraction notes for confidence scoring ────────────────────
    tender_data["_extraction_notes"] = {
        "raw_confidence": "Medium",
    }

    return tender_data


def run_pricing_engine(
    pricing_input: PricingInput,
    rates_found: Optional[Dict[str, Any]] = None,
    debate_result: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
    """Execute PricingEngine.calculate() with honest input handling.

    Args:
        pricing_input: The PricingInput model with extracted/applied data.
        rates_found: Market rates dict from extraction (None if unavailable).
        debate_result: LLM debate result dict (None if unavailable).

    Returns:
        (result_dict, pricing_status, failure_reason):
          - result_dict: The pricing engine output dict, or None on failure.
          - pricing_status: "completed" or "failed".
          - failure_reason: Human-readable reason if failed, else None.

    Rules:
      - If rates_found or debate_result are unavailable, passes {}.
        The engine handles missing data internally via baseline formulas.
      - If the engine raises PricingError, the structured payload's
        'message' field is used as the failure reason.
      - If the engine raises ValueError (e.g. missing sector), that
        is also caught and reported as a structured failure.
    """
    from .pricing_engine import PricingEngine, PricingError

    # ── Validate we have minimum input ─────────────────────────────
    if not pricing_input.sector:
        return None, "failed", "No sector detected. Pricing cannot be calculated."

    if pricing_input.cost_per_hour is None or pricing_input.cost_per_hour <= 0:
        return None, "failed", (
            "Missing cost_per_hour input. Pricing requires a valid "
            "cost_per_hour from user input, document extraction, or config."
        )

    # ── Build tender_data dict ─────────────────────────────────────
    tender_data = _build_tender_data(pricing_input)

    # ── Log pricing start with available inputs ────────────────────
    input_summary = {
        "sector": pricing_input.sector,
        "cost_source": pricing_input.cost_source,
        "duration_months": pricing_input.duration_months,
        "workforce_provided": pricing_input.workforce is not None,
        "requirements_provided": pricing_input.requirements is not None,
        "scope_provided": pricing_input.scope is not None,
        "location_provided": pricing_input.location is not None,
        "rates_found_available": rates_found is not None,
        "debate_result_available": debate_result is not None,
    }
    logger.info("[PRICE_ADAPTER] Starting pricing: sector=%s inputs=%s",
                pricing_input.sector, input_summary)

    # ── Execute pricing ────────────────────────────────────────────
    try:
        engine = PricingEngine()

        # Only pass {} when values are unavailable (honest approach)
        rf = rates_found if rates_found is not None else {}
        dr = debate_result if debate_result is not None else {}

        logger.info("[PRICE_ADAPTER] Calling PricingEngine.calculate() "
                    "with tender_data keys=%s rates_found=%s debate_result=%s",
                    list(tender_data.keys()), "available" if rates_found else "{}",
                    "available" if debate_result else "{}")

        result = engine.calculate(tender_data, rf, dr)

        logger.info("[PRICE_ADAPTER] Pricing succeeded: sector=%s "
                    "final_price=%s confidence=%s",
                    result.get("sector"), result.get("final_price"),
                    result.get("confidence"))

        return result, "completed", None

    except PricingError as e:
        # Structured error from the engine (has .payload dict)
        err_msg = e.payload.get("message", str(e))
        details = e.payload.get("details", {})
        logger.warning("[PRICE_ADAPTER] PricingError: %s details=%s",
                       err_msg, details)
        return None, "failed", err_msg

    except ValueError as e:
        # Missing required fields (e.g. sector not set)
        logger.warning("[PRICE_ADAPTER] ValueError: %s", e)
        return None, "failed", str(e)

    except Exception as e:
        logger.exception("[PRICE_ADAPTER] Unexpected pricing error: %s", e)
        return None, "failed", f"Unexpected pricing error: {e}"