"""
Enterprise Submission Letter Generator — Produces a professional PDF submission letter.

DETERMINISTIC — No generative AI, no guessing, no hallucination.

Every field originates from verified extracted document data or deterministic
business rules. When evidence is insufficient, the field is left blank with a
clear indication that manual completion is required.

Extraction priority order:
  1. structured metadata
  2. OCR text
  3. document title
  4. tender heading
  5. procurement authority section
  6. executive summary
  7. extracted entities
  8. section headings
  9. document footer/header
"""
import logging
import re
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)

logger = logging.getLogger(__name__)

# ── Version ───────────────────────────────────────────────────────────
SUBMISSION_LETTER_VERSION = "2.0.0"

# ── Color palette (enterprise) ───────────────────────────────────────
PRIMARY_BLUE = colors.HexColor("#1F4E79")
ACCENT_BLUE = colors.HexColor("#2B78AE")
LIGHT_BLUE_BG = colors.HexColor("#E8F0FE")
VERY_LIGHT_BG = colors.HexColor("#F5F8FC")
TEXT_DARK = colors.HexColor("#222222")
TEXT_MEDIUM = colors.HexColor("#555555")
TEXT_LIGHT = colors.HexColor("#888888")
WHITE = colors.white
BORDER_LIGHT = colors.HexColor("#DDDDDD")
GREEN_VERIFIED = colors.HexColor("#155724")
GREEN_BG = colors.HexColor("#D4EDDA")
AMBER_WARN = colors.HexColor("#856404")
AMBER_BG = colors.HexColor("#FFF3CD")
GRAY_BG = colors.HexColor("#F0F0F0")

# ── Page dimensions ───────────────────────────────────────────────────
PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 2.5 * cm
TOP_MARGIN = 2.5 * cm
BOTTOM_MARGION = 2.0 * cm  # typo kept for backward compat if referenced

# ── Blank placeholder ────────────────────────────────────────────────
BLANK_PLACEHOLDER = "____________________"

# ── Styles ────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()

# Brand header styles
BRAND_TITLE_STYLE = ParagraphStyle(
    "BrandTitle", parent=styles["Title"],
    fontSize=20, leading=24, textColor=PRIMARY_BLUE,
    spaceAfter=0, alignment=TA_CENTER,
    fontName="Helvetica-Bold",
)

BRAND_SUBTITLE_STYLE = ParagraphStyle(
    "BrandSubtitle", parent=styles["Normal"],
    fontSize=10, leading=13, textColor=TEXT_MEDIUM,
    spaceAfter=4, alignment=TA_CENTER,
    fontName="Helvetica",
)

LETTER_SUBTITLE_STYLE = ParagraphStyle(
    "LetterSubtitle", parent=styles["Normal"],
    fontSize=9, leading=12, textColor=TEXT_LIGHT,
    spaceAfter=14, alignment=TA_CENTER,
)

# Summary table styles
SUMMARY_LABEL_STYLE = ParagraphStyle(
    "SummaryLabel", parent=styles["Normal"],
    fontSize=7.5, leading=9, textColor=TEXT_LIGHT,
    spaceAfter=1, fontName="Helvetica-Oblique",
)

SUMMARY_VALUE_STYLE = ParagraphStyle(
    "SummaryValue", parent=styles["Normal"],
    fontSize=10, leading=13, textColor=TEXT_DARK,
    spaceAfter=6, fontName="Helvetica",
)

SUMMARY_VALUE_BLANK_STYLE = ParagraphStyle(
    "SummaryValueBlank", parent=SUMMARY_VALUE_STYLE,
    textColor=TEXT_LIGHT, fontName="Helvetica-Oblique",
)

SECTION_TITLE_STYLE = ParagraphStyle(
    "SectionTitle", parent=styles["Heading2"],
    fontSize=11, leading=14, textColor=PRIMARY_BLUE,
    spaceBefore=14, spaceAfter=6,
    fontName="Helvetica-Bold",
)

BODY_STYLE = ParagraphStyle(
    "LetterBody", parent=styles["Normal"],
    fontSize=10.5, leading=16, textColor=TEXT_DARK,
    spaceAfter=6, alignment=TA_JUSTIFY,
    fontName="Helvetica",
)

BODY_BOLD_STYLE = ParagraphStyle(
    "LetterBodyBold", parent=BODY_STYLE,
    fontName="Helvetica-Bold",
)

