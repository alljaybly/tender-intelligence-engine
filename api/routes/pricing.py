"""
Pricing Engine Routes (Phase 1)

Isolated pricing endpoints that wrap the existing PricingEngine service.
No scraper, no Selenium, no BOQ parsing, no PDF extraction.
Preserves all existing sector formulas, labour/material/equipment/VAT logic.
"""
import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from ..schemas.pricing import PricingInput, PricingOutput, RepriceInput
from ..services.pricing_engine import PricingEngine, PricingError

router = APIRouter(prefix="/pricing", tags=["Pricing"])
logger = logging.getLogger(__name__)

# Singleton engine instance (stateless, thread-safe)
_engine = PricingEngine()


def _build_tender_data(payload: PricingInput) -> Dict[str, Any]:
    """Convert a validated PricingInput into the internal dict format expected by PricingEngine."""
    tender_data: Dict[str, Any] = {
        "sector": payload.sector,
        "cost_per_hour": payload.cost_per_hour,
        "_cost_source": payload.cost_source or "user",
        "duration_months": payload.duration_months,
    }

    if payload.workforce is not None:
        tender_data["workforce"] = payload.workforce
    if payload.requirements is not None:
        tender_data["requirements"] = payload.requirements
    if payload.scope is not None:
        tender_data["scope"] = payload.scope

    return tender_data


def _output_from_result(result: Dict[str, Any], location: str | None = None) -> Dict[str, Any]:
    """Build a clean output dict from the engine result, applying location factor if given."""
    if location:
        result = _engine.apply_location_factor(result, location)

    # Map all known fields into a flat output
    return {
        "sector": result.get("sector"),
        "labour_cost": result.get("labour_cost"),
        "equipment_cost": result.get("equipment_cost"),
        "materials_cost": result.get("materials_cost"),
        "transport_cost": result.get("transport_cost"),
        "emergency_premium": result.get("emergency_premium"),
        "subtotal": result.get("subtotal"),
        "overheads": result.get("overheads"),
        "profit": result.get("profit"),
        "vat": result.get("vat"),
        "total_monthly": result.get("total_monthly"),
        "total_contract_value": result.get("total_contract_value"),
        "final_price": result.get("final_price"),
        "breakdown": result.get("breakdown"),
        "confidence": result.get("confidence"),
        "assumptions": result.get("assumptions"),
        "calculation_method": result.get("calculation_method"),
        "duration_months": result.get("duration_months"),
        "location": result.get("location"),
        "location_multiplier": result.get("location_multiplier"),
        "workers": result.get("workers"),
        "shifts_per_day": result.get("shifts_per_day"),
        "hours_per_day": result.get("hours_per_day"),
        "rate_source": result.get("rate_source"),
        "Extraction_Error_Mismatch": result.get("Extraction_Error_Mismatch"),
        "extraction_error_code": result.get("extraction_error_code"),
        "pricing_validation_status": result.get("pricing_validation_status"),
        "mismatch_details": result.get("mismatch_details"),
    }


@router.post("/calculate", response_model=PricingOutput, summary="Calculate pricing for a tender")
async def calculate_pricing(payload: PricingInput):
    """
    Calculate pricing for a given sector using the honest pricing engine.

    **Required fields:**
    - `sector`: industry sector (cleaning, construction, electrical, security, gardening, it_services, maintenance, supply, general)
    - `cost_per_hour`: labour cost per hour (> 0)

    **Optional fields:**
    - `_cost_source`: source of cost_per_hour (default: "user")
    - `duration_months`: contract duration in months
    - `workforce`: workforce breakdown dict
    - `requirements`: operational requirements dict (shifts_per_day, hours_per_day)
    - `scope`: scope details (area_sqm, is_emergency)
    - `location`: geographic location for cost adjustment

    Preserves all existing sector formulas, labour/material/equipment/subtotal/VAT/grand-total calculations.
    Works independently from the scraper system.
    """
    logger.info("[PRICING] POST /api/pricing/calculate — sector=%s, cost_per_hour=%s",
                payload.sector, payload.cost_per_hour)

    try:
        tender_data = _build_tender_data(payload)
        rates_found: Dict[str, Any] = {}  # Not used by pricing engine directly
        debate_result: Dict[str, Any] = {}  # Not integrated in Phase 1

        result = _engine.calculate(tender_data, rates_found, debate_result)

        if payload.location:
            result = _engine.apply_location_factor(result, payload.location)

        output = _output_from_result(result, location=payload.location)

        logger.info("[PRICING] Calculation complete — sector=%s, final_price=%s",
                    payload.sector, output.get("final_price"))
        return output

    except PricingError as e:
        logger.error("[PRICING] PricingError: %s", e.payload)
        raise HTTPException(status_code=422, detail=e.payload)
    except ValueError as e:
        logger.error("[PRICING] ValueError: %s", e)
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("[PRICING] Unexpected error: %s", e)
        raise HTTPException(status_code=500, detail="Internal pricing calculation error")


@router.post("/reprice", response_model=PricingOutput, summary="Reprice an existing pricing result")
async def reprice_pricing(payload: RepriceInput):
    """
    Reprice an existing pricing result using one of three strategies:

    - `optimize_win`: reduces profit by 8% and overheads by 5% for competitive pricing
    - `maximize_profit`: increases profit by 5% and overheads by 2% for higher margins
    - `reduce_margin`: aggressive reduction (profit -12%, overheads -8%) for price-sensitive contracts
    """
    logger.info("[PRICING] POST /api/pricing/reprice — mode=%s", payload.mode)

    try:
        result = _engine.reprice(payload.pricing_result, payload.mode)
        output = _output_from_result(result)
        logger.info("[PRICING] Reprice complete — mode=%s, final_price=%s",
                    payload.mode, output.get("final_price"))
        return output
    except Exception as e:
        logger.exception("[PRICING] Reprice error: %s", e)
        raise HTTPException(status_code=500, detail="Repricing calculation failed")
