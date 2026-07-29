"""
Centralized Pricing Service — Single Entry Point for All Pricing

Incorporates South African QS standards (SANS 1200, SSMBW, ASAQS) insights:
- Strong BOQ validation first (fail closed on weak data)
- Handles "Sum 1", R1, placeholders, maintenance/framework tenders
- Correct BOQ totals: sum valid amounts + 15% VAT = subtotal/vat/grand_total
- Sector-based sanity ceilings (maintenance ≤ R10M, construction ≤ R30M, etc.)
- Clear, honest error messages when data is insufficient
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from .pricing_engine import PricingEngine, PricingError
from .validator import validate_boq_for_pricing
from .boq_extractor import BOQItem

logger = logging.getLogger(__name__)

# ── Sector Sanity Ceilings (South African market aligned) ──────────────
# Based on ASAQS/SSMBW guidance for typical contract values
SECTOR_CEILINGS = {
    "cleaning": 5_000_000,      # R5M - typical cleaning contracts
    "construction": 30_000_000,  # R30M - typical construction
    "electrical": 15_000_000,    # R15M - electrical installations
    "security": 8_000_000,       # R8M - security services
    "gardening": 3_000_000,      # R3M - landscaping/maintenance
    "it_services": 10_000_000,   # R10M - IT services
    "maintenance": 10_000_000,   # R10M - maintenance/framework
    "supply": 20_000_000,        # R20M - supply contracts
    "general": 5_000_000,        # R5M - fallback
}

# Minimum viable BOQ thresholds
MIN_REAL_PRICED_ITEMS = 3
MIN_REAL_PRICED_RATIO = 0.25
MAX_WEAK_PLACEHOLDER_RATIO = 0.40

# VAT rate (South Africa)
VAT_RATE = 0.15


class PricingServiceError(Exception):
    """Structured error for pricing service failures."""
    def __init__(self, payload: Dict[str, Any]):
        self.payload = payload
        super().__init__(str(payload))


def validate_boq_strong(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Run strong BOQ validation — fail closed on weak data.
    
    Returns validation result with status 'complete' or 'error'.
    """
    if not items:
        return {
            "status": "error",
            "code": "NO_BOQ_ITEMS",
            "message": "No BOQ items provided. Cannot proceed with pricing.",
            "details": {"total_items": 0}
        }
    
    # Use existing validator (already has strong checks)
    result = validate_boq_for_pricing(items)
    
    # Add sector-agnostic sanity checks
    if result.get("status") == "complete":
        details = result.get("details", {})
        real_priced = details.get("real_priced_items", 0)
        total = details.get("total_items", 0)
        
        if real_priced < MIN_REAL_PRICED_ITEMS:
            result = {
                "status": "error",
                "code": "INSUFFICIENT_REAL_ITEMS",
                "message": f"Only {real_priced} real-priced BOQ items (minimum {MIN_REAL_PRICED_ITEMS} required).",
                "details": details
            }
        
        priced_ratio = details.get("real_priced_ratio", 0)
        if priced_ratio < MIN_REAL_PRICED_RATIO:
            result = {
                "status": "error",
                "code": "LOW_PRICED_RATIO",
                "message": f"Only {priced_ratio:.0%} of items have valid pricing (minimum {MIN_REAL_PRICED_RATIO:.0%}).",
                "details": details
            }
    
    return result