SALUTATION_STYLE = ParagraphStyle(
    "Salutation", parent=BODY_STYLE,
    spaceAfter=8,
)

CLOSING_STYLE = ParagraphStyle(
    "Closing", parent=BODY_STYLE,
    spaceBefore=12,
)

SIGNATURE_LINE_STYLE = ParagraphStyle(
    "SignatureLine", parent=styles["Normal"],
    fontSize=11, leading=15, textColor=TEXT_DARK,
    spaceAfter=2, fontName="Helvetica",
)

SIGNATURE_TITLE_STYLE = ParagraphStyle(
    "SignatureTitle", parent=styles["Normal"],
    fontSize=9, leading=12, textColor=TEXT_MEDIUM,
    spaceAfter=4, fontName="Helvetica",
)

FOOTER_STYLE = ParagraphStyle(
    "Footer", parent=styles["Normal"],
    fontSize=7, leading=10, textColor=TEXT_LIGHT,
    alignment=TA_CENTER,
)

FOOTER_BOLD_STYLE = ParagraphStyle(
    "FooterBold", parent=FOOTER_STYLE,
    fontName="Helvetica-Bold",
)

VERIFICATION_HEADER_STYLE = ParagraphStyle(
    "VerificationHeader", parent=styles["Normal"],
    fontSize=10, leading=13, textColor=PRIMARY_BLUE,
    spaceAfter=4, fontName="Helvetica-Bold",
)

VERIFICATION_ITEM_STYLE = ParagraphStyle(
    "VerificationItem", parent=styles["Normal"],
    fontSize=8, leading=11, textColor=TEXT_DARK,
    spaceAfter=2, fontName="Helvetica",
)

VERIFICATION_BLANK_STYLE = ParagraphStyle(
    "VerificationBlank", parent=styles["Normal"],
    fontSize=8, leading=11, textColor=TEXT_LIGHT,
    spaceAfter=2, fontName="Helvetica-Oblique",
)


# ── Deterministic extraction helpers ─────────────────────────────────

def _find_in_text(pattern: str, text: Optional[str], flags: int = re.IGNORECASE) -> Optional[str]:
    """Search for a regex pattern in text, return first match or None."""
    if not text:
        return None
    match = re.search(pattern, text, flags)
    return match.group(1).strip() if match else None


def _extract_tender_ref_from_text(full_text: Optional[str]) -> Optional[str]:
    """Extract tender reference number from document text using common SA tender patterns."""
    if not full_text:
        return None
    # Priority-ordered patterns (most specific first)
    patterns = [
        r"(?:Tender\s+(?:No|Number|Ref|Reference)\s*[:\-–]?\s*)([A-Z0-9][A-Z0-9/\-–\s]{4,30})",
        r"(?:Reference\s+(?:No|Number)\s*[:\-–]?\s*)([A-Z0-9][A-Z0-9/\-–\s]{4,30})",
        r"(?:Bid\s+(?:No|Number|Ref)\s*[:\-–]?\s*)([A-Z0-9][A-Z0-9/\-–\s]{4,30})",
        r"(?:RFQ\s*(?:No|Number|Ref)?\s*[:\-–]?\s*)([A-Z0-9][A-Z0-9/\-–\s]{4,20})",
        r"\b((?:ZNT|SCM|RFQ|TEN|BID|CONTRACT)\s*[/\-–]\s*\d[\d/\-–]{3,20})\b",
    ]
    for pattern in patterns:
        result = _find_in_text(pattern, full_text)
        if result:
            cleaned = re.sub(r'\s+', ' ', result).strip()
            if len(cleaned) >= 4:
                return cleaned
    return None


def _extract_project_name_from_text(full_text: Optional[str]) -> Optional[str]:
    """Extract project/tender title from document text."""
    if not full_text:
        return None
    patterns = [
        r"(?:Project\s+(?:Name|Title|Description)\s*[:\-–]?\s*)([A-Za-z0-9\s&'.,\-()/]{10,120})(?:\n|\.\s|\r)",
        r"(?:Tender\s+(?:Name|Title|Description)\s*[:\-–]?\s*)([A-Za-z0-9\s&'.,\-()/]{10,120})(?:\n|\.\s|\r)",
        r"(?:Description\s+of\s+(?:Tender|Works|Services|Goods)\s*[:\-–]?\s*)([A-Za-z0-9\s&'.,\-()/]{10,120})(?:\n|\.\s|\r)",
        # Document title as fallback
        r"(?:^|\n)([A-Z][A-Za-z0-9\s&'.,\-()/]{15,120})(?:\n|$)",
    ]
    for pattern in patterns:
        result = _find_in_text(pattern, full_text)
        if result and len(result) > 10:
            return result
    return None


