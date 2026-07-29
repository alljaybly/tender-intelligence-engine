"""
Tender Completion Guide - contractor instruction manual.

This document is intentionally different from the Bid Response Roadmap.
The roadmap tells the contractor what to capture from the tender.
This guide tells the contractor what still needs to be completed before
submission, who normally handles it, and how to get it done.

Production-Quality Enterprise Document
=======================================
- Auto-wrapping table cells (never truncated, no overlap)
- Professional status badges with colour coding
- Confidence summary (Metadata, BOQ, Pricing, Compliance, Overall)
- Estimated remaining work, completion time, complexity level
- Helpful contacts per information field
- Footer: QR Code, version, timestamp, page X of Y
- Alternating row colours, generous padding, professional typography
"""
from __future__ import annotations

import io
import logging
import os
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

# QR code is optional — application must never fail to start if unavailable.
try:
    import qrcode
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False
    qrcode = None  # type: ignore[assignment]

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .report_framework import DataCompleteness, build_extracted_fields, build_missing_information, build_action_plan
from .schema_manager import SchemaManager

logger = logging.getLogger(__name__)

GUIDE_VERSION = "4.0.0"

# ── Colour Palette ──────────────────────────────────────────────────────
PRIMARY_BLUE = colors.HexColor("#1F4E79")
SECONDARY_BLUE = colors.HexColor("#2B78AE")
LIGHT_BLUE_BG = colors.HexColor("#EEF5FC")
SUCCESS_GREEN = colors.HexColor("#1B5E20")
SUCCESS_GREEN_BG = colors.HexColor("#E8F5E9")
WARNING_AMBER = colors.HexColor("#8A5A00")
WARNING_AMBER_BG = colors.HexColor("#FFF3CD")
ERROR_RED = colors.HexColor("#8B1E2D")
ERROR_RED_BG = colors.HexColor("#F8D7DA")
TEXT_DARK = colors.HexColor("#222222")
TEXT_MEDIUM = colors.HexColor("#555555")
TEXT_LIGHT = colors.HexColor("#888888")
WHITE = colors.white
VERIFIED_GREEN_BG = colors.HexColor("#D4EDDA")
PENDING_BG = colors.HexColor("#FFF3CD")
MISSING_BG = colors.HexColor("#F8D7DA")

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 2.2 * cm
TOP_MARGIN = 2.5 * cm
BOTTOM_MARGIN = 2.8 * cm  # Extra space for footer with QR code

# ── Paragraph Styles ────────────────────────────────────────────────────
styles = getSampleStyleSheet()

COVER_TITLE = ParagraphStyle(
    "CoverTitle",
    parent=styles["Title"],
    fontSize=26,
    leading=32,
    textColor=PRIMARY_BLUE,
    alignment=TA_CENTER,
    spaceAfter=10,
)
COVER_SUBTITLE = ParagraphStyle(
    "CoverSubtitle",
    parent=styles["Normal"],
    fontSize=11,
    leading=16,
    textColor=TEXT_MEDIUM,
    alignment=TA_CENTER,
    spaceAfter=24,
)
SECTION_STYLE = ParagraphStyle(
    "SectionHeader",
    parent=styles["Heading1"],
    fontSize=16,
    leading=21,
    textColor=PRIMARY_BLUE,
    spaceBefore=20,
    spaceAfter=10,
)
SUBSECTION_STYLE = ParagraphStyle(
    "SubSectionHeader",
    parent=styles["Heading2"],
    fontSize=12,
    leading=16,
    textColor=PRIMARY_BLUE,
    spaceBefore=14,
    spaceAfter=6,
)
BODY = ParagraphStyle(
    "Body",
    parent=styles["Normal"],
    fontSize=9,
    leading=14,
    textColor=TEXT_DARK,
    spaceAfter=6,
)
BODY_BOLD = ParagraphStyle(
    "BodyBold",
    parent=BODY,
    fontName="Helvetica-Bold",
)
SMALL = ParagraphStyle(
    "Small",
    parent=styles["Normal"],
    fontSize=7.5,
    leading=11,
    textColor=TEXT_MEDIUM,
    spaceAfter=4,
)
CHECKLIST_STYLE = ParagraphStyle(
    "Checklist",
    parent=styles["Normal"],
    fontSize=9,
    leading=14,
    textColor=TEXT_DARK,
    leftIndent=18,
    spaceAfter=5,
    wordWrap="CJK",
)
CELL_BODY = ParagraphStyle(
    "CellBody",
    parent=styles["Normal"],
    fontSize=7.6,
    leading=10,
    textColor=TEXT_DARK,
    spaceAfter=0,
    spaceBefore=0,
    wordWrap="CJK",
)
CELL_HEADER = ParagraphStyle(
    "CellHeader",
    parent=styles["Normal"],
    fontSize=8.2,
    leading=11,
    textColor=WHITE,
    fontName="Helvetica-Bold",
    spaceAfter=0,
    spaceBefore=0,
    wordWrap="CJK",
)
CENTRE_SMALL = ParagraphStyle(
    "CentreSmall",
    parent=SMALL,
    alignment=TA_CENTER,
)

# ── Status Badge Styles ─────────────────────────────────────────────────
BADGE_CRITICAL = ParagraphStyle(
    "BadgeCritical",
    fontName="Helvetica-Bold",
    fontSize=8,
    leading=10,
    alignment=TA_CENTER,
    textColor=ERROR_RED,
    backColor=ERROR_RED_BG,
    borderPadding=3,
    borderWidth=0.5,
    borderColor=ERROR_RED,
)
BADGE_HIGH = ParagraphStyle(
    "BadgeHigh",
    fontName="Helvetica-Bold",
    fontSize=8,
    leading=10,
    alignment=TA_CENTER,
    textColor=WARNING_AMBER,
    backColor=WARNING_AMBER_BG,
    borderPadding=3,
    borderWidth=0.5,
    borderColor=WARNING_AMBER,
)
BADGE_MEDIUM = ParagraphStyle(
    "BadgeMedium",
    fontName="Helvetica-Bold",
    fontSize=8,
    leading=10,
    alignment=TA_CENTER,
    textColor=SECONDARY_BLUE,
    backColor=LIGHT_BLUE_BG,
    borderPadding=3,
    borderWidth=0.5,
    borderColor=SECONDARY_BLUE,
)
BADGE_COMPLETE = ParagraphStyle(
    "BadgeComplete",
    fontName="Helvetica-Bold",
    fontSize=8,
    leading=10,
    alignment=TA_CENTER,
    textColor=SUCCESS_GREEN,
    backColor=VERIFIED_GREEN_BG,
    borderPadding=3,
    borderWidth=0.5,
    borderColor=SUCCESS_GREEN,
)
BADGE_PENDING = ParagraphStyle(
    "BadgePending",
    fontName="Helvetica-Bold",
    fontSize=8,
    leading=10,
    alignment=TA_CENTER,
    textColor=WARNING_AMBER,
    backColor=PENDING_BG,
    borderPadding=3,
    borderWidth=0.5,
    borderColor=WARNING_AMBER,
)
BADGE_MISSING = ParagraphStyle(
    "BadgeMissing",
    fontName="Helvetica-Bold",
    fontSize=8,
    leading=10,
    alignment=TA_CENTER,
    textColor=ERROR_RED,
    backColor=MISSING_BG,
    borderPadding=3,
    borderWidth=0.5,
    borderColor=ERROR_RED,
)
BADGE_VERIFIED = ParagraphStyle(
    "BadgeVerified",
    fontName="Helvetica-Bold",
    fontSize=8,
    leading=10,
    alignment=TA_CENTER,
    textColor=SUCCESS_GREEN,
    backColor=VERIFIED_GREEN_BG,
    borderPadding=3,
    borderWidth=0.5,
    borderColor=SUCCESS_GREEN,
)

STATUS_READY = ParagraphStyle(
    "StatusReady",
    parent=BODY_BOLD,
    fontSize=14,
    leading=18,
    alignment=TA_CENTER,
    textColor=SUCCESS_GREEN,
    backColor=SUCCESS_GREEN_BG,
    borderPadding=10,
    borderWidth=1,
    borderColor=SUCCESS_GREEN,
)
STATUS_PARTIAL = ParagraphStyle(
    "StatusPartial",
    parent=BODY_BOLD,
    fontSize=14,
    leading=18,
    alignment=TA_CENTER,
    textColor=WARNING_AMBER,
    backColor=WARNING_AMBER_BG,
    borderPadding=10,
    borderWidth=1,
    borderColor=WARNING_AMBER,
)
STATUS_NOT_READY = ParagraphStyle(
    "StatusNotReady",
    parent=BODY_BOLD,
    fontSize=14,
    leading=18,
    alignment=TA_CENTER,
    textColor=ERROR_RED,
    backColor=ERROR_RED_BG,
    borderPadding=10,
    borderWidth=1,
    borderColor=ERROR_RED,
)

