from typing import Dict, List, Any, Optional
import re


def _suggest_inputs_from_signals(schedule: Dict[str, Any]) -> Dict[str, List[int]]:
    suggestions: Dict[str, List[int]] = {}
    signals = schedule.get('detected_signals') if isinstance(schedule, dict) else None
    if not signals:
        return suggestions

    joined = ' '.join(signals).lower()
    if '24_hour' in joined or '24h_coverage' in joined or '24h' in joined:
        suggestions['shifts_per_day'] = [3]
        suggestions['hours_per_day'] = [8]
    if 'day_and_night' in joined or 'day-night' in joined:
        suggestions.setdefault('shifts_per_day', []).append(2)
        suggestions.setdefault('hours_per_day', []).append(12)

    return suggestions


def validate_extracted_tender(extracted: Dict[str, Any]) -> Dict[str, Any]:
    """Validate required fields. Return None-like dict for completeness or structured error payload."""
    missing: List[str] = []

    # shifts and hours are exposed at top level as integers (or None)
    shifts = extracted.get('shifts_per_day')
    hours = extracted.get('hours_per_day')

    if shifts is None:
        missing.append('shifts_per_day')
    if hours is None:
        missing.append('hours_per_day')

    # workers
    workforce = extracted.get('workforce', {}) or {}
    workers = workforce.get('total_workers') if isinstance(workforce, dict) else None
    if workers is None:
        missing.append('workers')

    # duration: try multiple fields
    duration = extracted.get('duration') or {}
    duration_months = None
    if isinstance(duration, dict):
        duration_months = duration.get('months')
    if duration_months is None:
        duration_months = extracted.get('duration_months')
    if duration_months is None:
        missing.append('duration')

    if missing:
        schedule = extracted.get('schedule') or {}
        payload = {
            'status': 'incomplete',
            'missing_fields': missing,
            'extracted_data': {
                'shifts_per_day': shifts,
                'hours_per_day': hours,
                'workers': workers,
                'duration': duration_months
            },
            'detected_signals': schedule.get('detected_signals', []),
            'suggested_inputs': _suggest_inputs_from_signals(schedule)
        }
        return payload

    return {'status': 'complete'}


def validate_boq_for_pricing(boq_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Stricter structural BOQ gate for South African tenders, designed to block placeholder-heavy maintenance
    maintenance BOQs before pricing/workforce inference.
    Returns {"status": "ok"} if pricing can proceed; structured error otherwise.
    """
    total = len(boq_items)

    # No items: cannot price
    if total == 0:
        return {
            "status": "error",
            "code": "INSUFFICIENT_BOQ_DATA",
            "message": "INSUFFICIENT_BOQ_DATA: No BOQ items to price.",
            "details": {"total_items": 0}
    }

    # Regex for common SA tender placeholder patterns
    placeholder_desc_patterns = [
        r"sum\s*1",  # Sum 1
        r"no\s*1",  # No 1
        r"r\s*1",  # R 1/R1
        r"^sum\s+1\.0",
        r"^1\.0",
    ]
    placeholder_desc_re = re.compile("|".join(placeholder_desc_patterns), re.IGNORECASE)

    # Short/generic descriptions to flag
    generic_descriptions = {"general works", "site works", "site establishment", "site clearance",
                        "labour", "material", "tools", "equipment", "other", "miscellaneous",
                        "provisional sum", "prime cost", "pc sum"}

    real_priceable = 0
    placeholder_items = 0
    low_rate_items = 0
    high_rate_items = 0
    flagged_items: List[Dict[str, Any]] = []

    for item in boq_items:
        desc = (item.get("description") or "").strip()
        rate = item.get("rate")
        amount = item.get("amount")
        quantity = item.get("quantity")

        is_placeholder = False
        reason = []

        # Exact value placeholders (SA tender markers
        if rate is not None and (rate == 1 or rate == 1.0):
            is_placeholder = True
            reason.append("rate=1")
        if amount is not None and (amount == 1 or amount == 1.0):
            is_placeholder = True
            reason.append("amount=1")

        # Description-based SA placeholder
        if placeholder_desc_re.search(desc):
            is_placeholder = True
            reason.append("placeholder-pattern")

        # No1/quantity=1 with missing rate/amount
        if quantity is not None and (quantity == 1 or quantity == 1.0) and (rate is None or amount is None):
            is_placeholder = True
            reason.append("quantity=1-missing-rate/amount")

        # Short/generic description
        if desc.lower() in generic_descriptions or len(desc) < 8:
            is_placeholder = True
            reason.append("short/generic-desc")

        if is_placeholder:
            placeholder_items += 1
            flagged_items.append({"desc": desc, "rate": rate, "amount": amount, "reason": reason})
            continue

        # Low-rate items (<=5)
        if rate is not None and rate <= 5:
            low_rate_items += 1

        # High-rate block (> R500k)
        if rate is not None and rate > 500000:
            high_rate_items += 1

        # Real priceable: rate>5 AND amount>5 AND meaningful desc
        rate_ok = rate is not None and rate > 5
        amount_ok = amount is not None and amount > 5
        desc_ok = len(desc) > 8 and desc.lower() not in generic_descriptions
        if rate_ok and amount_ok and desc_ok:
            real_priceable += 1

    # High-rate block first (keep existing requirement
    if high_rate_items > 0:
        return {
            "status": "error",
            "code": "HIGH_RATE_DETECTED",
            "message": "HIGH_RATE_DETECTED: BOQ contains rates exceeding R500,000.",
            "details": {"total_items": total, "high_rate_items": high_rate_items}
        }

    # Calculate ratios
    placeholder_ratio = placeholder_items / total
    low_rate_ratio = low_rate_items / total
    problematic_ratio = (placeholder_items + low_rate_items) / total
    real_priceable_ratio = real_priceable / total

    # Block if >40% are problematic (placeholders + rate<=5)
    if problematic_ratio > 0.40:
        return {
            "status": "error",
            "code": "INSUFFICIENT_BOQ_DATA",
            "message": "INSUFFICIENT_BOQ_DATA: BOQ dominated by placeholders (Sum 1/R1/rate<=1/short descriptions.",
            "details": {
                "total_items": total,
                "placeholder_items": placeholder_items,
                "low_rate_items": low_rate_items,
                "problematic_ratio": round(problematic_ratio, 2),
                "real_priceable": real_priceable,
                "flagged_samples": flagged_items[:10]
            }
        }

    # Block if fewer than 25% real priceable items
    if real_priceable_ratio < 0.25:
        return {
            "status": "error",
            "code": "INSUFFICIENT_BOQ_DATA",
            "message": "INSUFFICIENT_BOQ_DATA: Fewer than 25% of BOQ items are real priceable items.",
            "details": {
                "total_items": total,
                "real_priceable": real_priceable,
                "real_priceable_ratio": round(real_priceable_ratio, 2),
                "placeholder_items": placeholder_items
            }
        }

    # All checks passed
    return {
        "status": "ok",
        "details": {
            "total_items": total,
            "real_priceable": real_priceable,
            "real_priceable_ratio": round(real_priceable_ratio, 2),
            "placeholder_items": placeholder_items
        }
    }