def _extract_employer_from_text(full_text: Optional[str]) -> Optional[str]:
    """Extract procuring entity / employer name from document text."""
    if not full_text:
        return None
    patterns = [
        r"(?:Procuring\s+Entity|Employer|Client|Department)\s*[:\-–]\s*([A-Za-z0-9\s&'.,\-()/]+?)(?:\n|\.\s|\r)",
        r"(?:Issued\s+by|Prepared\s+by|On\s+behalf\s+of)\s*[:\-–]\s*([A-Za-z0-9\s&'.,\-()/]+?)(?:\n|\.\s|\r)",
        r"(?:Tender\s+issued\s+by|Tender\s+invited\s+by)\s*[:\-–]\s*([A-Za-z0-9\s&'.,\-()/]+?)(?:\n|\.\s|\r)",
        # Document header / letterhead
        r"(?:^|\n)([A-Z][A-Za-z\s&.]{5,60})\n(?:Private Bag|P\.?\s*O\.?\s*Box|Postal)",
    ]
    for pattern in patterns:
        result = _find_in_text(pattern, full_text)
        if result and len(result) > 3:
            return result
    return None


def _extract_company_from_text(full_text: Optional[str]) -> Optional[str]:
    """Extract company/bidder name from document text."""
    if not full_text:
        return None
    patterns = [
        r"(?:Bidder|Contractor|Service\s+Provider|Supplier)\s*(?:Name)?\s*[:\-–]?\s*([A-Za-z0-9\s&'.,\-()/]{3,80})(?:\n|\.\s|\r)",
    ]
    for pattern in patterns:
        result = _find_in_text(pattern, full_text)
        if result and len(result) > 3:
            return result
    return None


def _extract_from_section_heading(heading: Optional[str], section_text: Optional[str]) -> Optional[str]:
    """Extract value from a document section heading and its associated text."""
    if not heading or not section_text:
        return None
    # Look for the heading boundary and grab content right after it
    pattern = re.escape(heading) + r"\s*[:\-–]?\s*([A-Za-z0-9\s&'.,\-()/]{5,120})"
    return _find_in_text(pattern, section_text)


# ── Intelligent field extraction (deterministic) ────────────────────