# ── Helpful Contacts ────────────────────────────────────────────────────
MISSING_INFO_CONTACTS: Dict[str, str] = {
    "detected_sector": "Estimator, contracts manager, or the tender advert itself",
    "detected_duration_months": "Employer's scope, programme, or tender data sheet",
    "detected_locations": "Employer's scope, site information, or project particulars",
    "boq_items": "The tender BOQ attachment issued by the employer",
    "pricing_result": "Your estimator or quantity surveyor after completing the BOQ",
    "detected_workforce": "Estimator, contracts manager, or technical lead",
    "detected_schedule": "Programme/schedule attachment or the employer's project timeline",
    "detected_currency": "Tender pricing schedule or tender data",
}

HELPFUL_CONTACTS_DETAILED: Dict[str, str] = {
    "detected_sector": "Estimator",
    "detected_duration_months": "Employer / Director",
    "detected_locations": "Employer / Engineer",
    "boq_items": "Estimator / Quantity Surveyor",
    "pricing_result": "Estimator / Accountant",
    "detected_workforce": "Estimator / Contracts Manager",
    "detected_schedule": "Employer / Engineer / Architect",
    "detected_currency": "Accountant / Director",
    "tax_clearance": "Accountant / Tax Practitioner",
    "csd_registration": "Company Secretary / Director",
    "bbbee_certificate": "Director / Verification Agency",
    "company_registration": "Company Secretary / Director",
    "cidb_registration": "Director / Contracts Manager",
    "proof_of_address": "Admin Team / Finance Office",
    "bank_confirmation": "Finance Team / Director",
    "insurance_certificates": "Finance Team / Broker",
}

# ── Jurisdiction Documents ──────────────────────────────────────────────
JURISDICTION_DOCUMENTS: Dict[str, Dict[str, Any]] = {
    "south_africa": {
        "name": "South Africa",
        "documents": [
            {
                "name": "Tax Clearance / Tax Compliance Status",
                "priority": "Critical",
                "where": "SARS eFiling or your tax practitioner",
                "who": "Accountant, tax practitioner, or company director",
                "how": "Confirm it is valid on the closing date and print the current proof.",
            },
            {
                "name": "CSD Registration Summary",
                "priority": "Critical",
                "where": "National Treasury CSD portal",
                "who": "Company administrator or director",
                "how": "Download the current supplier summary and check banking and tax status.",
            },
            {
                "name": "B-BBEE Certificate / Sworn Affidavit",
                "priority": "Critical",
                "where": "Your verification agency or commissioner of oaths",
                "who": "Director, consultant, or verification agency",
                "how": "Use the correct document type for your entity size and current validity period.",
            },
            {
                "name": "Company Registration Documents",
                "priority": "Critical",
                "where": "CIPC records",
                "who": "Company secretary, director, or admin team",
                "how": "Check the registered name and number match every tender form exactly.",
            },
            {
                "name": "CIDB Registration Certificate",
                "priority": "High",
                "where": "CIDB portal",
                "who": "Director, contracts manager, or admin team",
                "how": "Confirm the grading is high enough for the tender class and value.",
            },
            {
                "name": "Proof of Business Address",
                "priority": "High",
                "where": "Municipal account, lease, or bank letter",
                "who": "Admin team or finance office",
                "how": "Use a recent document in the company name and scan it clearly.",
            },
            {
                "name": "Bank Confirmation Letter",
                "priority": "Medium",
                "where": "Your bank branch or relationship manager",
                "who": "Finance team or director",
                "how": "Request a current stamped letter if the tender calls for banking confirmation.",
            },
        ],
        "mistakes": [
            ("Missing signature", "Check every declaration, annexure, and pricing page for the required signatory."),
            ("Expired compliance document", "Confirm validity dates against the tender closing date, not today's date."),
            ("Wrong company details", "Use the exact registered name and number everywhere, including SBD forms."),
            ("BOQ arithmetic errors", "Recheck extensions, totals, provisional sums, and VAT before printing."),
            ("Late upload", "Submit early enough to recover from portal issues, slow scans, or power failures."),
        ],
    },
    "default": {
        "name": "International / General",
        "documents": [
            {
                "name": "Company Registration Certificate",
                "priority": "Critical",
                "where": "Your company registry",
                "who": "Company secretary, admin team, or director",
                "how": "Use the latest official record and verify the legal entity details match the tender forms.",
            },
            {
                "name": "Tax Registration / Clearance",
                "priority": "Critical",
                "where": "Tax authority portal or tax adviser",
                "who": "Finance team or tax adviser",
                "how": "Confirm the document is current and valid for the tender closing date.",
            },
            {
                "name": "Insurance Certificates",
                "priority": "High",
                "where": "Broker or insurer",
                "who": "Finance team or broker",
                "how": "Check policy limits, expiry dates, and insured name match the tender requirements.",
            },
            {
                "name": "Bank Reference Letter",
                "priority": "Medium",
                "where": "Your bank",
                "who": "Finance team",
                "how": "Request a current letter if the tender asks for financial standing or bank details.",
            },
        ],
        "mistakes": [
            ("Blank form fields", "Write a value or 'N/A' everywhere the form expects a response."),
            ("Unsigned declarations", "Confirm the authorised signatory signs every required declaration."),
            ("Wrong file order", "Compile documents in the exact order requested by the tender instructions."),
            ("Old certificates", "Check all compliance documents are still current on closing date."),
            ("Last-minute submission", "Finish the upload early enough to fix rejected files or portal problems."),
        ],
    },
}

DEFAULT_DISQUALIFICATION_MISTAKES: List[Tuple[str, str]] = [
    ("Wrong BOQ version", "Confirm the pricing team is working from the final issued BOQ and all addenda."),
    ("Expired tax certificate", "Check validity against the tender closing date, not the date of printing."),
    ("Missing initials", "Review every form page and annexure for required initials."),
    ("Missing signatures", "Ensure every declaration, form, and pricing page is signed by the authorised signatory."),
    ("Incorrect pricing totals", "Recalculate extensions, subtotals, contingencies, VAT, and grand totals before submission."),
    ("Wrong file naming", "Name uploaded files exactly as instructed by the tender or portal rules."),
    ("Wrong submission method", "Confirm whether submission is portal, email, courier, hand delivery, or physical box."),
    ("Missing annexures", "Check the returnable schedule list and attach every annexure in the correct order."),
    ("Incorrect VAT treatment", "Apply VAT exactly as the tender pricing rules require and verify summary totals."),
    ("Missing witness signatures", "Where witness signatures are required, make sure those fields are completed as well."),
    ("Late upload", "Submit early enough to recover from portal issues, connectivity problems, or scanner delays."),
    ("Password-protected PDFs", "Do not upload locked files unless the tender expressly allows them."),
    ("Unreadable scanned forms", "Review every scan for legibility, orientation, and completeness before final upload."),
    ("Mandatory briefing not attended", "Do not submit if briefing attendance was mandatory and your attendance cannot be proven."),
    ("Incorrect company registration number", "Match the legal entity number exactly across forms and supporting documents."),
    ("Missing declaration forms", "Check the tender instructions and returnable schedules for mandatory declarations."),
    ("Wrong document order", "Assemble the pack in the sequence required by the tender instructions."),
    ("Missing pricing schedule", "Do not finalise the submission without the official pricing schedule where required."),
    ("Altered tender forms", "Never change issued tender wording, schedules, or mandatory form structures."),
    ("Unsigned amendments", "Where addenda acknowledgement is required, sign and include every amendment page."),
]


# ═══════════════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════════════

def _hr() -> HRFlowable:
    return HRFlowable(
        width="100%",
        thickness=0.5,
        color=colors.HexColor("#CCCCCC"),
        spaceBefore=6,
        spaceAfter=10,
    )


def _p(text: str, style: ParagraphStyle = CELL_BODY) -> Paragraph:
    """Wrap text in a Paragraph for auto-wrapping in table cells."""
    return Paragraph(text, style)


def _badge(priority: str) -> Paragraph:
    """Return a styled badge Paragraph for the given priority level."""
    priority_upper = priority.strip().upper()
    if priority_upper == "CRITICAL":
        return Paragraph("● Critical", BADGE_CRITICAL)
    elif priority_upper in ("HIGH",):
        return Paragraph("● High", BADGE_HIGH)
    elif priority_upper in ("MEDIUM", "MED"):
        return Paragraph("● Medium", BADGE_MEDIUM)
    elif priority_upper in ("COMPLETE", "YES", "VERIFIED"):
        return Paragraph("✓ Complete", BADGE_COMPLETE)
    elif priority_upper in ("PENDING",):
        return Paragraph("○ Pending", BADGE_PENDING)
    elif priority_upper in ("MISSING", "NO", "NONE"):
        return Paragraph("✗ Missing", BADGE_MISSING)
    else:
        return Paragraph(priority, CELL_BODY)


