"""
BOQ Sanitization Layer — Filters out non-work rows from extracted BOQ items.

Removes:
- metadata rows (VAT REG, CONTACT PERSON, closing dates)
- legal/procurement sections
- empty rows
- contact/admin rows
- scoring tables
- form labels

Keeps only actionable work items like:
- "Prepare and paint external walls"
- "Replace shower panels"
- "Install wooden flooring"

Each filtered row records WHY it was removed (explainable filtering).
"""
import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Exclusion patterns ──────────────────────────────────────────────

# Exact-match labels (case-insensitive trimmed description matches one of these)
_ADMIN_LABELS: set[str] = {
    "vat registration nr",
    "vat registration no",
    "vat reg nr",
    "contact person",
    "contact",
    "closing date",
    "closing date and time",
    "bid number",
    "tender number",
    "tender ref",
    "reference number",
    "project number",
}

# Substring patterns — if ANY of these appears in the lowercase description,
# the row is considered non-work and removed.
_EXCLUSION_SUBSTRINGS: list[str] = [
    "vat registration",
    "vat reg",
    "contact person",
    "contact details",
    "closing date",
    "closing time",
    "bid no",
    "tender no",
    "reference no",
    "project no",
    "issuing office",
    "procurement",
    "legal requirement",
    "terms and conditions",
    "conditions of contract",
    "sbd ",
    "standard bid document",
    "preferential procurement",
    "bbbeee",
    "b-bbee",
    "broad-based black",
    "eligibility",
    "declaration of interest",
    "certificate of",
    "signed by",
    "date signed",
    "price schedule",
    "form of offer",
    "scoring",
    "evaluation criteria",
    "functionality",
    "weighted points",
    "page ",
    "signature",
    "compulsory",
    "clarification meeting",
    "site inspection",
    "enquiries",
    "fax number",
    "tel number",
    "postal address",
    "physical address",
    "company registration",
    "ck number",
    "vat number",
    "tax number",
]

# Substring patterns for form labels and procurement admin text
_FORM_LABEL_SUBSTRINGS: list[str] = [
    "form of offer",
    "offer to tender",
    "tender offer",
    "declaration by",
    "declaration of",
    "certificate of",
    "bid declaration",
    "bidder's declaration",
    "bidder declaration",
    "sbd ",
    "standard bid",
    "preferential procurement",
    "bbbeee",
    "b-bbee",
    "broad-based black",
    "eligibility",
    "evaluation criteria",
    "functionality criteria",
    "weighted points",
    "scoring sheet",
    "scoring criteria",
    "evaluation sheet",
    "functionality scoring",
    "price schedule",
    "pricing schedule",
    "bill of quantities",
    "schedule of quantities",
    "priced bill",
    "summary of quantities",
    "treasury",
    "national treasury",
    "provincial treasury",
    "municipal",
    "invitation to bid",
    "request for proposal",
    "rfp",
    "rfq",
    "request for quotation",
    "expression of interest",
    "eoi",
    "terms of reference",
    "specification",
    "scope of work",
    "closing",
    "submission",
]

# Description that are ONLY non-alphabetic (numbers, punctuation, whitespace)
_ONLY_NON_ALPHA_RE = re.compile(r"^[^a-zA-Z]*$")

# Scoring table patterns — descriptions that look like scoring criteria
_SCORING_RE = re.compile(
    r"(?:score|points|weight|criteria|rating|mark)\s*(?::|for|per|\d)",
    re.IGNORECASE,
)

# Procurement form labels
_FORM_LABELS: set[str] = {
    "item",
    "description",
    "quantity",
    "qty",
    "unit",
    "rate",
    "amount",
    "total",
    "subtotal",
    "grand total",
    "vat",
    "excl vat",
    "incl vat",
    "total excl vat",
    "total incl vat",
    "total ex vat",
    "total inc vat",
}

# ── Work category detection keywords ────────────────────────────────

_WORK_CATEGORIES: dict[str, list[str]] = {
    "painting": [
        "paint", "painting", "painter", "coat", "undercoat",
        "primer", "emulsion", "enamel", "varnish", "stain",
        "wall paint", "ceiling paint", "spray paint",
    ],
    "tiling": [
        "tile", "tiling", "tiler", "ceramic", "porcelain",
        "grout", "floor tile", "wall tile",
    ],
    "plumbing": [
        "plumb", "pipe", "piping", "drain", "drainage",
        "water supply", "sewer", "sewage", "tap", "faucet",
        "basin", "sink", "toilet", "cistern", "geyser",
        "water heater", "valve", "pump", "irrigation",
    ],
    "timber_carpentry": [
        "timber", "wooden", "carpent", "joinery", "skirting",
        "architrave", "door frame", "window frame", "cupboard",
        "cabinet", "shelf", "shelving", "truss", "rafter",
    ],
    "demolition": [
        "demolish", "demolition", "remove", "removal",
        "strip", "stripping", "clear", "clearing",
        "break out", "breaking out", "excavate",
    ],
    "electrical": [
        "electri", "cable", "wiring", "conduit", "switch",
        "socket", "light", "lighting", "luminaire",
        "db board", "distribution board", "breaker",
        "generator", "ups", "earthing", "cable tray",
    ],
    "roofing": [
        "roof", "roofing", "truss", "fascia", "soffit",
        "gutter", "downpipe", "rainwater", "ceiling board",
    ],
    "masonry_brickwork": [
        "brick", "block", "masonry", "plaster", "cement",
        "mortar", "concrete", "paving", "pave",
    ],
    "flooring": [
        "floor", "flooring", "screed", "vinyl", "laminate",
        "carpet", "polish", "grinding",
    ],
    "glazing": [
        "glass", "glazing", "window pane", "mirror",
        "aluminium frame", "aluminum frame", "sliding door",
    ],
    "plastering": [
        "plaster", "render", "screed",
    ],
    "waterproofing": [
        "waterproof", "damp proof", "sealant", "sealing",
    ],
    "steel_metalwork": [
        "steel", "metal", "welding", "weld", "balustrade",
        "handrail", "gate", "fence", "railing", "structural steel",
    ],
    "general_construction": [
        "general", "construction", "building", "renovate",
        "refurbish", "repair", "maintenance", "install",
        "supply and", "fixing", "fix",
    ],
}