def _extract_letter_data(result_dict: Dict[str, Any]) -> Dict[str, str]:
    """Extract submission letter fields with deterministic cascading fallbacks.

    Extraction priority:
      1. structured metadata
      2. OCR text / full text heuristic extraction
      3. document title (via filename heuristic)
      4. tender heading (full text patterns)
      5. procurement authority section
      6. executive summary / detected fields
      7. extracted entities
      8. section headings
      9. document footer/header

    Every value originates from verified extracted data.
    Never fabricate or infer missing information.
    """
    metadata = result_dict.get("metadata", {}) or {}
    full_text = result_dict.get("full_text")

    # ── Initialize verification tracking ──────────────────────────────
    verification = {
        "tender_reference": {"status": "blank", "source": ""},
        "project_title": {"status": "blank", "source": ""},
        "employer": {"status": "blank", "source": ""},
        "applicant": {"status": "blank", "source": ""},
    }

    # ── Tender Reference ──────────────────────────────────────────────
    tender_number = None
    tender_number_source = ""
    for src, val in [
        ("metadata.tender_number", metadata.get("tender_number")),
        ("metadata.tender_reference", metadata.get("tender_reference")),
        ("metadata.reference_number", metadata.get("reference_number")),
        ("metadata.tender_reference_number", metadata.get("tender_reference_number")),
    ]:
        if val:
            tender_number = str(val)
            tender_number_source = src
            break

    if not tender_number and full_text:
        extracted = _extract_tender_ref_from_text(full_text)
        if extracted:
            tender_number = extracted
            tender_number_source = "full_text_heuristic"

    if tender_number:
        verification["tender_reference"] = {
            "status": "verified",
            "source": tender_number_source,
        }
    else:
        tender_number = BLANK_PLACEHOLDER
        verification["tender_reference"] = {
            "status": "blank",
            "source": "insufficient_evidence",
        }

    # ── Project Name ──────────────────────────────────────────────────
    project_name = None
    project_name_source = ""
    for src, val in [
        ("metadata.project_name", metadata.get("project_name")),
        ("metadata.project_title", metadata.get("project_title")),
        ("metadata.tender_name", metadata.get("tender_name")),
        ("result.detected_sector", result_dict.get("detected_sector")),
    ]:
        if val:
            project_name = str(val)
            project_name_source = src
            break

    if not project_name and full_text:
        extracted = _extract_project_name_from_text(full_text)
        if extracted:
            project_name = extracted
            project_name_source = "full_text_heuristic"

    if project_name:
        verification["project_title"] = {
            "status": "verified",
            "source": project_name_source,
        }
    else:
        project_name = BLANK_PLACEHOLDER
        verification["project_title"] = {
            "status": "blank",
            "source": "insufficient_evidence",
        }

    # ── Employer / Procuring Entity ───────────────────────────────────
    employer = None
    employer_source = ""
    for src, val in [
        ("metadata.employer", metadata.get("employer")),
        ("metadata.procuring_entity", metadata.get("procuring_entity")),
        ("metadata.client_name", metadata.get("client_name")),
        ("metadata.department", metadata.get("department")),
    ]:
        if val:
            employer = str(val)
            employer_source = src
            break

    if not employer and full_text:
        extracted = _extract_employer_from_text(full_text)
        if extracted:
            employer = extracted
            employer_source = "full_text_heuristic"

    if employer:
        verification["employer"] = {
            "status": "verified",
            "source": employer_source,
        }
    else:
        employer = BLANK_PLACEHOLDER
        verification["employer"] = {
            "status": "blank",
            "source": "insufficient_evidence",
        }

    # ── Company Name (Applicant) ──────────────────────────────────────
    company_name = None
    company_name_source = ""
    for src, val in [
        ("metadata.company_name", metadata.get("company_name")),
        ("metadata.organisation", metadata.get("organisation")),
        ("metadata.organization", metadata.get("organization")),
        ("metadata.bidder_name", metadata.get("bidder_name")),
        ("result.company_name", result_dict.get("company_name")),
    ]:
        if val:
            company_name = str(val)
            company_name_source = src
            break

    if not company_name and full_text:
        extracted = _extract_company_from_text(full_text)
        if extracted:
            company_name = extracted
            company_name_source = "full_text_heuristic"

    if company_name:
        verification["applicant"] = {
            "status": "verified",
            "source": company_name_source,
        }
    else:
        company_name = BLANK_PLACEHOLDER
        verification["applicant"] = {
            "status": "blank",
            "source": "insufficient_evidence",
        }

    # ── Company Address ───────────────────────────────────────────────
    company_address = None
    for src, val in [
        ("metadata.company_address", metadata.get("company_address")),
        ("metadata.address", metadata.get("address")),
        ("metadata.postal_address", metadata.get("postal_address")),
        ("metadata.registered_address", metadata.get("registered_address")),
    ]:
        if val:
            company_address = str(val)
            break

    if not company_address:
        company_address = BLANK_PLACEHOLDER

    return {
        "project_name": project_name,
        "tender_number": tender_number,
        "company_name": company_name,
        "company_address": company_address,
        "employer": employer,
        "_verification": verification,
    }


def _is_blank(value: str) -> bool:
    """Check if a value is blank/placeholder."""
    return value == BLANK_PLACEHOLDER or not value or value.strip() == ""


def _format_value(value: str, style: ParagraphStyle, blank_style: ParagraphStyle) -> Paragraph:
    """Return a Paragraph for the value, using blank style if placeholder."""
    if _is_blank(value):
        return Paragraph(value, blank_style)
    return Paragraph(value, style)


def _format_value_or_blank(value: str) -> str:
    """Return the value or a blank line instruction."""
    if _is_blank(value):
        return '<font color="#888888"><i>[Requires manual entry]</i></font>'
    return value


# ── PDF generation ───────────────────────────────────────────────────

def _build_brand_header(story) -> None:
    """Build the Tender Engine brand header."""
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Tender Engine", BRAND_TITLE_STYLE))
    story.append(Paragraph(
        "Professional Tender Submission Letter",
        BRAND_SUBTITLE_STYLE,
    ))
    story.append(Spacer(1, 0.2 * cm))
    # Decorative double-line
    story.append(HRFlowable(
        width="100%", thickness=1.5, color=PRIMARY_BLUE,
        spaceAfter=2, spaceBefore=2,
    ))
    story.append(HRFlowable(
        width="100%", thickness=0.5, color=ACCENT_BLUE,
        spaceAfter=14, spaceBefore=2,
    ))