def _confidence_meter(pct: float, label: str) -> Table:
    """Build a confidence bar with label and percentage."""
    bar_units = max(0, min(10, round(pct / 10)))
    filled = "█" * bar_units
    empty = "░" * (10 - bar_units)
    bar_text = f"{filled}{empty}"

    if pct >= 80:
        bar_style = ParagraphStyle("BarHigh", parent=CELL_BODY, textColor=SUCCESS_GREEN, fontName="Courier", fontSize=10)
    elif pct >= 50:
        bar_style = ParagraphStyle("BarMed", parent=CELL_BODY, textColor=WARNING_AMBER, fontName="Courier", fontSize=10)
    else:
        bar_style = ParagraphStyle("BarLow", parent=CELL_BODY, textColor=ERROR_RED, fontName="Courier", fontSize=10)

    label_cell = [_p(f"<b>{label}</b>", CELL_BODY)]
    bar_cell = [Paragraph(f"{bar_text}  {pct:.0f}%", bar_style)]
    pct_cell = [_p(f"{pct:.0f}%", ParagraphStyle("Pct", parent=CELL_BODY, alignment=TA_RIGHT))]

    meter = Table(
        [label_cell + bar_cell + pct_cell],
        colWidths=[4.5 * cm, 9.0 * cm, 2.0 * cm],
        hAlign="LEFT",
    )
    meter.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return meter


def _build_table(
    headers: List[str],
    rows: List[List[Any]],
    col_widths: List[float],
    header_style: ParagraphStyle = CELL_HEADER,
    cell_style: ParagraphStyle = CELL_BODY,
) -> Table:
    """
    Build a table with Paragraph-wrapped cells, auto-sizing, alternating row colours, and generous padding.
    All cell content is wrapped in Paragraph objects to ensure no overflow and no truncation.
    """
    # Wrap headers in Paragraph
    header_row = [_p(h, header_style) for h in headers]
    # Wrap each cell in Paragraph
    wrapped_rows = []
    for row in rows:
        wrapped_row = []
        for cell in row:
            if isinstance(cell, Paragraph):
                wrapped_row.append(cell)
            elif isinstance(cell, Table):
                wrapped_row.append(cell)
            else:
                wrapped_row.append(_p(str(cell), cell_style))
        wrapped_rows.append(wrapped_row)

    all_data = [header_row] + wrapped_rows
    table = Table(all_data, colWidths=col_widths, hAlign="LEFT", repeatRows=1)

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.2),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 7.6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D0D7DE")),
    ]
    # Alternating row colours
    for idx in range(1, len(wrapped_rows) + 1):
        if idx % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, idx), (-1, idx), LIGHT_BLUE_BG))

    table.setStyle(TableStyle(style_cmds))
    return table


