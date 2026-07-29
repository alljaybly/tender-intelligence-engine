"""
Workforce Inference Engine — Estimates workforce requirements from BOQ work items.

Maps classified work categories into estimated labour needs:
  - skilled_workers
  - unskilled_workers
  - supervisors

Each estimate is EXPLAINABLE — it logs the reasoning (category → worker mapping).
No magic numbers. Every multiplier has a named constant with justification.

CRITICAL RULE:
  This is an ESTIMATE, not a guarantee. The confidence field communicates
  reliability. Pricing validation still requires real workforce data — this
  only fills gaps when the document doesn't explicitly state worker counts.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from .boq_sanitizer import classify_work_category

logger = logging.getLogger(__name__)

# ── Workforce mapping ───────────────────────────────────────────────
# Each work category maps to (skilled_per_item, unskilled_per_item, supervisor_per_item)
# These are per-unit multipliers: for each item in this category, estimate N workers.
#
# Sources:
#   - South African construction industry benchmarks (CIDB)
#   - Labour intensity by trade (NHBRC guidelines)
#   - Typical crew composition ratios

_WORKFORCE_MAP: dict[str, tuple[float, float, float]] = {
    # (skilled_per_item, unskilled_per_item, supervisor_per_10_items)
    # Example: painting one item needs ~0.5 skilled (painter) + 0.5 unskilled + 0.1 supervisor

    "painting":              (0.5,  0.5,  0.1),
    # Painter (skilled) + helper (unskilled) + foreman oversight

    "tiling":                (0.5,  0.5,  0.1),
    # Tiler (skilled) + labourer (unskilled) + foreman oversight

    "plumbing":              (0.8,  0.3,  0.1),
    # Plumber (skilled) + assistant (unskilled). Higher skill ratio.

    "timber_carpentry":      (0.7,  0.4,  0.1),
    # Carpenter (skilled) + helper (unskilled). Moderate skill ratio.

    "demolition":            (0.2,  1.0,  0.15),
    # Demolition is labour-intensive. 1 unskilled + some skilled (supervisor/operator).

    "electrical":            (0.9,  0.2,  0.1),
    # Electrician (skilled) + assistant. Very high skill ratio.

    "roofing":               (0.6,  0.5,  0.15),
    # Roofer (skilled) + labourer (unskilled) + stronger supervision (safety).

    "masonry_brickwork":     (0.5,  0.6,  0.1),
    # Bricklayer (skilled) + labourer (unskilled). Balanced.

    "flooring":              (0.5,  0.4,  0.1),
    # Flooring installer (skilled) + helper (unskilled).

    "glazing":               (0.7,  0.3,  0.1),
    # Glazier (skilled) + assistant.

    "plastering":            (0.5,  0.5,  0.1),
    # Plasterer (skilled) + labourer (unskilled).

    "waterproofing":         (0.4,  0.5,  0.1),
    # Waterproofer (skilled) + labourer (unskilled).

    "steel_metalwork":       (0.8,  0.3,  0.1),
    # Welder/fabricator (skilled) + helper.

    "general_construction":  (0.4,  0.6,  0.1),
    # General works — balanced mix.
}


# ── Minimum workforce floor ─────────────────────────────────────────
# Even tiny jobs need minimum personnel
_MIN_WORKERS = 2      # At least 2 workers total
_MIN_SKILLED = 1      # At least 1 skilled
_MIN_UNSKILLED = 1    # At least 1 unskilled
_MIN_SUPERVISORS = 0  # Supervisors optional for very small jobs


def estimate_workforce(
    boq_items: List[Dict],
    classified_items: Optional[Dict[str, List[Dict]]] = None,
    work_category_filter: Optional[Dict[str, List[str]]] = None,
) -> Tuple[Dict[str, Any], str, List[str]]:
    """
    Estimate workforce requirements from classified BOQ items.

    Args:
        boq_items: List of BOQ item dicts with at least "description" field.
        classified_items: Pre-classified items (from classify_boq_items).
                          If None, classification is done here.

    Returns:
        (workforce_dict, confidence, reasoning_log):
          - workforce_dict: Dict with skilled_workers, unskilled_workers,
            supervisors, total_workers, work_categories (list of categories found),
            item_count (total items processed).
          - confidence: "High", "Medium", or "Low".
          - reasoning_log: List of human-readable explanations.
    """
    reasoning: List[str] = []

    # Classify items if not pre-classified
    if classified_items is None:
        from .boq_sanitizer import classify_boq_items
        classified_items = classify_boq_items(boq_items, work_category_filter)

    categories_found: List[str] = []
    total_items = 0

    # Aggregate workforce estimates per category
    total_skilled: float = 0.0
    total_unskilled: float = 0.0
    total_supervisors: float = 0.0

    for category, items in sorted(classified_items.items()):
        if category == "unclassified":
            continue  # Skip unclassified for estimation (they're likely noise)

        categories_found.append(category)
        item_count = len(items)
        total_items += item_count

        # Get multipliers for this category (default to general_construction if unknown)
        skilled_per, unskilled_per, supervisor_per_10 = _WORKFORCE_MAP.get(
            category, (0.4, 0.6, 0.1)
        )

        cat_skilled = skilled_per * item_count
        cat_unskilled = unskilled_per * item_count
        cat_supervisors = supervisor_per_10 * (item_count / 10.0)

        total_skilled += cat_skilled
        total_unskilled += cat_unskilled
        total_supervisors += cat_supervisors

        reasoning.append(
            f"Category '{category}': {item_count} items → "
            f"{cat_skilled:.1f} skilled, {cat_unskilled:.1f} unskilled, "
            f"{cat_supervisors:.1f} supervisors "
            f"(skilled_per={skilled_per}, unskilled_per={unskilled_per}, "
            f"supervisor_per_10={supervisor_per_10})"
        )

    # Apply minimum floors
    final_skilled = max(_MIN_SKILLED, round(total_skilled))
    final_unskilled = max(_MIN_UNSKILLED, round(total_unskilled))
    final_supervisors = max(_MIN_SUPERVISORS, round(total_supervisors))
    final_total = final_skilled + final_unskilled + final_supervisors

    # Ensure at least minimum total
    if final_total < _MIN_WORKERS:
        final_total = _MIN_WORKERS
        if final_skilled < 1:
            final_skilled = 1
        if final_unskilled < 1:
            final_unskilled = 1
        final_total = final_skilled + final_unskilled + final_supervisors
        reasoning.append(f"Applied minimum workforce floor: at least {_MIN_WORKERS} workers")

    # Determine confidence
    confidence = _determine_confidence(categories_found, total_items)

    if not categories_found:
        confidence = "Low"
        reasoning.append("No recognised work categories found. Workforce estimate is a default minimum.")

    reasoning.append(
        f"Final estimate: {final_skilled} skilled, {final_unskilled} unskilled, "
        f"{final_supervisors} supervisors, {final_total} total "
        f"(confidence: {confidence})"
    )

    workforce_dict: Dict[str, Any] = {
        "skilled_workers": final_skilled,
        "unskilled_workers": final_unskilled,
        "supervisors": final_supervisors,
        "total_workers": final_total,
        "work_categories": categories_found,
        "item_count": total_items,
    }

    logger.info("[WORKFORCE_INFERENCE] Estimated workforce: %s (confidence=%s)",
                workforce_dict, confidence)

    return workforce_dict, confidence, reasoning


def _determine_confidence(categories: List[str], total_items: int) -> str:
    """Determine confidence level for workforce estimate."""
    if not categories:
        return "Low"
    if total_items >= 10 and len(categories) >= 3:
        return "High"
    if total_items >= 5 and len(categories) >= 2:
        return "Medium"
    return "Low"


def get_workforce_explanation(
    workforce: Dict[str, Any],
    confidence: str,
    reasoning: List[str],
) -> Dict[str, Any]:
    """
    Package workforce estimate with explainability metadata.

    Returns a dict that can be stored in the result alongside the workforce data.
    This makes the estimation process fully transparent.
    """
    return {
        "workforce": workforce,
        "confidence": confidence,
        "reasoning": reasoning,
        "method": "boq_category_inference",
        "explanation": (
            "Workforce estimated by classifying BOQ line items into work categories "
            "(e.g. painting, plumbing, electrical) and applying per-category "
            "skill-to-labour ratios. Each category maps to expected "
            "skilled/unskilled/supervisor counts per item. Estimates are floor-capped "
            "to minimum viable crew sizes."
        ),
    }