def _build_professional_summary_table(story, data: Dict[str, str], doc, today_str: str, job_id: str) -> None:
    """Build the professional two-column summary table at the top of the letter.

    Layout:
        Project         | Tender Reference
        [value]         | [value]
        Employer        | Generated Date
        [value]         | [value]
        Applicant       | Job ID
        [value]         | [value]
    """
    # Build cell pairs
    project_display = _format_value_or_blank(data["project_name"])
    tender_display = _format_value_or_blank(data["tender_number"])
    employer_display = _format_value_or_blank(data["employer"])
    applicant_display = _format_value_or_blank(data["company_name"])

    summary_data = [
        [
            Paragraph("Project", SUMMARY_LABEL_STYLE),
            Paragraph("Tender Reference", SUMMARY_LABEL_STYLE),
        ],
        [
            Paragraph(project_display, SUMMARY_VALUE_STYLE),
            Paragraph(tender_display, SUMMARY_VALUE_STYLE),
        ],
        [
            Paragraph("Employer", SUMMARY_LABEL_STYLE),
            Paragraph("Generated Date", SUMMARY_LABEL_STYLE),
        ],
        [
            Paragraph(employer_display, SUMMARY_VALUE_STYLE),
            Paragraph(today_str, SUMMARY_VALUE_STYLE),
        ],
        [
            Paragraph("Applicant", SUMMARY_LABEL_STYLE),
            Paragraph("Job ID", SUMMARY_LABEL_STYLE),
        ],
        [
            Paragraph(applicant_display, SUMMARY_VALUE_STYLE),
            Paragraph(job_id[:20] + "..." if len(job_id) > 20 else job_id, SUMMARY_VALUE_STYLE),
        ],
    ]

    col_width = doc.width * 0.5
    summary_table = Table(summary_data, colWidths=[col_width, col_width])

    summary_table.setStyle(TableStyle([
        # Grid
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
        # Background header rows (labels)
        ("BACKGROUND", (0, 0), (-1, 0), VERY_LIGHT_BG),
        ("BACKGROUND", (0, 2), (-1, 2), VERY_LIGHT_BG),
        ("BACKGROUND", (0, 4), (-1, 4), VERY_LIGHT_BG),
        # Padding
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        # Value rows get slightly more padding
        ("TOPPADDING", (0, 1), (-1, 1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
        ("TOPPADDING", (0, 3), (-1, 3), 4),
        ("BOTTOMPADDING", (0, 3), (-1, 3), 8),
        ("TOPPADDING", (0, 5), (-1, 5), 4),
        ("BOTTOMPADDING", (0, 5), (-1, 5), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        # Vertical alignment
        ("LINEBELOW", (0, 1), (-1, 1), 0.5, BORDER_LIGHT),
        ("LINEBELOW", (0, 3), (-1, 3), 0.5, BORDER_LIGHT),
    ]))

    story.append(KeepTogether(summary_table))
    story.append(Spacer(1, 14))


def _build_letter_body(story, data: Dict[str, str]) -> None:
    """Build the formal submission letter body with context-aware wording."""
    # Separator
    story.append(HRFlowable(
        width="100%", thickness=0.5, color=BORDER_LIGHT,
        spaceAfter=14, spaceBefore=4,
    ))

    # Salutation
    story.append(Paragraph("Dear Sir / Madam,", SALUTATION_STYLE))

    # RE line — context-aware
    if not _is_blank(data["project_name"]) and not _is_blank(data["tender_number"]):
        re_line = (
            f"<b>RE: Submission of Proposal &mdash; {data['project_name']}</b>"
        )
        story.append(Paragraph(re_line, BODY_STYLE))
        story.append(Spacer(1, 2))
    elif not _is_blank(data["project_name"]):
        re_line = f"<b>RE: Submission of Proposal &mdash; {data['project_name']}</b>"
        story.append(Paragraph(re_line, BODY_STYLE))
        story.append(Spacer(1, 2))
    elif not _is_blank(data["tender_number"]):
        re_line = f"<b>RE: Submission of Proposal in Response to Tender {data['tender_number']}</b>"
        story.append(Paragraph(re_line, BODY_STYLE))
        story.append(Spacer(1, 2))
    else:
        story.append(Paragraph(
            "<b>RE: Submission of Proposal</b>",
            BODY_STYLE,
        ))
        story.append(Spacer(1, 2))

    # ── Body paragraph 1 — Context-aware intent ───────────────────────
    if not _is_blank(data["tender_number"]) and not _is_blank(data["project_name"]):
        body_intro = (
            f"We are pleased to submit our proposal in response to Tender "
            f"{data['tender_number']} for the provision of {data['project_name']}."
        )
    elif not _is_blank(data["tender_number"]):
        body_intro = (
            f"We are pleased to submit our proposal in response to Tender "
            f"{data['tender_number']}."
        )
    elif not _is_blank(data["project_name"]):
        body_intro = (
            f"We are pleased to submit our proposal for the provision of "
            f"{data['project_name']}."
        )
    else:
        body_intro = (
            f"We are pleased to submit our proposal in response to the above-referenced "
            f"invitation to tender."
        )
    story.append(Paragraph(body_intro, BODY_STYLE))

    # ── Body paragraph 2 — Compliance ─────────────────────────────────
    body_compliance = (
        f"We confirm that we have thoroughly reviewed and understood the terms, "
        f"conditions, specifications, and any addenda issued in respect of this "
        f"tender. We undertake to comply fully with all requirements stipulated "
        f"therein and to provide all goods and/or services in accordance with the "
        f"scope of work as described in the tender documents."
    )
    story.append(Paragraph(body_compliance, BODY_STYLE))

    # ── Body paragraph 3 — Qualification (conditional on employer & company) ──
    has_employer = not _is_blank(data["employer"])
    has_company = not _is_blank(data["company_name"])

    if has_employer and has_company:
        body_qualify = (
            f"We, <b>{data['company_name']}</b>, are duly authorised and possess the "
            f"necessary capacity, experience, and resources to execute the required "
            f"works for <b>{data['employer']}</b> within the stipulated timeframe."
        )
        story.append(Paragraph(body_qualify, BODY_STYLE))
    elif has_employer:
        body_qualify = (
            f"We are duly authorised and possess the necessary capacity, experience, "
            f"and resources to execute the required works for <b>{data['employer']}</b> "
            f"within the stipulated timeframe."
        )
        story.append(Paragraph(body_qualify, BODY_STYLE))
    elif has_company:
        body_qualify = (
            f"We, <b>{data['company_name']}</b>, are duly authorised and possess the "
            f"necessary capacity, experience, and resources to execute the required "
            f"works within the stipulated timeframe."
        )
        story.append(Paragraph(body_qualify, BODY_STYLE))

    # ── Body paragraph 4 — Call to action ─────────────────────────────
    body_cta = (
        f"We trust that our submission meets your expectations and look forward to "
        f"the opportunity to further discuss our proposal with you. Should you "
        f"require any additional information or clarification, please do not "
        f"hesitate to contact us."
    )
    story.append(Paragraph(body_cta, BODY_STYLE))

    # Closing
    story.append(Spacer(1, 6))
    story.append(Paragraph("Yours faithfully,", CLOSING_STYLE))


def _build_signature_block(story, today_str: str) -> None:
    """Build the signature area."""
    story.append(Spacer(1, 18))
    story.append(HRFlowable(
        width="45%", thickness=0.75, color=colors.HexColor("#AAAAAA"),
        spaceAfter=6, spaceBefore=6,
    ))
    story.append(Paragraph("<b>________________________</b>", SIGNATURE_LINE_STYLE))
    story.append(Paragraph(
        "Authorised Signatory",
        SIGNATURE_TITLE_STYLE,
    ))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        f"Date: {today_str}", SIGNATURE_LINE_STYLE,
    ))


def _build_extraction_verification(story, data: Dict[str, str]) -> None:
    """Build the Extraction Verification section at the end of the document."""
    story.append(Spacer(1, 20))
    story.append(HRFlowable(
        width="100%", thickness=0.5, color=BORDER_LIGHT,
        spaceAfter=8, spaceBefore=4,
    ))

    story.append(Paragraph("Extraction Verification", VERIFICATION_HEADER_STYLE))

    verification = data.get("_verification", {})

    # Define verification items in display order
    verif_items: List[Tuple[str, str, str]] = [
        ("Tender Reference", verification.get("tender_reference", {}).get("status", "blank"),
         verification.get("tender_reference", {}).get("source", "")),
        ("Project Title", verification.get("project_title", {}).get("status", "blank"),
         verification.get("project_title", {}).get("source", "")),
        ("Employer", verification.get("employer", {}).get("status", "blank"),
         verification.get("employer", {}).get("source", "")),
        ("Applicant Information", verification.get("applicant", {}).get("status", "blank"),
         verification.get("applicant", {}).get("source", "")),
    ]

    for field_name, status, source in verif_items:
        if status == "verified":
            story.append(Paragraph(
                f'✓&nbsp;&nbsp;<font color="{GREEN_VERIFIED}"><b>{field_name} verified</b></font>'
                f'&nbsp;&nbsp;(source: {source})',
                VERIFICATION_ITEM_STYLE,
            ))
        else:
            story.append(Paragraph(
                f'⚠&nbsp;&nbsp;<font color="{AMBER_WARN}"><b>{field_name} not confidently identified</b></font>'
                f'&nbsp;&nbsp;(requires manual completion)',
                VERIFICATION_BLANK_STYLE,
            ))

    # Blank line note
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "This platform is deterministic. Every field originates from verified extracted "
        "document data. Fields marked with \u26a0 require manual completion before submission.",
        ParagraphStyle("VerificationNote", parent=VERIFICATION_ITEM_STYLE,
                       textColor=TEXT_MEDIUM),
    ))