def _generate_qr_code(job_id: str) -> Optional[Image]:
    """Generate a QR code image pointing to the job's processing audit.
    
    Returns None if QR code generation is unavailable (module not installed).
    Never raises an exception — all failures are caught and logged.
    """
    if not QR_AVAILABLE:
        logger.debug("QR code not generated — qrcode module not available")
        return None
    
    try:
        base_url = os.environ.get(
            "PUBLIC_URL",
            os.environ.get("FRONTEND_URL", "https://tender-engine.app"),
        )
        audit_url = f"{base_url.rstrip('/')}/audit/{job_id}"
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=3,
            border=1,
        )
        qr.add_data(audit_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#1F4E79", back_color="white")
        
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        
        return Image(buf, width=1.2 * cm, height=1.2 * cm)
    except Exception as e:
        logger.warning("Failed to generate QR code: %s", e)
        return None


def _build_footer_table(canvas, doc, job_id: str) -> None:
    """Draw the footer on every page with QR code, version, timestamp, and page numbering."""
    canvas.saveState()
    
    # Footer separator line
    canvas.setStrokeColor(PRIMARY_BLUE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, BOTTOM_MARGIN - 0.2 * cm, PAGE_WIDTH - MARGIN, BOTTOM_MARGIN - 0.2 * cm)
    
    # Timestamp
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    
    # Left side: branding
    canvas.setFont("Helvetica", 6.5)
    canvas.setFillColor(TEXT_LIGHT)
    canvas.drawString(MARGIN, 1.0 * cm, "Tender Engine")
    canvas.setFont("Helvetica-Oblique", 6)
    canvas.drawString(MARGIN, 0.5 * cm, "Evidence-Based Document Processing")
    
    # Centre: version, date, time
    canvas.setFont("Helvetica", 6.5)
    canvas.drawCentredString(PAGE_WIDTH / 2, 1.0 * cm, f"v{GUIDE_VERSION} | Generated: {date_str}  {time_str}")
    
    # Right side: page X of Y
    canvas.drawRightString(PAGE_WIDTH - MARGIN, 1.0 * cm, f"Page {doc.page}")
    
    # QR Code — optional enhancement. Never abort PDF generation if unavailable.
    qr_img = _generate_qr_code(job_id)
    if qr_img is not None:
        try:
            qr_img.drawOn(canvas, PAGE_WIDTH - MARGIN - 0.5 * cm, 0.3 * cm)
        except Exception as e:
            logger.warning("Failed to render QR code on canvas: %s", e)
            _draw_qr_fallback(canvas)
    else:
        _draw_qr_fallback(canvas)
    
    canvas.restoreState()


def _draw_qr_fallback(canvas) -> None:
    """Draw a small text note when QR code is unavailable."""
    canvas.setFont("Helvetica-Oblique", 5.5)
    canvas.setFillColor(TEXT_LIGHT)
    canvas.drawRightString(PAGE_WIDTH - MARGIN, 0.5 * cm, "QR code unavailable on this deployment.")


def _status_summary(result_data: Dict[str, Any]) -> Dict[str, Any]:
    extracted_fields = build_extracted_fields(result_data)
    completeness_count = sum(1 for field in extracted_fields if field.get("extracted"))
    completeness = DataCompleteness.calculate(completeness_count, len(extracted_fields))
    missing_info = build_missing_information(result_data)

    pricing_missing = result_data.get("pricing_result") is None
    boq_missing = not bool(result_data.get("boq_items"))
    duration_missing = result_data.get("detected_duration_months") is None
    sector_missing = not bool(result_data.get("detected_sector"))

    hard_stops = sum([pricing_missing, boq_missing, duration_missing, sector_missing])
    if hard_stops == 0 and completeness["percentage"] >= 80:
        return {
            "label": "READY FOR FINAL ASSEMBLY",
            "style": STATUS_READY,
            "badge": _badge("Complete"),
            "summary": "Core tender information is in place. Focus on signatures, attachments, and final checks.",
            "next_action": "Run the printable submission checklist and assemble the final pack.",
            "completeness": completeness,
            "missing_info_count": len(missing_info),
        }
    if hard_stops <= 2 and completeness["percentage"] >= 50:
        return {
            "label": "PARTIALLY READY",
            "style": STATUS_PARTIAL,
            "badge": _badge("Pending"),
            "summary": "You have enough to move forward, but some important gaps still need attention before submission.",
            "next_action": "Complete the missing information and document checklist before final pricing sign-off.",
            "completeness": completeness,
            "missing_info_count": len(missing_info),
        }
    return {
        "label": "NOT READY TO SUBMIT",
        "style": STATUS_NOT_READY,
        "badge": _badge("Missing"),
        "summary": "Critical tender inputs are still missing. Submission would be high-risk if you proceeded now.",
        "next_action": "Start with missing BOQ, pricing, sector, duration, and mandatory company documents.",
        "completeness": completeness,
        "missing_info_count": len(missing_info),
    }


def _build_missing_information_rows(result_data: Dict[str, Any]) -> List[List[Any]]:
    rows: List[List[Any]] = []
    for item in build_missing_information(result_data):
        field_key = item.get("field", "")
        contact = HELPFUL_CONTACTS_DETAILED.get(field_key, "Tender administrator or document owner")
        rows.append(
            [
                f"{item.get('label', 'Unknown')}\nStatus: {item.get('status', 'Missing')}",
                item.get("why_it_matters", ""),
                item.get("where_found", ""),
                contact,
                item.get("recommended_action", item.get('action', '')),
            ]
        )
    return rows


def _build_document_rows(profile: Dict[str, Any]) -> List[List[Any]]:
    rows: List[List[Any]] = []
    for document in profile["documents"]:
        priority = document["priority"]
        badge = _badge(priority)
        contact = HELPFUL_CONTACTS_DETAILED.get(
            document["name"].lower().replace(" ", "_")
            .replace("/", "_").replace("-", "_").replace("__", "_"),
            document["who"].split(",")[0].strip(),
        )
        rows.append(
            [
                badge,
                document["name"],
                "Separate company attachment — not extracted from the tender notice itself.",
                document["where"],
                document["who"],
                document["how"],
            ]
        )
    return rows


def _workflow_steps(result_data: Dict[str, Any], status: Dict[str, Any]) -> List[Tuple[str, str]]:
    steps: List[Tuple[str, str]] = [
        (
            "1. Read the tender instructions first",
            "Before filling in anything, confirm closing time, submission method, file order, compulsory forms, and whether hard copy or portal upload rules apply.",
        ),
    ]
    if not result_data.get("boq_items"):
        steps.append(
            (
                "2. Get the correct BOQ",
                "Ask for the official BOQ attachment or schedule of quantities. Without the real BOQ, pricing and resource planning cannot be finished properly.",
            )
        )
    else:
        steps.append(
            (
                "2. Lock the pricing basis",
                "Work only from the final issued BOQ and addenda. Make sure the estimator and signatory are working from the same version.",
            )
        )
    steps.extend(
        [
            (
                "3. Collect company compliance documents",
                "Pull tax, registration, empowerment, insurance, banking, and any sector-specific certificates before you prepare the final pack.",
            ),
            (
                "4. Complete tender forms line by line",
                "Fill every required field. If something does not apply, write 'N/A' rather than leaving blanks that can be treated as omissions.",
            ),
            (
                "5. Verify signatures and authority",
                "Check who must sign each form, declaration, pricing page, and cover letter. Make sure the signatory has authority to bind the company.",
            ),
            (
                "6. Perform a disqualification check",
                "Run through the mistakes list and checklist in this guide before you print, scan, or upload anything.",
            ),
            (
                "7. Submit early and keep proof",
                "Finish early enough to recover from portal errors, rejected files, or scanner issues, and save proof of submission immediately.",
            ),
        ]
    )
    if status["label"] != "READY FOR FINAL ASSEMBLY":
        steps.append(
            (
                "8. Do not finalise until the gaps are closed",
                "This guide still shows open work. Treat the missing information and missing documents sections as your live punch list.",
            )
        )
    return steps


def _checklist_items(result_data: Dict[str, Any]) -> List[str]:
    currency = result_data.get("detected_currency") or {}
    currency_code = currency.get("currency_code") if isinstance(currency, dict) else None
    pricing_label = f"Currency confirmed ({currency_code})" if currency_code else "Currency confirmed against the tender pricing schedule"
    return [
        "☐  Tender instructions reviewed in full",
        "☐  Closing date, closing time, and submission address/portal rechecked",
        "☐  Final BOQ version confirmed against all addenda",
        "☐  Pricing checked for arithmetic, provisional sums, and VAT",
        f"☐  {pricing_label}",
        "☐  Mandatory forms completed with no blank required fields",
        "☐  Company registration details match supporting documents exactly",
        "☐  Mandatory compliance documents attached and still valid",
        "☐  Every required signature, initial, and date completed",
        "☐  Final submission pack assembled in the required order",
        "☐  Proof of submission plan ready (portal receipt, courier slip, or hand-delivery register)",
    ]


def _readiness_questions(result_data: Dict[str, Any]) -> List[List[Any]]:
    has_pricing = result_data.get("pricing_result") is not None
    has_boq = bool(result_data.get("boq_items"))
    has_duration = result_data.get("detected_duration_months") is not None
    has_sector = bool(result_data.get("detected_sector"))

    return [
        ["Do you have the final BOQ that will be submitted?", _badge("Yes" if has_boq else "Missing"),
         "Submission should stop if this answer is 'No'."],
        ["Has the pricing been completed and reviewed?", _badge("Yes" if has_pricing else "Missing"),
         "Do not rely on draft figures for final submission."],
        ["Is the contract duration confirmed from the tender documents?", _badge("Yes" if has_duration else "Missing"),
         "Duration affects pricing, programme, and resources."],
        ["Is the project sector/work scope understood clearly?", _badge("Yes" if has_sector else "Missing"),
         "The wrong scope assumption can invalidate pricing and compliance."],
        ["Have all supporting company documents been physically checked?", _badge("Pending"),
         "This guide cannot verify separate attachments automatically."],
        ["Are all signatures and dates complete?", _badge("Pending"),
         "Final manual check required before upload/printing."],
    ]


def _build_extracted_evidence_rows(result_data: Dict[str, Any]) -> List[List[Any]]:
    rows: List[List[Any]] = []
    for field in build_extracted_fields(result_data):
        if not field.get("extracted"):
            continue

        value = field.get("value", "")
        if isinstance(value, list):
            value_text = ", ".join(str(v) for v in value)
        elif isinstance(value, dict):
            summary_parts = []
            for key, item_value in list(value.items())[:4]:
                summary_parts.append(f"{key}: {item_value}")
            value_text = "; ".join(summary_parts)
            if len(value) > 4:
                value_text += "; ..."
        else:
            value_text = str(value)
        value_text = value_text.replace("\r", " ").replace("\n", " ").strip()
        if len(value_text) > 220:
            value_text = value_text[:217].rstrip() + "..."

        paragraph = str(field.get("paragraph_or_sentence") or "").replace("\r", " ").replace("\n", " ").strip()
        if len(paragraph) > 160:
            paragraph = paragraph[:157].rstrip() + "..."

        verified_lines = [
            f"Verified From: {field.get('verified_from') or 'Unknown'}",
            f"Page: {field.get('page') or 'Unknown'}",
            f"Confidence: {field.get('confidence') or 'Missing'}",
        ]
        if paragraph:
            verified_lines.append(f"Evidence: {paragraph}")
        if field.get("warning"):
            verified_lines.append(field["warning"])
        rows.append([
            field.get("label", "Unknown"),
            value_text,
            "\n".join(verified_lines),
        ])
    return rows


def _calculate_dashboard_metrics(result_data: Dict[str, Any]) -> Dict[str, float]:
    metadata = result_data.get("metadata", {})
    metadata_fields = ["tender_number", "employer", "project_title"]
    metadata_found = sum(1 for f in metadata_fields if metadata.get(f) or result_data.get(f))
    metadata_pct = (metadata_found / len(metadata_fields)) * 100

    tender_fields = [
        result_data.get("detected_currency"),
        result_data.get("detected_locations"),
        result_data.get("detected_duration_months"),
        result_data.get("detected_sector"),
        metadata.get("closing_date") or result_data.get("closing_date"),
    ]
    tender_pct = (sum(1 for item in tender_fields if item) / len(tender_fields)) * 100

    boq_items = result_data.get("boq_items", [])
    boq_count = len(boq_items) if boq_items else 0
    boq_pct = 100.0 if boq_count > 0 else 0.0

    pricing_pct = 100.0 if result_data.get("pricing_result") else 0.0

    compliance_fields = ["detected_sector", "detected_duration_months", "detected_locations", "detected_currency"]
    compliance_found = sum(1 for f in compliance_fields if result_data.get(f))
    compliance_pct = (compliance_found / len(compliance_fields)) * 100

    overall_pct = round((metadata_pct * 0.20 + tender_pct * 0.25 + boq_pct * 0.25 + pricing_pct * 0.15 + compliance_pct * 0.15), 1)
    return {
        "metadata_pct": metadata_pct,
        "tender_pct": tender_pct,
        "boq_pct": boq_pct,
        "pricing_pct": pricing_pct,
        "compliance_pct": compliance_pct,
        "overall_pct": overall_pct,
    }


def _dashboard_status_label(overall_pct: float) -> str:
    if overall_pct >= 80:
        return "HIGH"
    if overall_pct >= 50:
        return "MEDIUM"
    return "LOW"


def _status_icon(status_text: str) -> str:
    normalized = status_text.upper()
    if "VERIFIED" in normalized or status_text == "✓ Verified":
        return "✓"
    if "MANUAL" in normalized or "REVIEW" in normalized:
        return "⚠"
    if "MISSING" in normalized:
        return "✗"
    if "N/A" in normalized:
        return "–"
    return "○"


def _build_executive_summary(result_data: Dict[str, Any], status: Dict[str, Any]) -> List[Any]:
    metrics = _calculate_dashboard_metrics(result_data)
    health = _calculate_tender_health_score(result_data)
    metadata = result_data.get("metadata", {})
    currency = result_data.get("detected_currency") or {}
    currency_code = currency.get("currency_code") if isinstance(currency, dict) else None
    closing_date = metadata.get("closing_date") or result_data.get("closing_date")
    pricing_available = result_data.get("pricing_result") is not None
    boq_available = bool(result_data.get("boq_items"))

    employer_field = next((f for f in build_extracted_fields(result_data) if f.get("field") == "employer"), None)
    employer_status = "⚠ Manual Verification Required"
    if employer_field and employer_field.get("extracted"):
        confidence = str(employer_field.get("confidence") or "").lower()
        employer_status = "✓ Verified" if confidence == "high" else "⚠ Manual Verification Required"

    summary_rows = [
        ["Tender Number", "✓ Verified" if metadata.get("tender_number") or result_data.get("tender_number") else "✗ Missing"],
        ["Project", "✓ Verified" if metadata.get("project_title") or result_data.get("project_title") else "✗ Missing"],
        ["Employer", employer_status],
        ["Currency", f"✓ {currency_code}" if currency_code else "✗ Missing"],
        ["Closing Date", "✓ Verified" if closing_date else "✗ Missing"],
        ["BOQ", "✓ Verified" if boq_available else "✗ Missing"],
        ["Pricing", "✓ Verified" if pricing_available else "✗ Missing"],
        ["Supporting Documents", "⚠ Manual Verification Required"],
        ["Estimated Remaining Work", _estimate_remaining_work_label(result_data)],
        ["Submission Recommendation", _final_decision_label(status)],
    ]

    title_style = ParagraphStyle("ExecutiveSummaryTitle", parent=SECTION_STYLE, fontSize=18, leading=22, alignment=TA_CENTER)
    value_style = ParagraphStyle("ExecutiveSummaryValue", parent=BODY_BOLD, fontSize=12, leading=16)
    recommendation_style = ParagraphStyle(
        "ExecutiveRecommendation",
        parent=BODY_BOLD,
        fontSize=18,
        leading=22,
        alignment=TA_CENTER,
        textColor=ERROR_RED if "DO NOT SUBMIT" in _final_decision_label(status) else WARNING_AMBER if "REVIEW" in _final_decision_label(status) else SUCCESS_GREEN,
    )

    elements: List[Any] = []
    elements.append(Paragraph("EXECUTIVE SUMMARY", title_style))
    elements.append(_hr())
    executive_table = Table(
        [[_p(f"<b>{label}</b>", value_style), _p(value, value_style)] for label, value in summary_rows[:-1]],
        colWidths=[5.4 * cm, 10.2 * cm],
        hAlign="LEFT",
    )
    executive_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D7DE")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
    ]))
    health_style = ParagraphStyle(
        "TenderHealthStyle",
        parent=BODY_BOLD,
        fontSize=18,
        leading=22,
        alignment=TA_CENTER,
        textColor=SUCCESS_GREEN if health["score"] >= 80 else WARNING_AMBER if health["score"] >= 50 else ERROR_RED,
    )
    executive_block = KeepTogether([
        executive_table,
        Spacer(1, 0.35 * cm),
        Paragraph("Tender Health Score", SUBSECTION_STYLE),
        Paragraph(f"{health['score']}/100", health_style),
        Paragraph(f"Submission-readiness status: {health['status']}", ParagraphStyle("TenderHealthNote", parent=SMALL, alignment=TA_CENTER)),
        Spacer(1, 0.25 * cm),
        Paragraph("Submission Recommendation", SUBSECTION_STYLE),
        Paragraph(summary_rows[-1][1], recommendation_style),
        Spacer(1, 0.2 * cm),
        Paragraph(f"Overall Extraction Status: {_dashboard_status_label(metrics['overall_pct'])}", ParagraphStyle("ExecStatusLine", parent=SMALL, alignment=TA_CENTER)),
    ])
    elements.append(executive_block)
    return elements


