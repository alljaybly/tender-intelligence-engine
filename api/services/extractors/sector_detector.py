"""
Sector detection via keyword matching in tender document text.

Detects common South African tender sectors:
cleaning, construction, electrical, security, gardening,
it_services, maintenance, supply, general.
"""
import logging
import re
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Sector keywords: (sector_name, weighted keywords)
_SECTOR_KEYWORDS = {
    "cleaning": [
        "cleaning", "janitorial", "sanitary", "hygiene", "washroom",
        "floor care", "carpet cleaning", "window cleaning", "disinfection",
        "office cleaning", "industrial cleaning", "deep clean",
    ],
    "construction": [
        "construction", "building", "civil works", "road", "bridge",
        "earthworks", "excavation", "concrete", "steel", "structural",
        "paving", "trenching", "foundation", "renovation", "rehabilitation",
    ],
    "electrical": [
        "electrical", "electrification", "cabling", "wiring", "substation",
        "transformer", "generator", "solar", "photovoltaic", "lighting",
        "switchgear", "distribution board", "power supply",
    ],
    "security": [
        "security", "guard", "patrol", "access control", "cctv",
        "surveillance", "alarm", "perimeter", "armed response",
        "security services", "protect",
    ],
    "gardening": [
        "gardening", "landscaping", "lawn", "tree", "horticulture",
        "irrigation", "pruning", "weed", "grass cutting",
    ],
    "it_services": [
        "it services", "information technology", "software", "hardware",
        "network", "cyber", "server", "cloud", "website", "web development",
        "it support", "managed services", "digital",
    ],
    "professional_services": [
        "professional services", "consulting services", "consultancy",
        "advisory services", "feasibility study", "design services",
        "project management", "audit services", "legal services",
        "engineering services", "quantity surveying",
    ],
    "maintenance": [
        "maintenance", "repair", "servicing", "upkeep", "facilities management",
        "preventative maintenance", "planned maintenance",
    ],
    "supply": [
        "supply and delivery", "supply of", "provision of", "furniture",
        "equipment supply", "stationery", "consumables", "personal protective equipment",
        "ppe", "uniform", "tools and equipment",
    ],
    "general": [
        "general services", "training", "logistics",
        "transport", "freight", "catering", "event management",
    ],
}

_SECTOR_FIRST_PRIORITY = ("it_services", "professional_services", "cleaning")
_TITLE_LINE_LIMIT = 12
_SCOPE_SECTION_RE = re.compile(
    r"\b(?:scope\s+of\s+work|scope|terms\s+of\s+reference|tor|"
    r"description\s+of\s+services|required\s+services)\b",
    re.IGNORECASE,
)
_NEXT_HEADING_RE = re.compile(
    r"^\s*(?:\d+\.?\s*)?(?:pricing|bill\s+of\s+quantities|boq|"
    r"evaluation|eligibility|submission|returnable|contract\s+period|"
    r"closing|special\s+conditions)\b",
    re.IGNORECASE,
)


def _extract_title_and_scope_text(text: str) -> str:
    """Return the title and scope/TOR text used for sector-first matching."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title_lines = lines[:_TITLE_LINE_LIMIT]

    scope_lines = []
    in_scope = False
    for line in lines:
        if _SCOPE_SECTION_RE.search(line):
            in_scope = True
        elif in_scope and _NEXT_HEADING_RE.search(line):
            break

        if in_scope:
            scope_lines.append(line)
            if len(" ".join(scope_lines)) > 2500:
                break

    return "\n".join(title_lines + scope_lines)


def detect_sector_first(text: str) -> Optional[str]:
    """
    Run the deterministic title/scope pre-scan before BOQ extraction.

    Only the constrained non-construction sectors are allowed to override the
    broader full-document detector, preventing construction terms in BOQs from
    biasing the sector.
    """
    scan_text = _extract_title_and_scope_text(text)
    if not scan_text.strip():
        return None

    lower_text = scan_text.lower()
    scores: Dict[str, int] = {}
    for sector in _SECTOR_FIRST_PRIORITY:
        score = 0
        for keyword in _SECTOR_KEYWORDS.get(sector, []):
            score += len(re.findall(re.escape(keyword), lower_text))
        if score > 0:
            scores[sector] = score

    if not scores:
        return None

    best_sector = max(scores, key=scores.get)
    logger.info("[SECTOR] Sector-first detected sector=%s score=%d", best_sector, scores[best_sector])
    return best_sector


def detect_sector(text: str) -> Optional[str]:
    """
    Analyse document text and return the most likely sector.

    Uses weighted keyword matching — each keyword match contributes
    to a sector score.  Returns the sector with the highest score,
    or None if no sector is recognisable.
    """
    if not text or not text.strip():
        logger.debug("[SECTOR] Empty text, cannot detect sector")
        return None

    sector_first = detect_sector_first(text)
    if sector_first:
        return sector_first

    lower_text = text.lower()
    scores: dict[str, int] = {}

    for sector, keywords in _SECTOR_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            # Count occurrences (not just presence)
            count = len(re.findall(re.escape(keyword), lower_text))
            score += count
        if score > 0:
            scores[sector] = score
            logger.debug("[SECTOR] %s score=%d", sector, score)

    if not scores:
        logger.info("[SECTOR] No sector detected in document")
        return None

    # Return highest-scoring sector
    best_sector = max(scores, key=scores.get)
    logger.info(
        "[SECTOR] Detected sector=%s score=%d",
        best_sector, scores[best_sector],
    )
    return best_sector