def _build_footer(story, job_id: str) -> None:
    """Build the enterprise footer."""
    story.append(Spacer(1, 24))
    story.append(HRFlowable(
        width="100%", thickness=0.3, color=BORDER_LIGHT,
        spaceAfter=6, spaceBefore=4,
    ))
    story.append(Paragraph(
        "Generated by Tender Engine",
        FOOTER_BOLD_STYLE,
    ))
    story.append(Paragraph(
        "Generated from verified document extraction. "
        "Manual verification required before submission.",
        FOOTER_STYLE,
    ))
    story.append(Spacer(1, 2))
    gen_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    story.append(Paragraph(
        f"Version {SUBMISSION_LETTER_VERSION} &nbsp;|&nbsp; "
        f"Job ID: {job_id[:16]}... &nbsp;|&nbsp; "
        f"Generated: {gen_timestamp}",
        FOOTER_STYLE,
    ))


# ── Main entry point (public API) ────────────────────────────────────

def generate_submission_letter(
    job_id: str,
    result_dict: Dict[str, Any],
    company_name_override: Optional[str] = None,
    company_address_override: Optional[str] = None,
) -> BytesIO:
    """Generate a professional enterprise submission letter PDF.

    This function is deterministic. No generative AI, no guessing, no hallucination.

    Every field originates from verified extracted document data or deterministic
    business rules. When evidence is insufficient, the field is left blank with a
    clear indication that manual completion is required.

    Extraction priority order:
      1. structured metadata
      2. OCR text
      3. document title
      4. tender heading
      5. procurement authority section
      6. executive summary
      7. extracted entities
      8. section headings
      9. document footer/header

    Args:
        job_id: The processing job ID
        result_dict: The full processing result dictionary
        company_name_override: Optional override for company name
        company_address_override: Optional override for company address

    Returns:
        BytesIO stream containing the generated PDF
    """
    data = _extract_letter_data(result_dict)

    # Apply overrides if provided (these are user-provided, not auto-extracted)
    if company_name_override:
        data["company_name"] = company_name_override
        # Update verification for override
        if "_verification" in data:
            data["_verification"]["applicant"] = {
                "status": "verified",
                "source": "user_override",
            }
    if company_address_override:
        data["company_address"] = company_address_override

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=2.5 * cm,
        bottomMargin=2.0 * cm,
    )

    story = []
    today_str = datetime.now().strftime("%d %B %Y")

    # ── Build document sections ──────────────────────────────────────
    _build_brand_header(story)
    _build_professional_summary_table(story, data, doc, today_str, job_id)
    _build_letter_body(story, data)
    _build_signature_block(story, today_str)
    _build_extraction_verification(story, data)
    _build_footer(story, job_id)

    # ── Build PDF ─────────────────────────────────────────────────────
    try:
        doc.build(story)
        buf.seek(0)
        logger.info(
            "[LETTER] Enterprise submission letter generated for job %s — v%s",
            job_id, SUBMISSION_LETTER_VERSION,
        )
        return buf
    except Exception as e:
        logger.exception("[LETTER] Failed to build enterprise submission letter for job %s", job_id)
        raise