def _build_confidence_summary(result_data: Dict[str, Any]) -> List[Any]:
    """Build an executive extraction dashboard."""
    elements: List[Any] = []
    metrics = _calculate_dashboard_metrics(result_data)
    overall_label = _dashboard_status_label(metrics["overall_pct"])
    overall_color = SUCCESS_GREEN if overall_label == "HIGH" else WARNING_AMBER if overall_label == "MEDIUM" else ERROR_RED

    elements.append(Paragraph("2. Document Status Dashboard", SECTION_STYLE))
    elements.append(_hr())
    elements.append(Paragraph("This dashboard shows deterministic extraction coverage by document area without cluttered percentage-heavy reporting.", BODY))
    elements.append(Spacer(1, 0.25 * cm))
    elements.append(_confidence_meter(metrics["metadata_pct"], "Document Metadata"))
    elements.append(Spacer(1, 0.15 * cm))
    elements.append(_confidence_meter(metrics["tender_pct"], "Tender Details"))
    elements.append(Spacer(1, 0.15 * cm))
    elements.append(_confidence_meter(metrics["boq_pct"], "BOQ"))
    elements.append(Spacer(1, 0.15 * cm))
    elements.append(_confidence_meter(metrics["pricing_pct"], "Pricing"))
    elements.append(Spacer(1, 0.15 * cm))
    elements.append(_confidence_meter(metrics["compliance_pct"], "Compliance"))
    elements.append(Spacer(1, 0.3 * cm))
    elements.append(Paragraph("Overall Extraction Status", SUBSECTION_STYLE))
    elements.append(Paragraph(overall_label, ParagraphStyle("OverallExtractionStatus", parent=BODY_BOLD, fontSize=18, leading=22, alignment=TA_CENTER, textColor=overall_color)))

    evidence_fields = ((result_data.get("evidence") or {}).get("fields", {}) or {})
    counts = {"High": 0, "Medium": 0, "Low": 0, "Missing": 0}
    for field in evidence_fields.values():
        confidence = str(field.get("confidence") or ("Missing" if field.get("value") in (None, "", [], {}) else "Low")).title()
        if confidence not in counts:
            confidence = "Missing"
        counts[confidence] += 1

    elements.append(Spacer(1, 0.25 * cm))
    elements.append(Paragraph("Extraction Confidence Summary", SUBSECTION_STYLE))
    elements.append(_build_table(["High Confidence", "Medium Confidence", "Low Confidence", "Missing"], [[str(counts["High"]), str(counts["Medium"]), str(counts["Low"]), str(counts["Missing"])]], [4.1 * cm, 4.1 * cm, 4.1 * cm, 4.1 * cm]))
    return elements


def _estimate_remaining_work_label(result_data: Dict[str, Any]) -> str:
    missing_count = len(build_missing_information(result_data))
    if missing_count == 0:
        return "0–1 Hours"
    if missing_count <= 3:
        return "2–4 Hours"
    if missing_count <= 6:
        return "4–8 Hours"
    return "8–16 Hours"


def _build_estimated_completion(result_data: Dict[str, Any], status: Dict[str, Any]) -> List[Any]:
    """Build an estimated completion plan."""
    elements: List[Any] = []
    missing_items = build_missing_information(result_data)
    missing_count = len(missing_items)
    est_hours = _estimate_remaining_work_label(result_data)

    today_tasks: List[str] = []
    tomorrow_tasks: List[str] = []

    for item in missing_items[:3]:
        today_tasks.append(f"□ {item.get('label', 'Resolve missing item')}")
    if not result_data.get("boq_items") and "□ Obtain BOQ" not in today_tasks:
        today_tasks.insert(0, "□ Obtain BOQ")
    if result_data.get("pricing_result") is None and "□ Complete Pricing" not in today_tasks:
        today_tasks.append("□ Complete Pricing")
    employer_present = any(f.get("field") == "employer" and f.get("extracted") for f in build_extracted_fields(result_data))
    if not employer_present and "□ Verify Employer" not in today_tasks:
        today_tasks.append("□ Verify Employer")
    if not today_tasks:
        today_tasks = ["□ Final internal review", "□ Confirm signatures", "□ Prepare submission proof"]

    tomorrow_defaults = ["□ Review Compliance", "□ Verify Documents", "□ Final Review"]
    tomorrow_tasks.extend(tomorrow_defaults)

    elements.append(Paragraph("3. Estimated Completion Plan", SECTION_STYLE))
    elements.append(_hr())
    elements.append(Paragraph("Use this plan to organise the remaining deterministic completion work before submission.", BODY))
    elements.append(Spacer(1, 0.2 * cm))
    elements.append(_build_table(["Metric", "Value"], [["Estimated Remaining Work", est_hours], ["Open Information Items", str(missing_count)], ["Current Submission Position", status["label"]]], [5.5 * cm, 9.8 * cm]))
    elements.append(Spacer(1, 0.3 * cm))
    elements.append(Paragraph("Today's Work", SUBSECTION_STYLE))
    for task in today_tasks[:6]:
        elements.append(Paragraph(task, CHECKLIST_STYLE))
    elements.append(Spacer(1, 0.15 * cm))
    elements.append(Paragraph("Tomorrow", SUBSECTION_STYLE))
    for task in tomorrow_tasks[:6]:
        elements.append(Paragraph(task, CHECKLIST_STYLE))
    elements.append(Spacer(1, 0.2 * cm))
    elements.append(Paragraph(f"Estimated Completion: <b>{est_hours}</b>", BODY_BOLD))
    return elements


# ═══════════════════════════════════════════════════════════════════════════
# Main Generation Function
# ═══════════════════════════════════════════════════════════════════════════

def _build_document_navigation_rows(result_data: Dict[str, Any]) -> List[List[Any]]:
    rows: List[List[Any]] = []
    for section in result_data.get("document_sections", []) or []:
        rows.append([
            str(section.get("section_type", "")).replace("_", " ").title(),
            section.get("heading", ""),
            str(section.get("page", "Unknown")),
            section.get("confidence", "Unknown"),
        ])
    return rows


