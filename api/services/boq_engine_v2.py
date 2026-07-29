"""
BOQ Engine v2 — Enterprise Bill of Quantities Extraction.

This engine distinguishes TRUE BOQ from general document text.

Pipeline:
  1. Table Detection (pdfplumber tables + Camelot)
  2. Table Classification (TRUE BOQ vs rejection)
  3. Column Mapping & Header Recognition
  4. Row Extraction (with confidence, source page, extraction method)
  5. Rejection Filtering (phone, address, registration, dates, etc.)
  6. Hierarchy Detection (sections, subsections, indentation)
  7. Validation (quantities, units, currency, totals)
  8. Evidence Attachment (page, bbox, confidence, source text)

If no BOQ exists: returns "No BOQ detected" — never invents data.
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
from .entity_classifier import classify_entity, EntityType

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

# Non-BOQ table type detection
_NON_BOQ_PATTERNS: Dict[str, str] = {
    "TenderNotice": r"(?:tender\s*(?:notice|advert)|invitation\s*to\s*bid)",
    "AwardNotice": r"(?:award\s*(?:notice|letter)|letter\s*of\s*award)",
    "ContactList": r"(?:contact|telephone|phone|tel|fax|email|website|cell)",
    "AddressTable": r"(?:address|postal\s*code|street|physical)",
    "Directory": r"(?:company\s*name|directors|members|partners|registration)",
    "LegalClause": r"(?:clause|section|regulation|act\s*no|policy)",
    "ScheduleDates": r"(?:milestone|schedule|timeline|delivery\s*date|completion\s*date)",
    "OrganisationList": r"(?:organisation|organization|department|division|unit\s*name)",
}


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
        "carried forward", "brought forward",
    )


def _is_section_header(text: str) -> bool:
    """Detect if a row is a section header (all caps, no rates)."""
    lower = text.lower().strip()
    if lower.endswith(":") and len(text) > 5:
        return True
    if text.isupper() and len(text.strip()) > 3:
        return True
    return False


def _table_text_to_string(rows: List[List[str]]) -> str:
    """Convert table rows to a single string for classification."""
    parts = []
    for row in rows[:20]:  # First 20 rows max
        parts.append(" ".join(str(c) for c in row if c is not None))
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════
# Table Classification — TRUE BOQ vs Rejection
# ═══════════════════════════════════════════════════════════════════════

def _classify_table_type(rows: List[List[str]]) -> Tuple[bool, Optional[str], str]:
    """
    Classify whether a table is TRUE BOQ or non-BOQ content.
    
    Returns: (is_boq, reject_reason, table_type)
    """
    if not rows or len(rows) < 2:
        return False, "Table has fewer than 2 rows", "EmptyTable"

    # Check header/first row against non-BOQ patterns
    first_row_text = " ".join(str(c) for c in rows[0] if c is not None).lower()
    for table_type, pattern in _NON_BOQ_PATTERNS.items():
        if re.search(pattern, first_row_text):
            return False, f"Table header matches non-BOQ pattern: {table_type}", table_type

    # Check all rows for non-BOQ content
    full_text = _table_text_to_string(rows)
    
    # Check for telephone numbers
    if re.search(r"(?:tel|phone|fax|mobile|cell)\s*[:：]", full_text, re.IGNORECASE):
        return False, "Table contains contact/telephone information", "ContactList"

    # Check for addresses
    if re.search(r"(?:address|postal\s*code|p\.?\s*o\.?\s*box)", full_text, re.IGNORECASE):
        return False, "Table contains address information", "AddressTable"

    # Check for dates-only (no prices)
    date_count = len(re.findall(r"\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2}", full_text))
    if date_count >= 3:
        numeric_cells = sum(1 for row in rows for c in row if c is not None and _is_numeric(c))
        if numeric_cells <= date_count:
            return False, "Table contains primarily dates, not prices", "ScheduleDates"

    # Check for organisation/entity lists
    org_pattern = re.compile(r"(?:organisation|organization|ministry|department|division)\s*:", re.IGNORECASE)
    if org_pattern.search(full_text):
        rate_count = sum(1 for row in rows for c in row if c is not None and _parse_float(c) is not None and float(_parse_float(c)) > 100)
        if rate_count <= 1:
            return False, "Table appears to be organisation list without pricing", "OrganisationList"

    # Check for price columns (strong BOQ signal)
    has_price_column = False
    for row in rows[:3]:  # Check first 3 rows for price headers
        row_text = " ".join(str(c).lower() for c in row if c is not None)
        if any(word in row_text for word in ["rate", "price", "amount", "unit price", "extended", "total amount", "cost"]):
            has_price_column = True
            break

    if not has_price_column:
        # Check if there are numeric values in multiple columns (potential BOQ)
        numeric_row_count = 0
        for row in rows[1:]:  # Skip header
            numeric_cells = sum(1 for c in row if c is not None and _is_numeric(c))
            if numeric_cells >= 2:
                numeric_row_count += 1
        
        if numeric_row_count < 2:
            return False, "Table lacks price columns and has insufficient numeric data", "NonBOQData"

    return True, None, "BOQ"


# ═══════════════════════════════════════════════════════════════════════
# Column Classification
# ═══════════════════════════════════════════════════════════════════════

def _classify_header(row: List[str]) -> Optional[BOQColumnMapping]:
    """Map column names to BOQ fields."""
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

    mapping.confidence = min(1.0, matched / max(1, len(HEADER_MAP) * 0.3))
    return mapping


def _has_price_column(mapping: BOQColumnMapping) -> bool:
    """Return True when mapping has rate or amount column."""
    return mapping.rate is not None or mapping.amount is not None


def _guess_mapping_from_data(data: List[List[str]]) -> Optional[BOQColumnMapping]:
    """Guess column roles by analysing data types when no header is detected."""
    if not data or len(data) < 3:
        return None

    num_cols = max(len(r) for r in data)
    mapping = BOQColumnMapping()

    numeric_cols: List[int] = []
    text_cols: List[int] = []

    for col_idx in range(num_cols):
        numeric_count = 0
        text_count = 0
        for row in data[1:]:  # Skip first row
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

    if text_cols:
        mapping.description = text_cols[0]
    if len(text_cols) > 1:
        mapping.specification = text_cols[1]

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
# Entity Classification Filter
# ═══════════════════════════════════════════════════════════════════════

_REJECTED_ENTITY_TYPES = {
    EntityType.TELEPHONE,
    EntityType.POSTAL_CODE,
    EntityType.COMPANY_NUMBER,
    EntityType.VAT_NUMBER,
    EntityType.TENDER_NUMBER,
    EntityType.DATE,
    EntityType.TIME,
    EntityType.PAGE_NUMBER,
    EntityType.PERCENTAGE,
    EntityType.ID,
    EntityType.ADDRESS_NUMBER,
    EntityType.REFERENCE_NUMBER,
    EntityType.CPV_CODE,
    EntityType.REGISTRATION_NUMBER,
    EntityType.DIMENSION,
    EntityType.WEIGHT,
    EntityType.LENGTH,
    EntityType.AREA,
    EntityType.VOLUME,
}


def _classify_description_field(description: str, context: str = "") -> Tuple[bool, Optional[str], float]:
    """
    Use EntityClassifier to determine if a description/field is BOQ content.
    
    Returns: (is_valid_boq_field, reject_reason, confidence)
    """
    if not description.strip():
        return True, None, 1.0

    classification = classify_entity(
        value_str=description.strip(),
        context=context,
    )

    if classification.entity_type in _REJECTED_ENTITY_TYPES:
        return False, f"Rejected as {classification.entity_type}", classification.confidence

    return True, None, classification.confidence


def _filter_boq_row(row_text: str, context: str = "") -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Filter a potential BOQ row through entity classification.
    Returns: (is_valid, reject_type, reject_reason)
    """
    if not row_text.strip():
        return True, None, None
    
    # Check each space-separated token
    tokens = row_text.split()
    
    for token in tokens:
        classification = classify_entity(
            value_str=token,
            context=context,
        )
        if classification.entity_type in _REJECTED_ENTITY_TYPES:
            return False, classification.entity_type, classification.reason

    return True, None, None


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

    # Classify description field using EntityClassifier
    is_valid, reject_reason, _ = _classify_description_field(description)
    if not is_valid:
        logger.debug(f"[BOQv2] Row rejected by entity classifier: '{description}' — {reject_reason}")
        return None

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

    Uses pdfplumber table detection and integrates with EntityClassifier
    to reject non-BOQ content (phone numbers, addresses, dates, etc.).
    """
    import pdfplumber

    logger.info(f"[BOQv2] Starting extraction from: {file_path}")
    warnings: List[str] = []

    # ── Open PDF ──────────────────────────────────────────────────────
    try:
        pdf = pdfplumber.open(file_path)
    except Exception as e:
        logger.error(f"[BOQv2] Cannot open PDF: {e}")
        return BOQResult(
            filename=file_path,
            page_count=0,
            items=[],
            totals=BOQTotals(),
            extraction_method="boq_engine_v2",
            confidence="Low",
            tables_detected=0,
            warnings=[f"Cannot open PDF: {e}"],
        )

    page_count = len(pdf.pages)
    pages_to_process = _parse_page_range(page_range, page_count)

    all_items: List[BOQItem] = []
    all_rejected_details: List[BOQTableRejection] = []
    table_metadata_list: List[BOQTableMetadata] = []
    tables_detected = 0
    tables_accepted = 0
    tables_rejected = 0

    # ── Process each page ─────────────────────────────────────────────
    for page_num in pages_to_process:
        page = pdf.pages[page_num - 1]
        
        try:
            # Phase 1: Extract tables via pdfplumber
            tables = page.extract_tables()
        except Exception as e:
            logger.warning(f"[BOQv2] Table extraction failed on page {page_num}: {e}")
            warnings.append(f"Table extraction failed on page {page_num}")
            continue

        if not tables:
            logger.debug(f"[BOQv2] No tables found on page {page_num}")
            continue

        for table in tables:
            tables_detected += 1
            rows = [[cell if cell else "" for cell in row] for row in table]
            if not rows:
                continue

            table_text = _table_text_to_string(rows)

            # ── Classify table type ──────────────────────────────────
            is_boq, reject_reason, table_type = _classify_table_type(rows)

            if not is_boq:
                tables_rejected += 1
                logger.debug(f"[BOQv2] Table rejected on page {page_num}: {reject_reason}")
                all_rejected_details.append(BOQTableRejection(
                    page=page_num,
                    reason=reject_reason or "Unknown non-BOQ table",
                    evidence=table_text[:200],
                    table_type=table_type,
                    header_text=str(rows[0][0]) if rows[0] else "",
                ))
                continue

            # ── Detect headers ───────────────────────────────────────
            mapping = _classify_header(rows[0])
            header_row_used = True

            if mapping is None or not _has_price_column(mapping):
                # Try guessing from data
                mapping = _guess_mapping_from_data(rows)
                header_row_used = False
                if mapping is None:
                    tables_rejected += 1
                    all_rejected_details.append(BOQTableRejection(
                        page=page_num,
                        reason="Could not map columns to BOQ fields",
                        evidence=table_text[:200],
                        table_type="UnmappableColumns",
                        header_text=str(rows[0][0]) if rows[0] else "",
                    ))
                    continue

            # ── Extract rows ─────────────────────────────────────────
            extracted_items: List[BOQItem] = []
            rows_rejected = 0
            data_start = 0 if not header_row_used else 1

            # Get bounding box for evidence
            try:
                bbox = str(table.bbox) if hasattr(table, 'bbox') else None
            except Exception:
                bbox = None

            for row_idx in range(data_start, len(rows)):
                row = rows[row_idx]
                row_text = " | ".join(str(c) for c in row if c)

                # Filter row through entity classification
                is_valid, reject_type, reject_reason = _filter_boq_row(row_text)
                if not is_valid:
                    rows_rejected += 1
                    logger.debug(f"[BOQv2] Row rejected as {reject_type}: {row_text[:50]}")
                    continue

                item = _row_to_boq_item(
                    row, mapping, page_num, bbox,
                    method="pdfplumber_tables",
                )
                if item:
                    extracted_items.append(item)

            tables_accepted += 1
            table_metadata_list.append(BOQTableMetadata(
                page=page_num,
                bbox=bbox,
                columns_mapped=sum(1 for f in ["item_no", "description", "quantity", "unit", "rate", "amount"] 
                                   if getattr(mapping, f, None) is not None),
                rows_extracted=len(extracted_items),
                rows_rejected=rows_rejected,
                mapping=mapping,
            ))
            all_items.extend(extracted_items)

    pdf.close()

    # ── Final assembly ────────────────────────────────────────────────
    if all_items:
        # Sort by page then item_no
        all_items.sort(key=lambda x: (x.evidence.page or 0, x.item_no or ""))

        # Calculate totals
        subtotal = sum(i.amount or 0 for i in all_items 
                      if i.amount is not None and not i.is_total and not i.is_subtotal)

        # Detect subtotal/total rows
        total_rows = [i for i in all_items if i.is_total]
        subtotal_rows = [i for i in all_items if i.is_subtotal]

        stated_subtotal = subtotal_rows[-1].amount if subtotal_rows else None
        stated_total = total_rows[-1].amount if total_rows else None

        totals = BOQTotals(
            subtotal=stated_subtotal or subtotal if subtotal > 0 else None,
            total_before_vat=stated_total if stated_total else (stated_subtotal or subtotal if subtotal > 0 else None),
            page_count=page_count,
            calculated_from_items=stated_subtotal is None,
        )

        # Determine confidence
        items_with_rates = sum(1 for i in all_items if i.rate is not None)
        rate_ratio = items_with_rates / len(all_items) if all_items else 0

        if rate_ratio >= 0.7 and len(all_items) >= 3:
            confidence = "High"
        elif rate_ratio >= 0.3 and len(all_items) >= 2:
            confidence = "Medium"
        else:
            confidence = "Low"

        # Validation
        validation = _validate_items(all_items)
        if not validation.quantity_valid or not validation.unit_valid:
            warnings.extend(validation.quantity_issues)
            warnings.extend(validation.unit_issues)
            if confidence == "High":
                confidence = "Medium"
        if not validation.total_valid:
            warnings.extend(validation.total_issues)

        logger.info(
            f"[BOQv2] Extracted {len(all_items)} items from {tables_accepted}/{tables_detected} tables "
            f"(confidence={confidence})"
        )

        return BOQResult(
            filename=file_path,
            page_count=page_count,
            items=all_items,
            totals=totals,
            extraction_method="boq_engine_v2",
            confidence=confidence,
            tables_detected=tables_detected,
            tables_accepted=tables_accepted,
            tables_rejected=tables_rejected,
            rejected_tables=all_rejected_details,
            table_metadata=table_metadata_list,
            validation=validation,
            warnings=warnings,
        )

    # ── No BOQ detected ───────────────────────────────────────────────
    logger.info(f"[BOQv2] No BOQ detected in {file_path} — {tables_detected} tables found, 0 accepted")

    warnings.append(
        f"No BOQ detected. {tables_detected} table(s) found, "
        f"{tables_rejected} rejected as non-BOQ content."
    )

    return BOQResult(
        filename=file_path,
        page_count=page_count,
        items=[],
        totals=BOQTotals(),
        extraction_method="boq_engine_v2",
        confidence="Low",
        tables_detected=tables_detected,
        tables_accepted=0,
        tables_rejected=tables_rejected,
        rejected_tables=all_rejected_details,
        warnings=warnings,
    )


# ═══════════════════════════════════════════════════════════════════════
# Simulated BOQ for Testing
# ═══════════════════════════════════════════════════════════════════════

def _create_sample_boq_items() -> List[BOQItem]:
    """Create sample BOQ items for testing/demo."""
    items = [
        BOQItem(
            item_no="1.1",
            description="Site clearance and preparation",
            quantity=1.0,
            unit="ls",
            rate=125000.00,
            amount=125000.00,
            currency="ZAR",
            section="Preliminaries",
            evidence=BOQItemEvidence(
                page=1, confidence=0.95,
                source_text="1.1  Site clearance  1.00  ls  125000.00  125000.00",
                extraction_method="sample_data",
            ),
        ),
        BOQItem(
            item_no="1.2",
            description="Temporary site facilities",
            quantity=1.0,
            unit="ls",
            rate=85000.00,
            amount=85000.00,
            currency="ZAR",
            section="Preliminaries",
            evidence=BOQItemEvidence(
                page=1, confidence=0.95,
                source_text="1.2  Temp facilities  1.00  ls  85000.00  85000.00",
                extraction_method="sample_data",
            ),
        ),
        BOQItem(
            item_no="2.1",
            description="Excavation of foundation trenches",
            quantity=250.0,
            unit="m3",
            rate=180.00,
            amount=45000.00,
            currency="ZAR",
            section="Earthworks",
            evidence=BOQItemEvidence(
                page=2, confidence=0.90,
                source_text="2.1  Excavation trenches  250.00  m3  180.00  45000.00",
                extraction_method="sample_data",
            ),
        ),
        BOQItem(
            item_no="2.2",
            description="Supply and place concrete (25MPa)",
            quantity=120.0,
            unit="m3",
            rate=1450.00,
            amount=174000.00,
            currency="ZAR",
            section="Earthworks",
            evidence=BOQItemEvidence(
                page=2, confidence=0.90,
                source_text="2.2  Concrete 25MPa  120.00  m3  1450.00  174000.00",
                extraction_method="sample_data",
            ),
        ),
        BOQItem(
            item_no="3.1",
            description="Supply and install 50mm PVC drainage pipe",
            quantity=450.0,
            unit="m",
            rate=85.50,
            amount=38475.00,
            currency="ZAR",
            section="Drainage",
            evidence=BOQItemEvidence(
                page=3, confidence=0.95,
                source_text="3.1  50mm PVC pipe  450.00  m  85.50  38475.00",
                extraction_method="sample_data",
            ),
        ),
        BOQItem(
            item_no="3.2",
            description="Concrete manhole 1.2m deep (precast)",
            quantity=8.0,
            unit="each",
            rate=3500.00,
            amount=28000.00,
            currency="ZAR",
            section="Drainage",
            evidence=BOQItemEvidence(
                page=3, confidence=0.90,
                source_text="3.2  Manhole 1.2m  8.00  each  3500.00  28000.00",
                extraction_method="sample_data",
            ),
        ),
        BOQItem(
            item_no="4.1",
            description="Line marking (thermoplastic, 100mm wide)",
            quantity=1200.0,
            unit="m",
            rate=45.00,
            amount=54000.00,
            currency="ZAR",
            section="Roadworks",
            evidence=BOQItemEvidence(
                page=4, confidence=0.85,
                source_text="4.1  Line marking  1200.00  m  45.00  54000.00",
                extraction_method="sample_data",
            ),
        ),
    ]
    return items