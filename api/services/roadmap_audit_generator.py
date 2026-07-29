"""
Bid Response Roadmap & Tender Integrity Audit Generator

This module generates:
1. Bid Response Roadmap (PDF) - Structured guide with Data Entry Schedule and manual entry placeholders
2. Tender Integrity Audit (PDF) - Automated justification report with confidence scores and risk assessment
"""
import logging
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether,
)

from .confidence_service import compute_composite_confidence

logger = logging.getLogger(__name__)

# ── Color palette ─────────────────────────────────────────────────────
PRIMARY_BLUE = colors.HexColor("#1F4E79")
SECONDARY_BLUE = colors.HexColor("#D6E4F0")
WARNING_AMBER = colors.HexColor("#FFF3CD")
ERROR_RED = colors.HexColor("#F8D7DA")
SUCCESS_GREEN = colors.HexColor("#D4EDDA")
TEXT_DARK = colors.HexColor("#333333")
TEXT_MEDIUM = colors.HexColor("#666666")
TEXT_LIGHT = colors.HexColor("#999999")
WHITE = colors.white

# ── Page dimensions ───────────────────────────────────────────────────
PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 2 * cm

# ── Styles ────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()

TITLE_STYLE = ParagraphStyle(
    "ReportTitle", parent=styles["Title"],
    fontSize=26, leading=32, textColor=PRIMARY_BLUE,
    spaceAfter=6, alignment=TA_CENTER,
)

SUBTITLE_STYLE = ParagraphStyle(
    "ReportSubtitle", parent=styles["Normal"],
    fontSize=12, leading=16, textColor=TEXT_MEDIUM,
    spaceAfter=20, alignment=TA_CENTER,
)

SECTION_STYLE = ParagraphStyle(
    "SectionHeader", parent=styles["Heading1"],
    fontSize=16, leading=22, textColor=PRIMARY_BLUE,
    spaceBefore=18, spaceAfter=10,
)

SUBSECTION_STYLE = ParagraphStyle(
    "SubSectionHeader", parent=styles["Heading2"],
    fontSize=12, leading=16, textColor=PRIMARY_BLUE,
    spaceBefore=12, spaceAfter=6,
)

BODY_STYLE = ParagraphStyle(
    "ReportBody", parent=styles["Normal"],
    fontSize=9, leading=13, textColor=TEXT_DARK,
    spaceAfter=4,
)

BODY_BOLD_STYLE = ParagraphStyle(
    "ReportBodyBold", parent=BODY_STYLE,
    fontName="Helvetica-Bold",
)

LABEL_STYLE = ParagraphStyle(
    "FieldLabel", parent=styles["Normal"],
    fontSize=8, leading=10, textColor=TEXT_MEDIUM,
    fontName="Helvetica-Bold",
)

VALUE_STYLE = ParagraphStyle(
    "FieldValue", parent=styles["Normal"],
    fontSize=10, leading=14, textColor=TEXT_DARK,
    spaceAfter=2,
)

UNAVAILABLE_STYLE = ParagraphStyle(
    "Unavailable", parent=styles["Normal"],
    fontSize=8, leading=10, textColor=colors.red,
    fontName="Helvetica-Oblique",
)

WARNING_STYLE = ParagraphStyle(
    "WarningText", parent=styles["Normal"],
    fontSize=8, leading=11, textColor=colors.HexColor("#856404"),
)

FOOTER_STYLE = ParagraphStyle(
    "Footer", parent=styles["Normal"],
    fontSize=7, leading=9, textColor=TEXT_LIGHT,
    alignment=TA_CENTER,
)


def _make_table(headers: List[str], rows: List[List[str]]) -> Table:
    """Create a styled table."""
    data = [headers] + rows
    col_count = len(headers)
    table = Table(data, colWidths=None, hAlign="LEFT")

    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]

    # Alternate row colors
    for i in range(1, len(data)):
        if i % 2 == 0:
            style_commands.append(
                ("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F8F9FA"))
            )

    table.setStyle(TableStyle(style_commands))
    return table


def _hr() -> HRFlowable:
    """Horizontal rule."""
    return HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CCCCCC"),
                      spaceBefore=6, spaceAfter=6)