def _build_decision_support_rows(result_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    action_plan = build_action_plan(result_data)
    for item in action_plan.get("critical", []) + action_plan.get("required", []) + action_plan.get("optional", []):
        rows.append({
            "priority": item.get("priority", "Unknown"),
            "action": item.get("action", ""),
            "reason": item.get("reason", ""),
            "evidence": item.get("evidence", ""),
            "estimated_time": item.get("estimated_time", ""),
            "responsible_person": item.get("responsible_person", ""),
            "required_documents": item.get("required_documents", []) or [],
            "completion_steps": item.get("completion_steps", []) or [],
            "risk_if_ignored": item.get("risk_if_ignored", ""),
        })
    return rows


def _build_action_cards(action_items: List[Dict[str, Any]]) -> List[Any]:
    elements: List[Any] = []
    card_label_style = ParagraphStyle("ActionCardLabel", parent=BODY_BOLD, fontSize=9.5, leading=12, textColor=PRIMARY_BLUE)
    card_value_style = ParagraphStyle("ActionCardValue", parent=BODY, fontSize=8.7, leading=12, wordWrap="CJK")

    for index, item in enumerate(action_items, start=1):
        priority_text = str(item.get("priority", "Unknown"))
        docs = ", ".join(str(doc) for doc in item.get("required_documents", [])) or "None specified"
        steps = item.get("completion_steps", []) or []
        if isinstance(steps, list):
            steps_text = "<br/>".join(f"• {step}" for step in steps) if steps else "No step-by-step actions provided"
        else:
            steps_text = str(steps)

        card_rows = [
            [_p("Action", card_label_style), _p(str(item.get("action", "")) or "Not specified", card_value_style)],
            [_p("Priority", card_label_style), _badge(priority_text) if priority_text.upper() in {"CRITICAL", "HIGH", "MEDIUM", "PENDING", "MISSING"} else _p(priority_text, card_value_style)],
            [_p("Reason", card_label_style), _p(str(item.get("reason", "")) or "Not specified", card_value_style)],
            [_p("Evidence", card_label_style), _p(str(item.get("evidence", "")) or "No direct evidence extracted", card_value_style)],
            [_p("Estimated Time", card_label_style), _p(str(item.get("estimated_time", "")) or "Not specified", card_value_style)],
            [_p("Responsible Person", card_label_style), _p(str(item.get("responsible_person", "")) or "Not specified", card_value_style)],
            [_p("Required Documents", card_label_style), _p(docs, card_value_style)],
            [_p("Completion Steps", card_label_style), _p(steps_text, card_value_style)],
            [_p("Risk if Ignored", card_label_style), _p(str(item.get("risk_if_ignored", "")) or "Not specified", card_value_style)],
        ]

        card = Table(card_rows, colWidths=[3.4 * cm, 12.6 * cm], hAlign="LEFT")
        card.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), VERY_LIGHT_BG if 'VERY_LIGHT_BG' in globals() else LIGHT_BLUE_BG),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#C9D4E5")),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#DCE3EC")),
            ("BACKGROUND", (0, 0), (0, -1), LIGHT_BLUE_BG),
        ]))

        elements.append(Paragraph(f"Action {index}", SUBSECTION_STYLE))
        elements.append(card)
        elements.append(Spacer(1, 0.2 * cm))
    return elements


def _final_decision_label(status: Dict[str, Any]) -> str:
    if status["label"] == "READY FOR FINAL ASSEMBLY":
        return "SUBMIT AFTER FINAL CHECKS"
    if status["label"] == "PARTIALLY READY":
        return "REVIEW BEFORE SUBMISSION"
    return "DO NOT SUBMIT"


