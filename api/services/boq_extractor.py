"""
BOQ Engine v2 — Deterministic Bill of Quantities extraction with table intelligence.

Pipeline:
  1. Locate BOQ tables (find all tables in PDF)
  2. Detect table headers (identify column types)
  3. Map columns (map to BOQ fields)
  4. Detect hierarchy (sections, nested items, indentation)
  5. Extract rows (with evidence)
  6. Validate quantities (positive numbers, reasonable ranges)
  7. Validate units (recognised UOMs)
  8. Validate currency (evidence-based, never default to ZAR)
  9. Validate totals (subtotal + VAT = grand total)
  10. Attach evidence (page, bbox, confidence, source text)

Rejected table types (with explanation):
  - Telephone lists
  - Address tables
  - Contact lists
  - Tender notices
  - Award notices
  - Company directories
  - Legal clauses
"""
from __future__ import annotations
import logging
import re
import io
from typing import Any, Dict, List, Optional, Tuple

from ..schemas.boq import (
    BOQItem, BOQItemEvidence, BOQResult, BOQTotals,
    BOQColumnMapping, BOQTableMetadata, BOQTableRejection,
    BOQValidationResult,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Known Column Headers
# ═══════════════════════════════════════════════════════════════════════

HEADER_MAP: Dict[str, List[str]] = {
    "item_no": ["item", "no", "item no", "item no.", "item #", "#", "ref", "ref.", "number", "item number"],
    "description": ["description", "item description", "work", "scope", "scope of work", "particulars", "details", "specification"],
    "specification": ["specification", "spec", "technical spec", "standard", "material spec"],
    "quantity": ["quantity", "qty", "qnty", "quant", "qty.", "measured quantity", "total quantity"],
    "unit": ["unit", "uom", "measure", "unit of measure", "meas", "units"],
    "rate": ["rate", "price", "unit price", "rate/unit", "rate per unit", "unit rate", "price per unit"],
    "amount": ["amount", "total", "extended", "extended amount", "amount (zar)", "amount (z ar)", "total amount", "cost"],
    "currency": ["currency", "curr", "ccy", "currency code"],
    "section": ["section", "heading", "group", "division", "part"],
    "notes": ["notes", "remarks", "comment", "note", "ref", "reference"],
}

# Key header words that identify a price column
_PRICE_HEADER_WORDS = {"rate", "price", "amount", "total", "unit price", "cost"}

# Recognised units of measure
_KNOWN_UNITS = {
    "m", "m2", "m3", "m²", "m³", "sqm", "cum",
    "mm", "cm", "km",
    "kg", "kg.", "kgs", "ton", "tonnes", "t",
    "l", "litre", "litres",
    "hr", "hrs", "hour", "hours",
    "day", "days", "week", "weeks", "month", "months", "year", "years",
    "each", "ea", "per", "nr", "no", "nos", "pcs", "pieces",
    "ls", "lump sum", "item", "sum",
    "m2/day", "m3/day",
    "%", "percent",
}

# Non-BOQ table type detection patterns
_NON_BOQ_HEADER_PATTERNS: List[Tuple[str, str]] = [
    ("TenderNotice", r"(?:tender\s*(?:notice|advert)|invitation\s*to\s*bid)"),
    ("AwardNotice", r"(?:award\s*(?:notice|letter)|letter\s*of\s*award)"),
    ("ContactList", r"(?:contact|telephone|phone|tel|fax|email|website|cell)"),
    ("AddressTable", r"(?:address|postal\s*code|street|physical)"),
    ("Directory", r"(?:company\s*name|directors|members|partners|registration)"),
    ("LegalClause", r"(?:clause|section|regulation|act\s*no|policy)"),
]


def _matches_non_boq_pattern(text: str) -> Optional[str]:
    """Check if header text matches a non-BOQ pattern. Returns table_type or None."""
    lower = text.lower()
    for table_type, pattern in _NON_BOQ_HEADER_PATTERNS:
        if re.search(pattern, lower):
            return table_type
    return None


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

_NUMERIC_RE = re.compile(r"^[\d,.\s\-]+$")
_CURRENCY_RE = re.compile(r"^[Rr$£€¥]?\s*[\d,.\s]+$")


def _parse_float(raw: Any) -> Optional[float]:
    """Safely parse a number from a cell / string."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    cleaned = re.sub(r"[Rr$£€¥\s,\-]", "", str(raw).strip().replace("\xa0", " "))
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _is_numeric(val: Any) -> bool:
    """Check if a cell value looks numeric."""
    if val is None:
        return False
    if isinstance(val, (int, float)):
        return True
    s = str(val).strip().replace("\xa0", " ")
    if not s:
        return False
    return bool(_CURRENCY_RE.match(s) or _NUMERIC_RE.match(s))


def _parse_page_range(page_range: Optional[str], max_pages: int) -> List[int]:
    """Convert user-supplied page range spec to list of 1-indexed page numbers."""
    if not page_range:
        return list(range(1, max_pages + 1))
    pages: List[int] = []
    for part in page_range.split(","):
        part = part.strip()
        if "-" in part:
            try:
                a, b = part.split("-", 1)
                start, end = int(a.strip()), int(b.strip())
                pages.extend(range(start, end + 1))
            except ValueError:
                continue
        else:
            try:
                pages.append(int(part))
            except ValueError:
                continue
    return sorted(set(p for p in pages if 1 <= p <= max_pages))


def _is_total_row(text: str) -> bool:
    """Detect if a description is a total/subtotal label."""
    lower = text.lower().strip()
    return lower in (
        "total", "subtotal", "grand total", "total brought forward",
        "total carried forward", "sub total",
        "vat", "total excl vat", "total incl vat",
        "total ex vat", "total inc vat",
        "total excluding vat", "total including vat",
        "excl vat", "incl vat",
    )


def _is_section_header(text: str) -> bool:
    """Detect if a row is a section header (all caps, no rates)."""
    lower = text.lower().strip()
    # Common section header patterns
    if lower.endswith(":") and len(text) > 5:
        return True
    # All caps with length > 3 (likely a section heading)
    if text.isupper() and len(text.strip()) > 3:
        return True
    return False


# ═══════════════════════════════════════════════════════════════════════
# Column Classification
# ═══════════════════════════════════════════════════════════════════════

def _classify_header(row: List[str]) -> Optional[BOQColumnMapping]:
    """
    Map column names to BOQ fields.
    Returns BOQColumnMapping or None if no meaningful columns found.
    """
    mapping = BOQColumnMapping()
    lowered = {i: str(c).strip().lower() for i, c in enumerate(row) if c is not None}
    matched = 0

    for field, aliases in HEADER_MAP.items():
        for idx, val in lowered.items():
            for alias in aliases:
                if val == alias or val.startswith(alias) or val.endswith(alias):
                    setattr(mapping, field, idx)
                    matched += 1
                    break

    if matched == 0:
        return None

    mapping.confidence = min(1.0, matched / len(HEADER_MAP) * 2)
    return mapping


def _has_price_column(mapping: BOQColumnMapping) -> bool:
    """Return True when mapping has rate or amount column."""
    return mapping.rate is not None or mapping.amount is not None


def _guess_mapping_from_data(data: List[List[str]]) -> Optional[BOQColumnMapping]:
    """
    When no header is detected, guess column roles by analysing
    the type of data in each column across multiple rows.
    """
    if not data or len(data) < 3:
        return None

    num_cols = max(len(r) for r in data)
    mapping = BOQColumnMapping()

    numeric_cols: List[int] = []
    text_cols: List[int] = []

    for col_idx in range(num_cols):
        numeric_count = 0
        text_count = 0
        for row in data[1:]:  # Skip first row (header)
            if col_idx < len(row) and row[col_idx] is not None:
                val = str(row[col_idx]).strip()
                if _is_numeric(val):
                    numeric_count += 1
                elif val:
                    text_count += 1

        if numeric_count > text_count and numeric_count >= 2:
            numeric_cols.append(col_idx)
        elif text_count > numeric_count:
            text_cols.append(col_idx)

    # Assign: first text col = description
    if text_cols:
        mapping.description = text_cols[0]
    if len(text_cols) > 1:
        mapping.specification = text_cols[1]

    # Assign numeric columns: first = qty, second = rate, third = amount
    numeric_cols.sort()
    for i, col_idx in enumerate(numeric_cols):
        if i == 0:
            mapping.quantity = col_idx
        elif i == 1:
            mapping.rate = col_idx
        elif i == 2:
            mapping.amount = col_idx

    mapping.confidence = 0.5
    return mapping


# ═══════════════════════════════════════════════════════════════════════
# Row Extraction
# ═══════════════════════════════════════════════════════════════════════

def _row_to_boq_item(
    row: List[str],
    mapping: BOQColumnMapping,
    page: int,
    bbox: Optional[str] = None,
    method: str = "pdfplumber_tables",
) -> Optional[BOQItem]:
    """Convert a table row to a BOQItem with evidence."""
    cleaned = [str(c).strip() for c in row if c is not None]
    if not cleaned or all(c == "" for c in cleaned):
        return None

    def _cell(idx: Optional[int]) -> Optional[str]:
        if idx is not None and idx < len(row) and row[idx] is not None:
            return str(row[idx]).strip()
        return None

    item_no = _cell(mapping.item_no)
    description = _cell(mapping.description) or ""
    specification = _cell(mapping.specification)
    quantity = _parse_float(_cell(mapping.quantity))
    unit = _cell(mapping.unit)
    rate = _parse_float(_cell(mapping.rate))
    amount = _parse_float(_cell(mapping.amount))
    currency = _cell(mapping.currency)
    section = _cell(mapping.section)
    notes = _cell(mapping.notes)

    # Skip empty rows
    if not description and item_no is None and quantity is None and amount is None:
        return None

    # Detect row type
    desc_lower = description.lower().strip()
    is_total = _is_total_row(desc_lower)
    is_section = _is_section_header(description) and quantity is None and rate is None
    is_subtotal = "subtotal" in desc_lower or "sub total" in desc_lower

    # Build evidence
    evidence = BOQItemEvidence(
        page=page,
        bbox=bbox,
        confidence=0.9 if rate is not None else 0.5,
        source_text=" | ".join(cleaned[:10]),
        extraction_method=method,
    )

    return BOQItem(
        item_no=item_no,
        description=description,
        specification=specification,
        quantity=quantity,
        unit=unit,
        rate=rate,
        amount=amount,
        currency=currency,
        section=section,
        notes=notes,
        is_subtotal=is_subtotal,
        is_total=is_total,
        is_section_header=is_section,
        evidence=evidence,
    )


# ═══════════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════════

def _validate_items(items: List[BOQItem]) -> BOQValidationResult:
    """Validate extracted BOQ items for quality."""
    issues: List[str] = []
    quantity_issues: List[str] = []
    unit_issues: List[str] = []
    currency_issues: List[str] = []
    total_issues: List[str] = []

    data_items = [i for i in items if not i.is_total and not i.is_subtotal]

    items_with_qty = sum(1 for i in data_items if i.quantity is not None)
    items_with_rate = sum(1 for i in data_items if i.rate is not None)
    items_with_amt = sum(1 for i in data_items if i.amount is not None)
    items_with_ccy = sum(1 for i in data_items if i.currency is not None)

    # Quantity validation
    for i, item in enumerate(data_items):
        if item.quantity is not None and item.quantity <= 0:
            quantity_issues.append(f"Item {item.item_no or i+1}: quantity <= 0 ({item.quantity})")
        if item.quantity is not None and item.quantity > 1_000_000:
            quantity_issues.append(f"Item {item.item_no or i+1}: unusually large quantity ({item.quantity})")

    # Unit validation
    for i, item in enumerate(data_items):
        if item.unit is not None and item.unit.lower() not in _KNOWN_UNITS:
            unit_issues.append(f"Item {item.item_no or i+1}: unknown unit '{item.unit}'")

    # Currency validation
    if items_with_ccy == 0:
        currency_issues.append("No currency detected on any item")

    # Total validation
    total_calculated = sum(i.amount or 0 for i in data_items if i.amount is not None)
    if total_calculated > 0:
        # Check if there's a total row that matches
        total_rows = [i for i in items if i.is_total]
        if total_rows:
            expected = total_rows[-1].amount
            if expected is not None and abs(expected - total_calculated) > 0.01:
                total_issues.append(
                    f"Total mismatch: calculated {total_calculated:.2f}, "
                    f"stated {expected:.2f} (diff: {abs(expected - total_calculated):.2f})"
                )

    return BOQValidationResult(
        quantity_valid=len(quantity_issues) == 0,
        unit_valid=len(unit_issues) == 0,
        currency_valid=len(currency_issues) == 0,
        total_valid=len(total_issues) == 0,
        items_with_quantities=items_with_qty,
        items_with_rates=items_with_rate,
        items_with_amounts=items_with_amt,
        items_with_currency=items_with_ccy,
        quantity_issues=quantity_issues,
        unit_issues=unit_issues,
        currency_issues=currency_issues,
        total_issues=total_issues,
    )


# ═══════════════════════════════════════════════════════════════════════
# Main BOQ Engine v2 Pipeline
# ═══════════════════════════════════════════════════════════════════════

def extract_from_pdf(file_path: str, extract_totals: bool = True,
                     page_range: Optional[str] = None) -> BOQResult:
    """
    BOQ Engine v2 — Extract BOQ data from a PDF file.

    Pipeline:
      1. Parse all pages with pdfplumber
      2. For each page, find all tables
      3. Classify each table as BOQ or non-BOQ
      4. For BOQ tables: detect headers, map columns, extract rows
      5. Validate extracted items
      6. Return structured result with evidence

    Args:
        file_path: Path to the PDF file.
        extract_totals: Whether to attempt extracting grand totals.
        page_range: Optional page range spec e.g. "1-3" or "1,3,5".

    Returns:
        BOQResult with extracted items, totals, confidence, and warnings.
    """
    import os
    import pdfplumber

    filename = os.path.basename(file_path)
    warnings: List[str] = []
    all_items: List[BOQItem] = []
    rejected_tables: List[BOQTableRejection] = []
    table_metadata: List[BOQTableMetadata] = []
    tables_detected = 0
    tables_accepted = 0
    tables_rejected = 0

    extraction_method = "boq_engine_v2"
    confidence = "Low"
    pages_to_process: List[int] = []
    hierarchy_levels: set = set()
    validation = BOQValidationResult()
    totals = BOQTotals()

    logger.info("[BOQ] BOQ Engine v2 starting for %s", filename)

    try:
        with pdfplumber.open(file_path) as pdf:
            max_pages = len(pdf.pages)
            pages_to_process = _parse_page_range(page_range, max_pages)

            for page_num in pages_to_process:
                page = pdf.pages[page_num - 1]

                # ── Step 1: Find all tables on page ────────────────
                tables = page.find_tables()
                if not tables:
                    logger.debug("[BOQ] Page %d: no tables found", page_num)
                    continue

                for table in tables:
                    tables_detected += 1
                    data = table.extract()
                    if not data or len(data) < 2:
                        continue

                    header_text = " ".join(str(c or "") for c in (data[0] if data else []))
                    bbox_str = str(table.bbox) if hasattr(table, 'bbox') else None

                    # ── Step 2: Check for non-BOQ patterns ────────
                    non_boq_type = _matches_non_boq_pattern(header_text)
                    if non_boq_type:
                        tables_rejected += 1
                        rejected_tables.append(BOQTableRejection(
                            page=page_num,
                            reason=f"Table matches non-BOQ pattern: {non_boq_type}",
                            evidence=header_text[:200],
                            table_type=non_boq_type,
                            header_text=header_text[:200],
                        ))
                        logger.info("[BOQ] Page %d: rejected table type=%s", page_num, non_boq_type)
                        continue

                    # ── Step 3: Classify header ─────────────────────
                    header_row = data[0]
                    mapping = _classify_header(header_row)

                    if mapping is None:
                        # Try guessing from data
                        mapping = _guess_mapping_from_data(data)
                        if mapping is None or not _has_price_column(mapping):
                            tables_rejected += 1
                            rejected_tables.append(BOQTableRejection(
                                page=page_num,
                                reason="Could not map any column to BOQ fields",
                                evidence=f"No price columns found. Header: {header_text[:200]}",
                                table_type="unstructured",
                                header_text=header_text[:200],
                            ))
                            continue

                    if not _has_price_column(mapping):
                        tables_rejected += 1
                        rejected_tables.append(BOQTableRejection(
                            page=page_num,
                            reason="Table header lacks price columns (rate/amount)",
                            evidence=f"Header: {header_text[:200]}",
                            table_type="non_price",
                            header_text=header_text[:200],
                        ))
                        continue

                    # ── Step 4: Accept as BOQ table → extract rows ──
                    tables_accepted += 1
                    start_row = 1 if mapping.confidence > 0 else 0
                    rows_extracted = 0
                    rows_rejected = 0
                    current_section: Optional[str] = None

                    for row_data in data[start_row:]:
                        row = [str(c).strip() for c in (row_data or [])]
                        item = _row_to_boq_item(
                            row, mapping, page_num,
                            bbox=bbox_str,
                            method=extraction_method,
                        )

                        if item is None:
                            rows_rejected += 1
                            continue

                        # Track section headers
                        if item.is_section_header:
                            current_section = item.description
                            continue  # Don't add section header as an item

                        # Assign section
                        if current_section and not item.section:
                            item.section = current_section

                        # Track hierarchy from item_no
                        if item.item_no:
                            levels = item.item_no.count(".")
                            if item.hierarchy_level is None:
                                item.hierarchy_level = levels
                            hierarchy_levels.add(levels)

                        # Skip total rows (handled separately) unless extracting
                        if item.is_total and not extract_totals:
                            rows_rejected += 1
                            continue

                        all_items.append(item)
                        rows_extracted += 1

                    table_metadata.append(BOQTableMetadata(
                        page=page_num,
                        bbox=bbox_str,
                        columns_mapped=len([v for v in [
                            mapping.item_no, mapping.description, mapping.quantity,
                            mapping.rate, mapping.amount
                        ] if v is not None]),
                        rows_extracted=rows_extracted,
                        rows_rejected=rows_rejected,
                        hierarchy_levels=len(hierarchy_levels),
                        mapping=mapping,
                    ))

            # ── Step 5: Calculate totals ──────────────────────────
            data_items = [i for i in all_items if not i.is_total and not i.is_subtotal]
            subtotal = sum(i.amount or 0 for i in data_items if i.amount is not None)
            total_before_vat: Optional[float] = subtotal if subtotal > 0 else None

            # Look for explicit VAT and total rows
            vat: Optional[float] = None
            total_incl: Optional[float] = None
            for item in all_items:
                desc = (item.description or "").lower().strip()
                if desc == "vat" or "vat" in desc:
                    vat = item.amount
                if desc in ("total incl vat", "total including vat", "grand total"):
                    total_incl = item.amount

            totals = BOQTotals(
                subtotal=subtotal if subtotal > 0 else None,
                total_before_vat=total_before_vat,
                vat=vat,
                total_incl_vat=total_incl,
                page_count=len(pages_to_process),
                calculated_from_items=len(data_items) > 0,
            )

            # ── Step 6: Validate ─────────────────────────────────
            validation = _validate_items(all_items)
            if validation.quantity_issues:
                for issue in validation.quantity_issues[:5]:
                    warnings.append(f"[BOQ_VALIDATION] {issue}")
            if validation.unit_issues:
                for issue in validation.unit_issues[:5]:
                    warnings.append(f"[BOQ_VALIDATION] {issue}")
            if validation.total_issues:
                for issue in validation.total_issues[:3]:
                    warnings.append(f"[BOQ_VALIDATION] {issue}")

            # ── Determine confidence ─────────────────────────────
            if len(data_items) >= 3 and validation.items_with_rates >= len(data_items) * 0.5:
                confidence = "High"
            elif len(data_items) >= 1:
                confidence = "Medium"
            else:
                confidence = "Low"
                if tables_detected > 0 and tables_accepted == 0:
                    warnings.append("Tables were found but none passed BOQ validation")
                elif tables_detected == 0:
                    warnings.append("No tables found in document")

            logger.info(
                "[BOQ] BOQ Engine v2 complete: %d tables (%d accepted, %d rejected), "
                "%d items, confidence=%s",
                tables_detected, tables_accepted, tables_rejected,
                len(data_items), confidence,
            )

    except Exception as e:
        logger.exception("[BOQ] BOQ Engine v2 failed: %s", e)
        warnings.append(f"BOQ Engine v2 failed: {e}")
        extraction_method = "boq_engine_v2_failed"

    return BOQResult(
        filename=filename,
        page_count=len(pages_to_process),
        items=all_items,
        totals=totals,
        extraction_method=extraction_method,
        confidence=confidence,
        tables_detected=tables_detected,
        tables_accepted=tables_accepted,
        tables_rejected=tables_rejected,
        rejected_tables=rejected_tables,
        table_metadata=table_metadata,
        hierarchy_levels=max(len(hierarchy_levels), 0),
        validation=validation,
        warnings=warnings,
    )