def calculate_boq_totals(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate BOQ totals correctly per SANS 1200 / ASAQS:
    - Sum only valid amounts (amount > 1, not placeholders)
    - Add 15% VAT
    - Return subtotal, vat, grand_total
    """
    subtotal = 0.0
    valid_items = 0
    placeholder_items = 0
    
    for item in items:
        amount = item.get("amount")
        rate = item.get("rate")
        description = (item.get("description") or "").strip().lower()
        
        # Skip placeholder descriptions
        if any(p in description for p in ["sum 1", "no 1", "r 1", "r1"]):
            placeholder_items += 1
            continue
        
        # Skip explicit placeholder rates/amounts
        if isinstance(amount, (int, float)) and amount == 1:
            placeholder_items += 1
            continue
        if isinstance(rate, (int, float)) and rate == 1:
            placeholder_items += 1
            continue
        
        # Valid amount: numeric and > 1 (not a placeholder)
        if isinstance(amount, (int, float)) and amount > 1:
            subtotal += float(amount)
            valid_items += 1
        # Fallback: if no amount but valid rate * quantity
        elif isinstance(rate, (int, float)) and rate > 1:
            qty = item.get("quantity")
            if isinstance(qty, (int, float)) and qty > 0:
                subtotal += float(rate) * float(qty)
                valid_items += 1
    
    vat = round(subtotal * VAT_RATE, 2)
    grand_total = round(subtotal + vat, 2)
    
    return {
        "subtotal": round(subtotal, 2),
        "vat": vat,
        "grand_total": grand_total,
        "vat_rate": VAT_RATE,
        "valid_items_count": valid_items,
        "placeholder_items_count": placeholder_items,
    }


def apply_sector_ceiling(final_price: float, sector: str) -> Tuple[float, Optional[str]]:
    """
    Apply sector-based sanity ceiling.
    Returns (adjusted_price, warning_message_or_None).
    """
    ceiling = SECTOR_CEILINGS.get(sector.lower(), SECTOR_CEILINGS["general"])
    
    if final_price > ceiling:
        warning = (
            f"PRICE_CEILING_EXCEEDED: Calculated price R{final_price:,.2f} exceeds "
            f"{sector} sector ceiling of R{ceiling:,.2f}. "
            f"Review BOQ quantities, rates, or duration."
        )
        logger.warning("[PRICING_SERVICE] %s", warning)
        return ceiling, warning
    
    return final_price, None


def build_pricing_input(
    sector: str,
    cost_per_hour: float,
    cost_source: str,
    duration_months: Optional[int] = None,
    workforce: Optional[Dict] = None,
    requirements: Optional[Dict] = None,
    scope: Optional[Dict] = None,
    location: Optional[str] = None,
    boq_items: Optional[List[Dict]] = None,
    boq_totals: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Build the tender_data dict for PricingEngine.calculate().
    This is the single point of truth for pricing input construction.
    """
    tender_data: Dict[str, Any] = {
        "sector": sector,
        "cost_per_hour": cost_per_hour,
        "_cost_source": cost_source,
    }
    
    if duration_months is not None:
        tender_data["duration_months"] = duration_months
        tender_data["duration"] = {"months": duration_months}
    
    if workforce:
        tender_data["workforce"] = workforce
    
    if requirements:
        tender_data["requirements"] = requirements
    
    if scope:
        tender_data["scope"] = scope
    
    if location:
        tender_data["location"] = location
    
    # Attach BOQ data for reference
    if boq_items:
        tender_data["boq_items"] = boq_items
    if boq_totals:
        tender_data["boq_totals"] = boq_totals
    
    # Extraction notes for confidence scoring
    tender_data["_extraction_notes"] = {
        "raw_confidence": "Medium",
        "boq_items_count": len(boq_items) if boq_items else 0,
    }
    
    return tender_data


def run_pricing(
    sector: str,
    cost_per_hour: float,
    cost_source: str,
    duration_months: Optional[int] = None,
    workforce: Optional[Dict] = None,
    requirements: Optional[Dict] = None,
    scope: Optional[Dict] = None,
    location: Optional[str] = None,
    boq_items: Optional[List[Dict]] = None,
    rates_found: Optional[Dict] = None,
    debate_result: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    MAIN ENTRY POINT — Run complete pricing workflow.
    
    Steps:
    1. Strong BOQ validation (if BOQ items provided)
    2. Calculate BOQ totals (if BOQ items provided)
    3. Build pricing input
    4. Run PricingEngine.calculate()
    4. Apply sector ceiling
    5. Return final result with clear error messages
    
    Returns:
        Dict with keys: final_price, breakdown, confidence, assumptions, 
        calculation_trace, rate_source, warnings (list), boq_validation, boq_totals
    
    Raises:
        PricingServiceError with structured payload on failure
    """
    warnings = []
    boq_validation = None
    boq_totals = None
    
    # ── Step 1: Strong BOQ Validation ─────────────────────────────────
    if boq_items:
        boq_validation = validate_boq_strong(boq_items)
        
        if boq_validation.get("status") == "error":
            # BOQ too weak — return clear error, don't proceed to pricing
            error_payload = {
                "status": "error",
                "code": boq_validation.get("code", "BOQ_VALIDATION_FAILED"),
                "message": boq_validation.get("message", "BOQ validation failed"),
                "details": boq_validation.get("details", {}),
                "warnings": warnings,
            }
            logger.error("[PRICING_SERVICE] BOQ validation failed: %s", error_payload["message"])
            raise PricingServiceError(error_payload)
        
        # BOQ passed validation — calculate totals
        boq_totals = calculate_boq_totals(boq_items)
        warnings.append(f"BOQ validated: {boq_totals['valid_items_count']} priced items, "
                       f"subtotal R{boq_totals['subtotal']:,.2f}, VAT R{boq_totals['vat']:,.2f}, "
                       f"total R{boq_totals['grand_total']:,.2f}")
    
    # ── Step 2: Validate core inputs ──────────────────────────────────
    if not sector:
        raise PricingServiceError({
            "status": "error",
            "code": "MISSING_SECTOR",
            "message": "Sector is required for pricing calculation",
            "details": {},
            "warnings": warnings,
        })
    
    if cost_per_hour is None or cost_per_hour <= 0:
        raise PricingServiceError({
            "status": "error",
            "code": "INVALID_COST_PER_HOUR",
            "message": "cost_per_hour must be a positive number from user input, document, or config",
            "details": {"cost_per_hour": cost_per_hour, "cost_source": cost_source},
            "warnings": warnings,
        })
    
    if duration_months is None or duration_months <= 0:
        raise PricingServiceError({
            "status": "error",
            "code": "MISSING_DURATION",
            "message": "Duration (months) is required for pricing calculation",
            "details": {"duration_months": duration_months},
            "warnings": warnings,
        })
    
    # ── Step 3: Build pricing input ───────────────────────────────────
    tender_data = build_pricing_input(
        sector=sector,
        cost_per_hour=cost_per_hour,
        cost_source=cost_source,
        duration_months=duration_months,
        workforce=workforce,
        requirements=requirements,
        scope=scope,
        location=location,
        boq_items=boq_items,
        boq_totals=boq_totals,
    )
    
    # ── Step 4: Run Pricing Engine ────────────────────────────────────
    try:
        engine = PricingEngine()
        rf = rates_found if rates_found is not None else {}
        dr = debate_result if debate_result is not None else {}
        
        logger.info("[PRICING_SERVICE] Running PricingEngine for sector=%s", sector)
        result = engine.calculate(tender_data, rf, dr)
        
    except PricingError as e:
        # Engine returned structured error
        error_payload = e.payload
        error_payload["warnings"] = warnings
        if boq_validation:
            error_payload["boq_validation"] = boq_validation
        if boq_totals:
            error_payload["boq_totals"] = boq_totals
        raise PricingServiceError(error_payload)
    
    except ValueError as e:
        raise PricingServiceError({
            "status": "error",
            "code": "PRICING_INPUT_ERROR",
            "message": str(e),
            "details": {},
            "warnings": warnings,
            "boq_validation": boq_validation,
            "boq_totals": boq_totals,
        })
    
    except Exception as e:
        logger.exception("[PRICING_SERVICE] Unexpected pricing error")
        raise PricingServiceError({
            "status": "error",
            "code": "PRICING_ENGINE_ERROR",
            "message": f"Unexpected pricing error: {e}",
            "details": {},
            "warnings": warnings,
            "boq_validation": boq_validation,
            "boq_totals": boq_totals,
        })
    
    # ── Step 5: Apply Sector Ceiling ──────────────────────────────────
    final_price = result.get("final_price")
    if isinstance(final_price, (int, float)):
        adjusted_price, ceiling_warning = apply_sector_ceiling(float(final_price), sector)
        if ceiling_warning:
            warnings.append(ceiling_warning)
            result["final_price"] = adjusted_price
            result["price_ceiling_applied"] = True
            result["price_ceiling_value"] = SECTOR_CEILINGS.get(sector.lower(), SECTOR_CEILINGS["general"])
    
    # ── Step 6: Attach metadata ───────────────────────────────────────
    result["warnings"] = warnings
    result["boq_validation"] = boq_validation
    result["boq_totals"] = boq_totals
    
    logger.info("[PRICING_SERVICE] Pricing complete: sector=%s final_price=%s confidence=%s",
                sector, result.get("final_price"), result.get("confidence"))
    
    return result


def estimate_from_boq_only(
    boq_items: List[Dict],
    sector: str,
    duration_months: int,
    cost_per_hour: float,
    cost_source: str = "document",
) -> Dict[str, Any]:
    """
    Convenience method: price directly from BOQ items without full pipeline.
    Used for quick estimates or testing.
    """
    # Validate BOQ
    validation = validate_boq_strong(boq_items)
    if validation.get("status") == "error":
        raise PricingServiceError({
            "status": "error",
            "code": validation.get("code", "BOQ_VALIDATION_FAILED"),
            "message": validation.get("message", "BOQ validation failed"),
            "details": validation.get("details", {}),
        })
    
    # Calculate BOQ totals
    totals = calculate_boq_totals(boq_items)
    
    # Estimate workforce from BOQ if not provided
    workforce = {"total_workers": max(1, len([i for i in boq_items if i.get("amount", 0) > 1]))}
    
    # Run pricing
    return run_pricing(
        sector=sector,
        cost_per_hour=cost_per_hour,
        cost_source=cost_source,
        duration_months=duration_months,
        workforce=workforce,
        boq_items=boq_items,
    )


# ── Backward compatibility: expose key functions ──────────────────────
__all__ = [
    "PricingServiceError",
    "SECTOR_CEILINGS",
    "VAT_RATE",
    "validate_boq_strong",
    "calculate_boq_totals",
    "apply_sector_ceiling",
    "build_pricing_input",
    "run_pricing",
    "estimate_from_boq_only",
]