def _get_page_reference(item_data: Dict[str, Any], default: str = "Original Tender") -> str:
    """
    Helper to get formatted page reference from item data.
    Returns "Original Tender, Page X" if page number exists, else default.
    """
    page_number = item_data.get("source_page_number")
    if page_number:
        return f"Original Tender, Page {page_number}"
    return default


def generate_bid_response_roadmap(job_id: str, result_data: Dict[str, Any]) -> BytesIO:
    """
    Generate Bid Response Roadmap PDF from a processing result.

    Returns BytesIO stream containing the PDF.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"Bid Response Roadmap - {job_id}",
        author="Tender Engine API",
    )
    story: List[Any] = []

    # Watermark header
    story.append(Paragraph(
        "Bid Response Roadmap — To be used in conjunction with official tender documentation",
        ParagraphStyle("Watermark", parent=BODY_STYLE, fontSize=8, textColor=TEXT_LIGHT, alignment=TA_CENTER, italic=True)
    ))
    story.append(Spacer(1, 0.5 * cm))

    # Cover section
    story.append(Paragraph("BID RESPONSE ROADMAP", TITLE_STYLE))
    story.append(Spacer(1, 1 * cm))

    filename = result_data.get("filename", "Unknown Document")
    cover_data = [
        ["Tender File Name", filename],
        ["Job ID", job_id],
        ["Processing Date", datetime.now().strftime("%Y-%m-%d %H:%M")],
    ]
    cover_table = Table(cover_data, colWidths=[5 * cm, 10 * cm])
    cover_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), PRIMARY_BLUE),
        ("TEXTCOLOR", (1, 0), (1, -1), TEXT_DARK),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#EEEEEE")),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
    ]))
    story.append(cover_table)
    story.append(PageBreak())

    # Executive Briefing
    story.append(Paragraph("EXECUTIVE BRIEFING", ParagraphStyle(
        "ExecutiveHeader", parent=styles["Title"],
        fontSize=28, leading=34, textColor=colors.HexColor("#1F4E79"),
        spaceAfter=16, alignment=TA_CENTER,
        fontName="Helvetica-Bold"
    )))

    # Why This Tool?
    story.append(Paragraph("WHY THIS TOOL?", ParagraphStyle(
        "SubHeader", parent=styles["Heading2"],
        fontSize=14, leading=20, textColor=colors.HexColor("#1F4E79"),
        spaceBefore=18, spaceAfter=8, fontName="Helvetica-Bold"
    )))
    story.append(Paragraph(
        "Government tenders are designed to disqualify you. This system identifies 'Disqualification Traps' and missing data before you spend hours preparing a bid.",
        ParagraphStyle("BodyText", parent=styles["Normal"],
            fontSize=11, leading=17, textColor=colors.HexColor("#333333"),
            spaceAfter=12
        )
    ))

    # What Is This?
    story.append(Paragraph("WHAT IS THIS?", ParagraphStyle(
        "SubHeader", parent=styles["Heading2"],
        fontSize=14, leading=20, textColor=colors.HexColor("#1F4E79"),
        spaceBefore=18, spaceAfter=8, fontName="Helvetica-Bold"
    )))
    story.append(Paragraph(
        "This is a 'Bid Response Roadmap'. It strips the fluff from the official tender and gives you a clean checklist of what to fill in and where the traps are.",
        ParagraphStyle("BodyText", parent=styles["Normal"],
            fontSize=11, leading=17, textColor=colors.HexColor("#333333"),
            spaceAfter=12
        )
    ))

    # When to Use It?
    story.append(Paragraph("WHEN TO USE IT?", ParagraphStyle(
        "SubHeader", parent=styles["Heading2"],
        fontSize=14, leading=20, textColor=colors.HexColor("#1F4E79"),
        spaceBefore=18, spaceAfter=8, fontName="Helvetica-Bold"
    )))
    story.append(Paragraph(
        "Use this the moment you download a tender. If the 'Risk Level' is 'High', this tender is likely a waste of time. If 'Medium/Low', use this as your guide to complete the official submission.",
        ParagraphStyle("BodyText", parent=styles["Normal"],
            fontSize=11, leading=17, textColor=colors.HexColor("#333333"),
            spaceAfter=12
        )
    ))

    # How to Use It?
    story.append(Paragraph("HOW TO USE IT?", ParagraphStyle(
        "SubHeader", parent=styles["Heading2"],
        fontSize=14, leading=20, textColor=colors.HexColor("#1F4E79"),
        spaceBefore=18, spaceAfter=8, fontName="Helvetica-Bold"
    )))
    story.append(Paragraph(
        "1. Review the Audit (Risk Assessment). 2. Use the Roadmap to fill in your official tender forms. 3. Refer to the 'Page References' provided to find original clauses quickly.",
        ParagraphStyle("BodyText", parent=styles["Normal"],
            fontSize=11, leading=17, textColor=colors.HexColor("#333333"),
            spaceAfter=12
        )
    ))
    story.append(PageBreak())

    # Data Entry Schedule
    story.append(Paragraph("DATA ENTRY SCHEDULE", SECTION_STYLE))
    story.append(_hr())

    # BOQ Items section
    boq_items = result_data.get("boq_items", [])
    story.append(Paragraph("Bill of Quantities Items", SUBSECTION_STYLE))

    if not boq_items:
        page_ref = _get_page_reference(result_data)
        story.append(Paragraph(
            f"[MANUAL ENTRY REQUIRED - REF: {page_ref}]",
            UNAVAILABLE_STYLE
        ))
    else:
        boq_rows = []
        for item in boq_items:
            item_num = str(item.get("item_no", "")) if item.get("item_no") else "[MANUAL ENTRY REQUIRED]"
            page_ref = _get_page_reference(item)
            desc = str(item.get("description", "")) if item.get("description") else f"[MANUAL ENTRY REQUIRED - REF: {page_ref}]"
            qty = str(item.get("quantity")) if item.get("quantity") is not None else f"[MANUAL ENTRY REQUIRED - REF: {page_ref}]"
            unit = str(item.get("unit", "")) if item.get("unit") else f"[MANUAL ENTRY REQUIRED - REF: {page_ref}]"
            rate = f"{item.get('rate'):.2f}" if item.get("rate") is not None else f"[MANUAL ENTRY REQUIRED - REF: {page_ref}]"
            amount = f"{item.get('amount'):.2f}" if item.get("amount") is not None else f"[MANUAL ENTRY REQUIRED - REF: {page_ref}]"

            boq_rows.append([
                item_num,
                desc,
                qty,
                unit,
                rate,
                amount
            ])
        boq_table = _make_table(
            ["Item #", "Description", "Quantity", "Unit", "Rate", "Amount"],
            boq_rows
        )
        story.append(boq_table)

    story.append(PageBreak())

    # Requirements section
    story.append(Paragraph("General Requirements", SUBSECTION_STYLE))
    req_data = []
    req_fields = [
        ("Sector", result_data.get("detected_sector")),
        ("Duration (Months)", result_data.get("detected_duration_months")),
        ("Location(s)", ", ".join(result_data.get("detected_locations", [])) or None),
    ]
    for label, value in req_fields:
        page_ref = _get_page_reference(result_data)
        if value:
            req_data.append([label, str(value), "Extracted"])
        else:
            req_data.append([label, f"[MANUAL ENTRY REQUIRED - REF: {page_ref}]", "Original Tender"])

    req_table = _make_table(["Requirement", "Value", "Reference"], req_data)
    story.append(req_table)

    story.append(PageBreak())

    # Compliance Checklist
    story.append(Paragraph("COMPLIANCE REQUIREMENTS CHECKLIST", SECTION_STYLE))
    story.append(_hr())
    story.append(Paragraph("Review original tender for all compliance criteria.", BODY_STYLE))
    story.append(Spacer(1, 0.5 * cm))

    # Mandatory Disqualification Criteria
    story.append(Paragraph("Mandatory Disqualification Criteria", ParagraphStyle(
        "MandatoryHeader", parent=SUBSECTION_STYLE, fontSize=14, fontName="Helvetica-Bold", textColor=colors.red
    )))
    mandatory_items = [
        ["Site Meeting Attendance", "☐ To be completed", "[MANUAL ENTRY REQUIRED - REF: Original Tender]"],
        ["Specialized Accreditation", "☐ To be completed", "[MANUAL ENTRY REQUIRED - REF: Original Tender]"],
        ["Location-Specific Packaging", "☐ To be completed", "[MANUAL ENTRY REQUIRED - REF: Original Tender]"],
    ]
    mandatory_table = _make_table(["Requirement", "Status", "Notes"], mandatory_items)
    story.append(mandatory_table)
    story.append(Spacer(1, 0.8 * cm))

    # Standard Compliance Requirements
    story.append(Paragraph("Standard Compliance Requirements", SUBSECTION_STYLE))
    standard_items = [
        ["Tax Clearance Certificate", "☐ To be completed", "[MANUAL ENTRY REQUIRED - REF: Original Tender]"],
        ["B-BBEE Certificate", "☐ To be completed", "[MANUAL ENTRY REQUIRED - REF: Original Tender]"],
        ["CIDB Registration", "☐ To be completed", "[MANUAL ENTRY REQUIRED - REF: Original Tender]"],
        ["Company Registration Documents", "☐ To be completed", "[MANUAL ENTRY REQUIRED - REF: Original Tender]"],
        ["Workman's Compensation", "☐ To be completed", "[MANUAL ENTRY REQUIRED - REF: Original Tender]"],
        ["Other compliance requirements (check original tender)", "☐ To be completed", "[MANUAL ENTRY REQUIRED - REF: Original Tender]"],
    ]
    standard_table = _make_table(["Requirement", "Status", "Notes"], standard_items)
    story.append(standard_table)

    doc.build(story)
    buffer.seek(0)
    logger.info(f"[EXPORT] Bid Response Roadmap generated for job {job_id}")
    return buffer


def generate_tender_integrity_audit(job_id: str, result_data: Dict[str, Any]) -> BytesIO:
    """
    Generate Tender Integrity Audit PDF from a processing result.

    Returns BytesIO stream containing the PDF.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"Tender Integrity Audit - {job_id}",
        author="Tender Engine API",
    )
    story: List[Any] = []

    # Title
    story.append(Paragraph("TENDER INTEGRITY AUDIT", TITLE_STYLE))
    story.append(Spacer(1, 1 * cm))

    filename = result_data.get("filename", "Unknown Document")
    cover_data = [
        ["Tender File Name", filename],
        ["Job ID", job_id],
        ["Audit Date", datetime.now().strftime("%Y-%m-%d %H:%M")],
    ]
    cover_table = Table(cover_data, colWidths=[5 * cm, 10 * cm])
    cover_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), PRIMARY_BLUE),
        ("TEXTCOLOR", (1, 0), (1, -1), TEXT_DARK),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#EEEEEE")),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
    ]))
    story.append(cover_table)
    story.append(PageBreak())

    # Confidence Score Breakdown
    story.append(Paragraph("CONFIDENCE SCORE BREAKDOWN", SECTION_STYLE))
    story.append(_hr())

    confidence_result = compute_composite_confidence(result_data)
    score = confidence_result.get("confidence_score", 0)
    label = confidence_result.get("confidence_label", "low")

    score_para = Paragraph(f"Overall Confidence Score: {score:.1%} ({label.title()})", ParagraphStyle(
        "ConfidenceScore", parent=BODY_BOLD_STYLE, textColor=PRIMARY_BLUE, fontSize=11
    ))
    story.append(score_para)
    story.append(Spacer(1, 0.5 * cm))

    breakdown = confidence_result.get("breakdown", {})
    breakdown_rows = [
        ["Text Extraction Quality", f"{breakdown.get('extraction', 0):.1%}"],
        ["BOQ Completeness", f"{breakdown.get('boq', 0):.1%}"],
        ["Pricing Quality", f"{breakdown.get('pricing', 0):.1%}"],
        ["OCR Penalty", f"{breakdown.get('ocr_penalty', 0):.1%}"],
        ["Missing Fields Penalty", f"{breakdown.get('missing_penalty', 0):.1%}"],
    ]
    breakdown_table = _make_table(["Factor", "Score"], breakdown_rows)
    story.append(breakdown_table)
    story.append(PageBreak())

    # Issues Identified
    story.append(Paragraph("ISSUES IDENTIFIED", SECTION_STYLE))
    story.append(_hr())

    issues = []
    warnings = result_data.get("warnings", [])
    ocr_used = any("ocr" in w.lower() for w in warnings)
    if ocr_used:
        issues.append({
            "issue": "OCR Fallback Used",
            "severity": "Medium",
            "confidence": "Medium",
            "explanation": "OCR was used for text extraction. Quality may be reduced. Manual review recommended.",
            "original_ref": "Original Tender"
        })

    if not result_data.get("detected_sector"):
        issues.append({
            "issue": "Missing Field: Sector",
            "severity": "High",
            "confidence": "Low",
            "explanation": "System failed to parse structure; manual review is critical.",
            "original_ref": "Original Tender"
        })

    if result_data.get("detected_duration_months") is None:
        issues.append({
            "issue": "Missing Field: Duration",
            "severity": "High",
            "confidence": "Low",
            "explanation": "System failed to parse structure; manual review is critical.",
            "original_ref": "Original Tender"
        })

    boq_confidence = result_data.get("boq_confidence")
    if boq_confidence in ("Low", None):
        issues.append({
            "issue": "Pricing Grid Malformed",
            "severity": "High",
            "confidence": "Low",
            "explanation": "BOQ extracted with low confidence. Manual verification required.",
            "original_ref": "Original Tender"
        })

    if not issues:
        issues.append({
            "issue": "No Major Issues Identified",
            "severity": "Low",
            "confidence": "High",
            "explanation": "All extraction completed successfully with high confidence.",
            "original_ref": "N/A"
        })

    issue_rows = []
    for issue in issues:
        issue_rows.append([
            issue["issue"],
            issue["severity"],
            issue["confidence"],
            f"{issue['explanation']} - REF: {issue['original_ref']}"
        ])
    issue_table = _make_table(["Issue", "Severity", "Confidence", "Explanation & Reference"], issue_rows)
    story.append(issue_table)
    story.append(PageBreak())

    # Risk Assessment
    story.append(Paragraph("RISK ASSESSMENT", SECTION_STYLE))
    story.append(_hr())

    if label == "high":
        risk_level = "Low"
        risk_summary = "Low risk - Extraction completed with high confidence."
    elif label == "medium":
        risk_level = "Medium"
        risk_summary = "Medium risk - Some fields may require manual verification."
    else:
        risk_level = "High"
        risk_summary = "High risk - Significant manual intervention required. Multiple fields missing or low confidence extraction."

    risk_para = Paragraph("Overall Risk Level: ", BODY_BOLD_STYLE)
    risk_color = SUCCESS_GREEN if risk_level == "Low" else (WARNING_AMBER if risk_level == "Medium" else ERROR_RED)
    risk_text = Paragraph(risk_level, ParagraphStyle("RiskText", parent=BODY_BOLD_STYLE, textColor=colors.black if risk_level == "Low" else (colors.HexColor("#856404") if risk_level == "Medium" else colors.HexColor("#721C24"))))
    story.append(KeepTogether([risk_para, risk_text]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(risk_summary, BODY_STYLE))

    doc.build(story)
    buffer.seek(0)
    logger.info(f"[EXPORT] Tender Integrity Audit generated for job {job_id}")
    return buffer


# ═══════════════════════════════════════════════════════════════════════
# Backward-Compatible Aliases
# ═══════════════════════════════════════════════════════════════════════

def generate_roadmap_pdf(job_id: str, result_data: Dict[str, Any]) -> BytesIO:
    """
    Alias for generate_bid_response_roadmap().
    
    Maintains backward compatibility with submission_package_service.py
    and other modules that import this function name.
    """
    return generate_bid_response_roadmap(job_id, result_data)


def generate_audit_pdf(job_id: str, result_data: Dict[str, Any]) -> BytesIO:
    """
    Alias for generate_tender_integrity_audit().
    
    Maintains backward compatibility with submission_package_service.py
    and other modules that import this function name.
    """
    return generate_tender_integrity_audit(job_id, result_data)