construction_sector_library: dict[str, list[str]] = _WORK_CATEGORIES

_NON_CONSTRUCTION_SECTORS = {
    "it",
    "it_services",
    "information_technology",
    "professional_services",
    "professional services",
    "cleaning",
}


def get_work_category_filter(sector: Optional[str]) -> Dict[str, List[str]]:
    """
    Build the deterministic work-category filter for a detected sector.

    IT, professional services, and cleaning tenders must not borrow
    construction trade tags for BOQ/workforce inference.
    """
    normalized = (sector or "").strip().lower()
    if normalized in _NON_CONSTRUCTION_SECTORS:
        return {
            "exclude": list(construction_sector_library.keys()),
            "source": "sector_first_constraint",
        }
    return {"exclude": [], "source": "sector_first_constraint"}


def sanitize_boq_items(
    items: List[Dict],
) -> Tuple[List[Dict], List[str]]:
    """
    Sanitize a list of BOQ items by removing non-work rows.

    Args:
        items: List of BOQ item dicts with at least a "description" field.

    Returns:
        (clean_items, removal_log):
          - clean_items: Filtered list containing only actionable work items.
          - removal_log: Human-readable list explaining what was removed.
    """
    clean: List[Dict] = []
    removal_log: List[str] = []

    for idx, item in enumerate(items):
        desc = (item.get("description") or "").strip()

        # Skip empty descriptions
        if not desc:
            removal_log.append(f"Row {idx}: removed (empty description)")
            continue

        # Skip non-alphabetic descriptions (numbers only, punctuation)
        if _ONLY_NON_ALPHA_RE.match(desc):
            removal_log.append(f"Row {idx}: removed (non-alphabetic: '{desc[:60]}')")
            continue

        desc_lower = desc.lower().strip()

        # Skip exact admin labels
        if desc_lower in _ADMIN_LABELS:
            removal_log.append(f"Row {idx}: removed (admin label: '{desc[:80]}')")
            continue

        # Skip form labels
        if desc_lower in _FORM_LABELS:
            removal_log.append(f"Row {idx}: removed (form label: '{desc[:80]}')")
            continue

        # Skip scoring criteria
        if _SCORING_RE.search(desc_lower):
            removal_log.append(f"Row {idx}: removed (scoring criteria: '{desc[:80]}')")
            continue

        # Skip exclusion substrings
        excluded = False
        for pattern in _EXCLUSION_SUBSTRINGS:
            if pattern in desc_lower:
                removal_log.append(f"Row {idx}: removed (contains '{pattern}': '{desc[:80]}')")
                excluded = True
                break
        if excluded:
            continue

        # Skip form label / procurement admin substrings
        excluded = False
        for pattern in _FORM_LABEL_SUBSTRINGS:
            if pattern in desc_lower:
                removal_log.append(f"Row {idx}: removed (form label '{pattern}': '{desc[:80]}')")
                excluded = True
                break
        if excluded:
            continue

        # Passed all checks — this is a work item
        clean.append(item)

    logger.info(
        "[BOQ_SANITIZER] Sanitized %d items → %d work items (%d removed)",
        len(items), len(clean), len(items) - len(clean),
    )
    if removal_log:
        for log_entry in removal_log:
            logger.debug("[BOQ_SANITIZER] %s", log_entry)

    return clean, removal_log


def classify_work_category(
    description: str,
    work_category_filter: Optional[Dict[str, List[str]]] = None,
) -> Optional[str]:
    """
    Classify a work description into a work category.

    Uses keyword matching. Returns the most specific matching category,
    or None if the description doesn't match any known category.

    The matching order matters — more specific categories are checked first.
    """
    if not description:
        return None

    desc_lower = description.lower().strip()
    excluded = set((work_category_filter or {}).get("exclude") or [])

    # Check each category's keywords in order
    for category, keywords in _WORK_CATEGORIES.items():
        if category in excluded:
            continue
        for keyword in keywords:
            if keyword in desc_lower:
                logger.debug(
                    "[BOQ_SANITIZER] Classified '%s' → %s (matched keyword: '%s')",
                    description[:60], category, keyword,
                )
                return category

    return None


def classify_boq_items(
    items: List[Dict],
    work_category_filter: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, List[Dict]]:
    """
    Classify all BOQ items into work categories.

    Returns a dict mapping category_name → list of items in that category.
    Items that don't match any category are placed under 'unclassified'.
    """
    classified: Dict[str, List[Dict]] = {}

    for item in items:
        desc = item.get("description") or ""
        category = classify_work_category(desc, work_category_filter) or "unclassified"

        if category not in classified:
            classified[category] = []
        classified[category].append(item)

    return classified