def _group_missing_information(result_data: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    groups = {"Critical Items": [], "Required Items": [], "Optional Items": []}
    for item in build_missing_information(result_data):
        field = item.get("field", "")
        if field in {"boq_items", "pricing_result", "closing_date", "submission_method"}:
            groups["Critical Items"].append(item)
        elif field in {"employer", "detected_locations", "detected_duration_months", "detected_currency", "detected_sector"}:
            groups["Required Items"].append(item)
        else:
            groups["Optional Items"].append(item)
    return groups


def _split_document_rows(document_rows: List[List[Any]]) -> Tuple[List[List[Any]], List[List[Any]]]:
    tender_docs: List[List[Any]] = []
    company_docs: List[List[Any]] = []
    tender_keywords = ["boq", "scope", "pricing", "schedule", "form", "drawing", "appendix"]
    for row in document_rows:
        document_name = str(row[1]).lower() if len(row) > 1 else ""
        if any(keyword in document_name for keyword in tender_keywords):
            tender_docs.append(row)
        else:
            company_docs.append(row)
    return tender_docs, company_docs


def _build_final_decision_reasons(result_data: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    currency = result_data.get("detected_currency") or {}
    if isinstance(currency, dict) and currency.get("currency_code"):
        reasons.append("✓ Currency identified")
    else:
        reasons.append("✗ Currency missing")
    if result_data.get("detected_sector"):
        reasons.append("✓ Sector identified")
    else:
        reasons.append("✗ Sector missing")
    if result_data.get("boq_items"):
        reasons.append("✓ BOQ available")
    else:
        reasons.append("✗ BOQ missing")
    if result_data.get("pricing_result"):
        reasons.append("✓ Pricing available")
    else:
        reasons.append("✗ Pricing incomplete")
    closing_date = (result_data.get("metadata") or {}).get("closing_date") or result_data.get("closing_date")
    if closing_date:
        reasons.append("✓ Closing Date identified")
    else:
        reasons.append("✗ Closing Date missing")
    return reasons


def _calculate_tender_health_score(result_data: Dict[str, Any]) -> Dict[str, Any]:
    extracted_fields = build_extracted_fields(result_data)
    total_fields = len(extracted_fields)
    extracted_count = sum(1 for field in extracted_fields if field.get("extracted"))
    completeness_points = round((extracted_count / max(1, total_fields)) * 40)

    mandatory_checks = {
        "Tender Number": bool((result_data.get("metadata") or {}).get("tender_number") or result_data.get("tender_number")),
        "Project Title": bool((result_data.get("metadata") or {}).get("project_title") or result_data.get("project_title")),
        "Employer": any(field.get("field") == "employer" and field.get("extracted") for field in extracted_fields),
        "Closing Date": bool((result_data.get("metadata") or {}).get("closing_date") or result_data.get("closing_date")),
        "Currency": bool(isinstance(result_data.get("detected_currency"), dict) and (result_data.get("detected_currency") or {}).get("currency_code")),
        "Location": bool(result_data.get("detected_locations")),
        "Submission Method": bool(result_data.get("submission_method") or (result_data.get("metadata") or {}).get("submission_method")),
        "Mandatory Documents": bool(result_data.get("mandatory_documents") or ((result_data.get("evidence") or {}).get("fields", {}) or {}).get("mandatory_documents")),
    }
    mandatory_points = round((sum(1 for ok in mandatory_checks.values() if ok) / len(mandatory_checks)) * 25)

    boq_points = 20 if bool(result_data.get("boq_items")) else 0
    pricing_points = 10 if result_data.get("pricing_result") else 0

    supporting_docs_profile = JURISDICTION_DOCUMENTS.get(SchemaManager.detect_jurisdiction(result_data), JURISDICTION_DOCUMENTS["default"])
    supporting_docs_present = len(supporting_docs_profile.get("documents", [])) > 0
    supporting_doc_points = 5 if supporting_docs_present else 0

    score = max(0, min(100, completeness_points + mandatory_points + boq_points + pricing_points + supporting_doc_points))
    breakdown = [
        ["Document completeness", f"{completeness_points}/40"],
        ["Mandatory fields found", f"{mandatory_points}/25"],
        ["BOQ availability", f"{boq_points}/20"],
        ["Pricing completion", f"{pricing_points}/10"],
        ["Supporting documents checklist", f"{supporting_doc_points}/5"],
    ]
    if score >= 80:
        status = "Strong"
    elif score >= 50:
        status = "Needs Work"
    else:
        status = "High Risk"
    return {
        "score": score,
        "status": status,
        "breakdown": breakdown,
    }


def generate_completion_guide(job_id: str, result_data: Dict[str, Any]) -> BytesIO:
    """Generate the Tender Completion Guide PDF."""
    buffer = BytesIO()
    status = _status_summary(result_data)
    jurisdiction_code = SchemaManager.detect_jurisdiction(result_data)
    profile = JURISDICTION_DOCUMENTS.get(jurisdiction_code, JURISDICTION_DOCUMENTS["default"])
    missing_info_rows = _build_missing_information_rows(result_data)
    document_rows = _build_document_rows(profile)
    workflow_steps = _workflow_steps(result_data, status)
    checklist_items = _checklist_items(result_data)
    readiness_rows = _readiness_questions(result_data)
    grouped_missing = _group_missing_information(result_data)
    tender_document_rows, company_document_rows = _split_document_rows(document_rows)
    filename = result_data.get("filename", "Unknown tender")
    now = datetime.now()

    def _header_footer(canvas, doc):
        canvas.saveState()

        # Header
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(TEXT_LIGHT)
        canvas.drawString(MARGIN, PAGE_HEIGHT - 1.4 * cm, "Tender Completion Guide")
        canvas.setFont("Helvetica-Oblique", 6.5)
        canvas.drawString(MARGIN, PAGE_HEIGHT - 1.8 * cm, "Evidence-Based Document Processing")
        canvas.drawRightString(PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 1.4 * cm, f"Job: {job_id[:16]}")
        canvas.drawRightString(PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 1.8 * cm, f"v{GUIDE_VERSION}")

        # Header separator
        canvas.setStrokeColor(PRIMARY_BLUE)
        canvas.setLineWidth(0.4)
        canvas.line(MARGIN, PAGE_HEIGHT - 2.0 * cm, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 2.0 * cm)

        # Footer
        _build_footer_table(canvas, doc, job_id)

        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=TOP_MARGIN,
        bottomMargin=BOTTOM_MARGIN,
        title=f"Tender Completion Guide - {filename}",
        author="Tender Engine",
        subject="Tender Completion Guide - Evidence-Based Document Processing",
    )

    story: List[Any] = []

    # ═════════════════════════════════════════════════════════════════════
    # COVER PAGE
    # ═════════════════════════════════════════════════════════════════════
    story.append(Spacer(1, 3.0 * cm))
    story.append(Paragraph("TENDER COMPLETION GUIDE", COVER_TITLE))
    story.append(
        Paragraph(
            "Practical instruction manual for a first-time contractor preparing the final tender submission.",
            COVER_SUBTITLE,
        )
    )
    story.append(HRFlowable(width="60%", thickness=2.5, color=PRIMARY_BLUE, spaceBefore=6, spaceAfter=14))
    story.append(
        Paragraph(
            "Use this guide to finish the work that still remains before submission. "
            "It does not repeat the roadmap, audit, readiness report, or submission letter.",
            BODY,
        )
    )
    story.append(Spacer(1, 0.6 * cm))
    story.append(
        _build_table(
            ["Guide Item", "Value"],
            [
                ["Document", filename],
                ["Jurisdiction", profile["name"]],
                ["Purpose", "Completion actions, missing items, document pack checks, and submission readiness"],
                ["Version", GUIDE_VERSION],
                ["Generated", now.strftime("%Y-%m-%d %H:%M")],
            ],
            [4.2 * cm, 11.1 * cm],
        )
    )
    story.append(Spacer(1, 0.6 * cm))
    story.append(Paragraph(status["label"], status["style"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(status["summary"], BODY))
    story.append(PageBreak())

    story.extend(_build_executive_summary(result_data, status))
    story.append(PageBreak())

    navigation_rows = _build_document_navigation_rows(result_data)
    if navigation_rows:
        story.append(Paragraph("1. Document Navigation by Section", SECTION_STYLE))
        story.append(_hr())
        story.append(Paragraph("Detected document sections are listed below so reviewers can navigate the tender structure quickly.", BODY))
        story.append(Spacer(1, 0.2 * cm))
        story.append(_build_table(["Section", "Heading", "Page", "Confidence"], navigation_rows, [3.0 * cm, 8.6 * cm, 2.0 * cm, 3.0 * cm]))
        story.append(PageBreak())

    # ═════════════════════════════════════════════════════════════════════
    # 1. COMPLETION STATUS
    # ═════════════════════════════════════════════════════════════════════
    story.append(Paragraph("1. Completion Status", SECTION_STYLE))
    story.append(_hr())
    story.append(Paragraph(status["label"], status["style"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(status["summary"], BODY))
    story.append(Paragraph(f"<b>Next best action:</b> {status['next_action']}", BODY))
    completeness = status["completeness"]
    bar_style = ParagraphStyle(
        "ExecutiveGaugeBar",
        parent=CELL_BODY,
        fontName="Courier",
        fontSize=18,
        leading=22,
        alignment=TA_CENTER,
        textColor=(SUCCESS_GREEN if completeness["percentage"] >= 80 else WARNING_AMBER if completeness["percentage"] >= 50 else ERROR_RED),
    )
    story.append(Spacer(1, 0.35 * cm))
    story.append(Paragraph("Submission Readiness", ParagraphStyle("SubmissionReadinessLabel", parent=BODY_BOLD, fontSize=16, leading=20, alignment=TA_CENTER)))
    story.append(Paragraph(completeness["bar"], bar_style))
    story.append(Paragraph(f"{completeness['percentage']}%", ParagraphStyle("SubmissionReadinessPercent", parent=BODY_BOLD, fontSize=18, leading=22, alignment=TA_CENTER)))
    story.append(Spacer(1, 0.25 * cm))
    story.append(_build_table(["Indicator", "Current Position"], [["Information readiness", completeness["label"]], ["Pricing available", "Yes" if result_data.get("pricing_result") else "No"], ["BOQ available", "Yes" if result_data.get("boq_items") else "No"], ["Final pack stage", "Assembly" if status["label"] == "READY FOR FINAL ASSEMBLY" else "Still in completion phase"]], [5 * cm, 10.3 * cm]))
    story.append(PageBreak())

    # ═════════════════════════════════════════════════════════════════════
    # 2. WHAT WAS EXTRACTED AND VERIFIED
    # ═════════════════════════════════════════════════════════════════════
    story.append(Paragraph("2. Verified Extracted Information", SECTION_STYLE))
    story.append(_hr())
    story.append(
        Paragraph(
            "Each extracted value below includes where it was found, how confident the extraction is, and whether it should be verified before submission.",
            BODY,
        )
    )
    story.append(Spacer(1, 0.2 * cm))
    extracted_rows = _build_extracted_evidence_rows(result_data)
    if extracted_rows:
        story.append(
            _build_table(
                ["Field", "Extracted Value", "Verified From"],
                extracted_rows,
                [3.6 * cm, 5.2 * cm, 7.8 * cm],
            )
        )
    else:
        story.append(Paragraph("No verified extracted information is currently available.", BODY))
    story.append(PageBreak())

    # ═════════════════════════════════════════════════════════════════════
    # 3. DOCUMENT STATUS DASHBOARD
    # ═════════════════════════════════════════════════════════════════════
    story.extend(_build_confidence_summary(result_data))
    story.append(PageBreak())

    # ═════════════════════════════════════════════════════════════════════
    # 4. ESTIMATED COMPLETION PLAN
    # ═════════════════════════════════════════════════════════════════════
    story.extend(_build_estimated_completion(result_data, status))
    story.append(PageBreak())

    # ═════════════════════════════════════════════════════════════════════
    # 5. EVIDENCE-BASED ACTIONS
    # ═════════════════════════════════════════════════════════════════════
    story.append(Paragraph("5. Evidence-Based Actions", SECTION_STYLE))
    story.append(_hr())
    story.append(Paragraph("Actions below are generated only from extracted evidence and unresolved fields. They are intended to guide completion work before submission.", BODY))
    story.append(Spacer(1, 0.2 * cm))
    decision_rows = _build_decision_support_rows(result_data)
    if decision_rows:
        priority_counts = {"Critical": 0, "High": 0, "Medium": 0, "Other": 0}
        for item in decision_rows:
            priority = str(item.get("priority", "Other")).strip().title()
            if priority in priority_counts:
                priority_counts[priority] += 1
            else:
                priority_counts["Other"] += 1
        story.append(_build_table(
            ["Metric", "Value"],
            [["Total Actions", str(len(decision_rows))], ["Critical", str(priority_counts["Critical"])], ["High", str(priority_counts["High"])], ["Medium", str(priority_counts["Medium"])], ["Other", str(priority_counts["Other"])]],
            [5.0 * cm, 4.0 * cm],
        ))
        story.append(Spacer(1, 0.25 * cm))
        story.extend(_build_action_cards(decision_rows))
    else:
        story.append(Paragraph("No unresolved evidence-based actions were generated from the current result.", BODY))
    story.append(PageBreak())

    # ═════════════════════════════════════════════════════════════════════
    # 6. MISSING INFORMATION
    # ═════════════════════════════════════════════════════════════════════
    story.append(Paragraph("5. Missing Information", SECTION_STYLE))
    story.append(_hr())
    story.append(
        Paragraph(
            "This section explains each information gap in plain language so a contractor knows exactly what is still missing, "
            "where to find it, who normally supplies it, and how to finish it.",
            BODY,
        )
    )
    story.append(Spacer(1, 0.2 * cm))

    has_grouped_missing_items = False
    for group_name in ["Critical Items", "Required Items", "Optional Items"]:
        items = grouped_missing.get(group_name, [])
        story.append(Paragraph(group_name, SUBSECTION_STYLE))
        if not items:
            story.append(Paragraph("No items currently grouped in this category.", BODY))
            story.append(Spacer(1, 0.15 * cm))
            continue
        has_grouped_missing_items = True
        grouped_rows = []
        for item in items:
            field_key = item.get("field", "")
            contact = HELPFUL_CONTACTS_DETAILED.get(field_key, "Tender administrator or document owner")
            grouped_rows.append([
                f"{item.get('label', 'Unknown')}\nStatus: {item.get('status', 'Missing')}",
                item.get("why_it_matters", ""),
                item.get("where_found", ""),
                contact,
                item.get("recommended_action", item.get('action', '')),
            ])
        story.append(_build_table(["Missing Item", "Why It Matters", "Where to Find It", "Who Provides It", "How to Complete It"], grouped_rows, [2.8 * cm, 3.6 * cm, 3.2 * cm, 3.2 * cm, 3.8 * cm]))
        story.append(Spacer(1, 0.15 * cm))
    if not has_grouped_missing_items:
        story.append(Paragraph("No unresolved information gaps were detected in the current processing result.", BODY))
    story.append(PageBreak())

    # ═════════════════════════════════════════════════════════════════════
    # 7. MISSING DOCUMENTS
    # ═════════════════════════════════════════════════════════════════════
    story.append(Paragraph("6. Missing Documents", SECTION_STYLE))
    story.append(_hr())
    story.append(
        Paragraph(
            "These are the supporting documents a contractor normally has to attach separately. "
            "They are treated as pending until someone on your team has physically checked them.",
            BODY,
        )
    )
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph("Tender Documents", SUBSECTION_STYLE))
    story.append(_build_table(["Priority", "Document", "Why It Appears Missing", "Where to Get It", "Who Provides It", "How to Complete It"], tender_document_rows or [["—", "No tender-document checklist items configured", "", "", "", ""]], [1.4 * cm, 2.9 * cm, 3.4 * cm, 2.7 * cm, 2.6 * cm, 3.2 * cm]))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph("Company Documents", SUBSECTION_STYLE))
    story.append(_build_table(["Priority", "Document", "Why It Appears Missing", "Where to Get It", "Who Provides It", "How to Complete It"], company_document_rows or document_rows, [1.4 * cm, 2.9 * cm, 3.4 * cm, 2.7 * cm, 2.6 * cm, 3.2 * cm]))
    story.append(PageBreak())

    # ═════════════════════════════════════════════════════════════════════
    # 8. RECOMMENDED WORKFLOW
    # ═════════════════════════════════════════════════════════════════════
    story.append(Paragraph("7. Recommended Workflow", SECTION_STYLE))
    story.append(_hr())
    story.append(
        Paragraph(
            "Follow this sequence to move from partial tender data to a properly assembled submission pack.",
            BODY,
        )
    )
    story.append(Spacer(1, 0.2 * cm))
    for title, detail in workflow_steps:
        story.append(Paragraph(title, SUBSECTION_STYLE))
        story.append(Paragraph(detail, BODY))
        story.append(Spacer(1, 0.1 * cm))
    story.append(PageBreak())

    # ═════════════════════════════════════════════════════════════════════
    # 7. PRINTABLE SUBMISSION CHECKLIST
    # ═════════════════════════════════════════════════════════════════════
    story.append(Paragraph("8. Printable Submission Checklist", SECTION_STYLE))
    story.append(_hr())
    story.append(
        Paragraph(
            "Print this page and tick every box before submission. This is meant for desk use during the final pack review.",
            BODY,
        )
    )
    story.append(Spacer(1, 0.2 * cm))
    for item in checklist_items:
        story.append(Paragraph(item, CHECKLIST_STYLE))
    story.append(Spacer(1, 0.3 * cm))
    story.append(
        Paragraph(
            "Tip: do this check with the final printed or uploaded pack in front of you, not from memory.",
            SMALL,
        )
    )
    story.append(PageBreak())

    # ═════════════════════════════════════════════════════════════════════
    # 8. COMMON DISQUALIFICATION MISTAKES
    # ═════════════════════════════════════════════════════════════════════
    story.append(Paragraph("9. Common Disqualification Mistakes", SECTION_STYLE))
    story.append(_hr())
    story.append(
        Paragraph(
            "These are the mistakes that regularly sink otherwise good bids. Use them as a last-minute guardrail.",
            BODY,
        )
    )
    story.append(Spacer(1, 0.2 * cm))
    disqualification_rows = [[name, guidance] for name, guidance in (profile.get("mistakes", []) + DEFAULT_DISQUALIFICATION_MISTAKES)]
    story.append(_build_table(["Mistake", "How to Avoid It"], disqualification_rows, [5.0 * cm, 11.6 * cm]))
    story.append(PageBreak())

    # ═════════════════════════════════════════════════════════════════════
    # 9. HELPFUL TENDER TIPS
    # ═════════════════════════════════════════════════════════════════════
    story.append(Paragraph("10. Helpful Tender Tips", SECTION_STYLE))
    story.append(_hr())
    tip_rows = [
        ["1", "Keep a live folder for standard company documents so you do not scramble for certificates every time a tender closes."],
        ["2", "Name files in submission order before you upload them. It reduces mistakes when portals show only filenames."],
        ["3", "Have a second person check totals, VAT, signatures, and document order. Fresh eyes catch expensive misses."],
        ["4", "Where the tender is silent, do not guess. Ask the tender contact in writing before closing date."],
        ["5", "Finish scanning and merging PDFs early. File-size, password, and upside-down scan issues waste closing-day time."],
        ["6", "Keep proof of submission, the final pack, and the pricing backup in one place immediately after submission."],
    ]
    story.append(_build_table(["Tip", "Practical Advice"], tip_rows, [1.0 * cm, 15.6 * cm]))
    story.append(PageBreak())

    # ═════════════════════════════════════════════════════════════════════
    # 11. FINAL DECISION
    # ═════════════════════════════════════════════════════════════════════
    final_decision = _final_decision_label(status)
    final_reasons = _build_final_decision_reasons(result_data)
    health = _calculate_tender_health_score(result_data)
    recommendation_text = "Complete outstanding critical items before submission." if final_decision == "DO NOT SUBMIT" else "Complete final review and sign-off before submission."
    story.append(Paragraph("11. Final Decision", SECTION_STYLE))
    story.append(_hr())
    health_bar_units = max(0, min(10, round(health["score"] / 10)))
    health_bar = ("█" * health_bar_units) + ("░" * (10 - health_bar_units))
    final_block: List[Any] = [
        Paragraph("Tender Health Score", SUBSECTION_STYLE),
        Paragraph(f"{health_bar}", ParagraphStyle("TenderHealthBar", parent=BODY_BOLD, fontName="Courier", fontSize=16, leading=20, alignment=TA_CENTER, textColor=SUCCESS_GREEN if health["score"] >= 80 else WARNING_AMBER if health["score"] >= 50 else ERROR_RED)),
        Paragraph(f"{health['score']}/100 — {health['status']}", ParagraphStyle("TenderHealthScoreFinal", parent=BODY_BOLD, fontSize=18, leading=22, alignment=TA_CENTER, textColor=SUCCESS_GREEN if health["score"] >= 80 else WARNING_AMBER if health["score"] >= 50 else ERROR_RED)),
        Spacer(1, 0.15 * cm),
        _build_table(["Tender Health Breakdown", "Score"], health["breakdown"], [8.5 * cm, 4.0 * cm]),
        Spacer(1, 0.2 * cm),
        Paragraph(final_decision, ParagraphStyle("FinalDecisionStyle", parent=BODY_BOLD, fontSize=20, leading=24, alignment=TA_CENTER, textColor=ERROR_RED if final_decision == "DO NOT SUBMIT" else WARNING_AMBER if "REVIEW" in final_decision else SUCCESS_GREEN)),
        Spacer(1, 0.2 * cm),
        Paragraph("Reasons", SUBSECTION_STYLE),
    ]
    for reason in final_reasons:
        final_block.append(Paragraph(reason, CHECKLIST_STYLE))
    final_block.extend([
        Spacer(1, 0.2 * cm),
        Paragraph("Recommendation", SUBSECTION_STYLE),
        Paragraph(recommendation_text, BODY_BOLD),
    ])
    story.append(KeepTogether(final_block))
    story.append(PageBreak())

    story.append(Paragraph("12. Director Approval", SECTION_STYLE))
    story.append(_hr())
    signoff_rows = [
        ["Tender reviewed", "□ YES", "□ NO"],
        ["Approved for submission", "□ YES", "□ NO"],
        ["Authorised Signatory", "____________________", ""],
        ["Date", "____________________", ""],
    ]
    story.append(_build_table(["Director Approval", "Option 1", "Option 2"], signoff_rows, [6.5 * cm, 4.8 * cm, 4.8 * cm]))
    story.append(Spacer(1, 0.35 * cm))
    story.append(Paragraph("No information has been invented. Verify all details before submission.", ParagraphStyle("FinalNotice", parent=SMALL, alignment=TA_CENTER, fontName="Helvetica-Oblique", textColor=TEXT_LIGHT)))

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    buffer.seek(0)
    logger.info("[COMPLETION] Tender Completion Guide v%s generated for job %s", GUIDE_VERSION, job_id)
    return buffer