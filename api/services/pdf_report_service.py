"""
PDF Report Service — Generates professional client-ready PDF reports.

Uses reportlab.platypus for document layout.

Sections:
  1. Cover Page — Tender filename, job ID, sector, location, date, pipeline version
  2. Executive Summary — Total contract value, duration, workforce, confidence, status
  3. Key Insights — BOQ count, work categories, extraction confidence, OCR, missing data
  4. Pricing Summary — Labour, materials, transport, overheads, VAT, total, method, confidence
  5. Workforce Summary — Skilled/unskilled/supervisors, categories, confidence
  6. Risks & Warnings — Pipeline warnings, failed stages, missing fields, OCR usage, retry

HONESTY RULES:
  - NO fabricated data
  - Confidence levels preserved
  - partial_success visible
  - Failed stages visible
  - Missing data honestly marked
"""
import logging
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether,
)

from .summary_builder import build_clean_summary
from .confidence_service import compute_composite_confidence

logger = logging.getLogger(__name__)

# ── Color palette ───────────────────────────────────────────────────
PRIMARY_BLUE = colors.HexColor("#1F4E79")
SECONDARY_BLUE = colors.HexColor("#D6E4F0")
WARNING_AMBER = colors.HexColor("#FFF3CD")
ERROR_RED = colors.HexColor("#F8D7DA")
SUCCESS_GREEN = colors.HexColor("#D4EDDA")
TEXT_DARK = colors.HexColor("#333333")
TEXT_MEDIUM = colors.HexColor("#666666")
TEXT_LIGHT = colors.HexColor("#999999")
WHITE = colors.white

# ── Page dimensions ─────────────────────────────────────────────────
PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 2 * cm

# ── Styles ──────────────────────────────────────────────────────────
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
    fontSize=8, leading=10, textColor=TEXT_LIGHT,
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

# ── Helpers ─────────────────────────────────────────────────────────


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


def _value_or_unavailable(value: Any, label: str = "") -> str:
    """Return value or 'Unavailable' indicator."""
    if value is None or value == "" or value == "N/A":
        if label:
            return f"[Unavailable — {label}]"
        return "[Unavailable]"
    return str(value)


def _format_currency(value: Any) -> str:
    """Format a value as currency."""
    if value is None:
        return "—"
    try:
        return f"R {float(value):,.2f}"
    except (ValueError, TypeError):
        return str(value)


# ── Main PDF generation function ────────────────────────────────────


def generate_pdf_report(job_id: str, result_data: Dict[str, Any]) -> BytesIO:
    """
    Generate a professional PDF report from a processing result.

    Args:
        job_id: The job ID for the report
        result_data: The full ProcessingResult as a dict

    Returns:
        BytesIO stream containing the PDF
    """
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"Tender Report - {job_id}",
        author="Tender Engine API",
    )

    # Build clean summary for consistent presentation
    summary = build_clean_summary(result_data)
    exec_summary = summary["executive_summary"]

    story: List[Any] = []

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 1: COVER PAGE
    # ═══════════════════════════════════════════════════════════════════

    # Spacer for top margin
    story.append(Spacer(1, 3 * cm))

    # Title
    story.append(Paragraph("TENDER PROCESSING REPORT", TITLE_STYLE))
    story.append(Spacer(1, 0.5 * cm))

    # Filename
    filename = result_data.get("filename", "Unknown Document")
    story.append(Paragraph(f"<b>{filename}</b>", SUBTITLE_STYLE))
    story.append(Spacer(1, 1 * cm))

    # Key metadata on cover
    cover_data = [
        ["Job ID", job_id[:12] + "..." if len(job_id) > 12 else job_id],
        ["Sector", _value_or_unavailable(result_data.get("detected_sector"))],
        ["Location", ", ".join(result_data.get("detected_locations", []) or []) or "Not detected"],
        ["Processing Date", datetime.now().strftime("%Y-%m-%d %H:%M")],
        ["Pipeline Version", _value_or_unavailable(result_data.get("pipeline_version"))],
        ["Status", result_data.get("status", "unknown").replace("_", " ").title()],
    ]
    cover_table = Table(cover_data, colWidths=[4 * cm, 10 * cm])
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

    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph(
        "CONFIDENTIAL — This report is generated automatically from "
        "processed tender data. All confidence levels and warnings are "
        "preserved transparently.",
        ParagraphStyle("Disclaimer", parent=BODY_STYLE,
                       fontSize=7, textColor=TEXT_LIGHT, fontName="Helvetica-Oblique")
    ))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 2: EXECUTIVE SUMMARY (MOST IMPORTANT)
    # ═══════════════════════════════════════════════════════════════════

    story.append(Paragraph("1. Executive Summary", SECTION_STYLE))
    story.append(_hr())

    status_display = result_data.get("status", "unknown").replace("_", " ").title()
    story.append(Paragraph(f"<b>Processing Status:</b> {status_display}", BODY_STYLE))

    # Build executive summary table
    exec_rows = [
        ["Total Contract Value", _format_currency(exec_summary.get("total_contract_value"))],
        ["Duration", _value_or_unavailable(
            f"{exec_summary.get('duration_months')} months"
            if exec_summary.get("duration_months") else None
        )],
        ["Workforce Total", str(exec_summary.get("workforce_total") or "Not available")],
        ["Pricing Confidence", exec_summary.get("pricing_confidence", "N/A").title()],
        ["Sector", _value_or_unavailable(exec_summary.get("sector"))],
        ["BOQ Items", str(exec_summary.get("boq_item_count", 0))],
    ]

    exec_table = Table(exec_rows, colWidths=[5 * cm, 9 * cm])
    exec_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), PRIMARY_BLUE),
        ("TEXTCOLOR", (1, 0), (1, -1), TEXT_DARK),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#EEEEEE")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8F9FA")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(exec_table)

    # Composite confidence score bar
    confidence = summary.get("confidence", {})
    score = confidence.get("confidence_score", 0)
    label = confidence.get("confidence_label", "low")

    # Create visual confidence indicator
    score_color = SUCCESS_GREEN if label == "high" else (
        WARNING_AMBER if label == "medium" else ERROR_RED
    )
    story.append(Spacer(1, 0.3 * cm))
    conf_text = f"Overall Confidence Score: {score:.0%} ({label.title()})"
    story.append(Paragraph(conf_text, ParagraphStyle(
        "ConfidenceScore", parent=BODY_BOLD_STYLE,
        textColor=PRIMARY_BLUE, fontSize=11,
    )))

    story.append(Spacer(1, 0.3 * cm))

    # Status indicators
    if result_data.get("status") == "partial_success":
        story.append(Paragraph(
            "<b>⚠ Partial Success:</b> Some processing stages completed, "
            "but others failed. See Risks & Warnings section.",
            ParagraphStyle("PartialWarning", parent=BODY_STYLE,
                           textColor=colors.HexColor("#856404"),
                           backColor=WARNING_AMBER, borderPadding=6,
                           borderColor=colors.HexColor("#FFE69C"), borderWidth=1),
        ))
    elif result_data.get("status") == "failed":
        story.append(Paragraph(
            "<b>✗ Processing Failed:</b> The pipeline was unable to complete "
            "processing. Limited or no data is available.",
            ParagraphStyle("FailWarning", parent=BODY_STYLE,
                           textColor=colors.HexColor("#721C24"),
                           backColor=ERROR_RED, borderPadding=6,
                           borderColor=colors.HexColor("#F5C6CB"), borderWidth=1),
        ))

    story.append(Spacer(1, 0.5 * cm))

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 3: KEY INSIGHTS
    # ═══════════════════════════════════════════════════════════════════

    story.append(Paragraph("2. Key Insights", SECTION_STYLE))
    story.append(_hr())

    boq = summary["boq"]
    risks = summary["risks"]
    ocr_used = risks.get("ocr_used", False)

    insights = [
        f"<b>BOQ Items:</b> {boq.get('item_count', 0)} items extracted "
        f"({boq.get('items_with_rates', 0)} with rates, "
        f"{boq.get('items_with_amounts', 0)} with amounts)",
        f"<b>BOQ Confidence:</b> {_value_or_unavailable(boq.get('confidence'))}",
        f"<b>Extraction Method:</b> {result_data.get('extraction_method', 'Standard')}",
        f"<b>OCR Used:</b> {'Yes' if ocr_used else 'No'}",
        f"<b>Text Length:</b> {result_data.get('text_length', 0):,} characters",
    ]

    for insight in insights:
        story.append(Paragraph(insight, BODY_STYLE))
    story.append(Spacer(1, 0.2 * cm))

    # Work categories
    workforce = summary["workforce"]
    categories = workforce.get("categories", [])
    if categories:
        story.append(Paragraph("<b>Work Categories Detected:</b>", BODY_STYLE))
        story.append(Paragraph(", ".join(categories), BODY_STYLE))
        story.append(Spacer(1, 0.2 * cm))

    # Missing data flags
    missing_flags = []
    if not result_data.get("detected_sector"):
        missing_flags.append("Sector not detected")
    if not result_data.get("detected_duration_months"):
        missing_flags.append("Duration not detected")
    if not result_data.get("detected_locations"):
        missing_flags.append("No locations found")
    if not workforce.get("total_workers"):
        missing_flags.append("Workforce data unavailable")
    if result_data.get("pricing_status") == "failed":
        missing_flags.append("Pricing unavailable")

    if missing_flags:
        story.append(Paragraph("<b>Data Gaps:</b>", BODY_STYLE))
        for flag in missing_flags:
            story.append(Paragraph(f"  • {flag}", UNAVAILABLE_STYLE))
        story.append(Spacer(1, 0.3 * cm))

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 4: PRICING SUMMARY
    # ═══════════════════════════════════════════════════════════════════

    story.append(Paragraph("3. Pricing Summary", SECTION_STYLE))
    story.append(_hr())

    pricing = summary["pricing"]
    pricing_result = pricing.get("result", {})

    if not pricing_result or pricing.get("status") == "failed":
        story.append(Paragraph(
            "<b>Pricing Unavailable</b>",
            ParagraphStyle("PriceUnavail", parent=BODY_STYLE,
                           textColor=colors.HexColor("#721C24"),
                           backColor=ERROR_RED, borderPadding=6),
        ))
        reason = pricing.get("unavailable_reason") or "Pricing could not be calculated."
        story.append(Paragraph(reason, BODY_STYLE))
    else:
        # Pricing breakdown table
        pricing_fields = [
            ("Labour Cost", _format_currency(pricing_result.get("labour_cost"))),
            ("Materials Cost", _format_currency(pricing_result.get("materials_cost"))),
            ("Transport Cost", _format_currency(pricing_result.get("transport_cost"))),
            ("Overheads", _format_currency(pricing_result.get("overheads"))),
            ("Subtotal", _format_currency(pricing_result.get("subtotal"))),
            ("VAT", _format_currency(pricing_result.get("vat"))),
            ("Total Monthly", _format_currency(pricing_result.get("total_monthly"))),
            ("Total Annual", _format_currency(pricing_result.get("total_annual"))),
            ("Final Contract Value", _format_currency(pricing_result.get("final_contract_value"))),
        ]

        pricing_table = _make_table(
            ["Component", "Amount (ZAR)"],
            pricing_fields
        )
        story.append(pricing_table)

        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph(f"<b>Calculation Method:</b> {pricing.get('method', 'N/A')}", BODY_STYLE))
        story.append(Paragraph(f"<b>Pricing Confidence:</b> {pricing.get('confidence', 'N/A')}", BODY_STYLE))

        # Assumptions
        if pricing_result.get("price_reliability") == "boq_based":
            story.append(Paragraph(
                "<b>Assumption:</b> Pricing is based on extracted Bill of Quantities items.",
                BODY_STYLE
            ))
        elif pricing_result.get("price_reliability") == "estimated":
            story.append(Paragraph(
                "<b>Assumption:</b> Pricing is estimated using default rates "
                "as no BOQ data was available.",
                ParagraphStyle("EstNote", parent=BODY_STYLE,
                               textColor=colors.HexColor("#856404"))
            ))

        story.append(Spacer(1, 0.3 * cm))

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 5: WORKFORCE SUMMARY
    # ═══════════════════════════════════════════════════════════════════

    story.append(Paragraph("4. Workforce Summary", SECTION_STYLE))
    story.append(_hr())

    workforce_data = result_data.get("detected_workforce", {})

    if not workforce_data:
        story.append(Paragraph(
            "Workforce data is not available.",
            UNAVAILABLE_STYLE
        ))
    else:
        wf_fields = [
            ("Skilled Workers", str(workforce_data.get("skilled_workers", "—"))),
            ("Unskilled Workers", str(workforce_data.get("unskilled_workers", "—"))),
            ("Supervisors", str(workforce_data.get("supervisors", "—"))),
            ("Total Workers", str(workforce_data.get("total_workers", "—"))),
            ("Shifts Per Day", str(workforce_data.get("shifts_per_day", "—"))),
            ("Hours Per Day", str(workforce_data.get("hours_per_day", "—"))),
            ("Days Per Week", str(workforce_data.get("days_per_week", "—"))),
        ]

        wf_table = _make_table(
            ["Category", "Value"],
            wf_fields
        )
        story.append(wf_table)

        # Confidence
        wf_conf = workforce_data.get("workforce_inference_confidence") or \
                  result_data.get("boq_confidence", "N/A")
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph(f"<b>Confidence:</b> {wf_conf}", BODY_STYLE))

        # Reasoning
        if workforce_data.get("workforce_reasoning"):
            story.append(Paragraph(
                f"<b>Note:</b> {workforce_data['workforce_reasoning']}",
                ParagraphStyle("WfNote", parent=BODY_STYLE, fontSize=8,
                               textColor=TEXT_MEDIUM, fontName="Helvetica-Oblique")
            ))

        # Work categories
        if workforce_data.get("work_categories"):
            story.append(Spacer(1, 0.2 * cm))
            cats = ", ".join(workforce_data["work_categories"])
            story.append(Paragraph(f"<b>Categories:</b> {cats}", BODY_STYLE))

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 6: RISKS & WARNINGS
    # ═══════════════════════════════════════════════════════════════════

    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("5. Risks & Warnings", SECTION_STYLE))
    story.append(_hr())

    # Failed stages
    failed_stages = result_data.get("failed_stages", [])
    if failed_stages:
        story.append(Paragraph("<b>Failed Stages:</b>", BODY_BOLD_STYLE))
        for stage in failed_stages:
            story.append(Paragraph(
                f"  • {stage.replace('_', ' ').title()}",
                ParagraphStyle("FailedItem", parent=BODY_STYLE,
                               textColor=colors.HexColor("#721C24"))
            ))
        story.append(Spacer(1, 0.2 * cm))

    # Warnings
    warnings_list = result_data.get("warnings", [])
    if warnings_list:
        story.append(Paragraph("<b>Processing Warnings:</b>", BODY_BOLD_STYLE))
        for warning in warnings_list[:10]:  # Show first 10
            story.append(Paragraph(f"  • {warning}", WARNING_STYLE))
        if len(warnings_list) > 10:
            story.append(Paragraph(
                f"  ... and {len(warnings_list) - 10} more warnings",
                UNAVAILABLE_STYLE
            ))
        story.append(Spacer(1, 0.2 * cm))

    # Missing BOQ fields
    boq_items = result_data.get("boq_items", [])
    if boq_items:
        missing_rates = sum(1 for i in boq_items if i.get("rate") is None)
        missing_amounts = sum(1 for i in boq_items if i.get("amount") is None)
        if missing_rates > 0 or missing_amounts > 0:
            story.append(Paragraph("<b>Missing BOQ Fields:</b>", BODY_BOLD_STYLE))
            if missing_rates > 0:
                story.append(Paragraph(
                    f"  • {missing_rates} items missing rate data",
                    WARNING_STYLE
                ))
            if missing_amounts > 0:
                story.append(Paragraph(
                    f"  • {missing_amounts} items missing amount data",
                    WARNING_STYLE
                ))
            story.append(Spacer(1, 0.2 * cm))

    # OCR usage
    if ocr_used:
        story.append(Paragraph(
            "<b>OCR Fallback Used:</b> Text was extracted using Optical Character "
            "Recognition. Quality may be reduced for scanned documents.",
            ParagraphStyle("OCRNote", parent=BODY_STYLE,
                           textColor=colors.HexColor("#856404"))
        ))
        story.append(Spacer(1, 0.2 * cm))

    # Retry metadata
    retry = summary.get("retry", {})
    if retry.get("retry_count", 0) > 0:
        story.append(Paragraph("<b>Retry Information:</b>", BODY_BOLD_STYLE))
        story.append(Paragraph(
            f"  • Retry count: {retry.get('retry_count', 0)}",
            BODY_STYLE
        ))
        retried = retry.get("retried_stages", [])
        if retried:
            story.append(Paragraph(
                f"  • Retried stages: {', '.join(retried)}",
                BODY_STYLE
            ))
        story.append(Spacer(1, 0.2 * cm))

    # No issues
    if not failed_stages and not warnings_list and not ocr_used:
        story.append(Paragraph(
            "No significant risks or warnings detected.",
            ParagraphStyle("CleanNote", parent=BODY_STYLE,
                           textColor=colors.HexColor("#155724"),
                           backColor=SUCCESS_GREEN, borderPadding=6)
        ))

    # ── Footer page break before end ─────────────────────────────────
    story.append(Spacer(1, 1 * cm))

    # ═══════════════════════════════════════════════════════════════════
    # FOOTER
    # ═══════════════════════════════════════════════════════════════════
    story.append(_hr())
    story.append(Paragraph(
        f"Generated by Tender Engine API | Job ID: {job_id[:16]}... | "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        FOOTER_STYLE
    ))
    story.append(Paragraph(
        "This report is automatically generated. All confidence levels, "
        "warnings, and data gaps are honestly presented.",
        FOOTER_STYLE
    ))

    # ── Build PDF ───────────────────────────────────────────────────
    try:
        doc.build(story)
        buffer.seek(0)
        logger.info("[EXPORT] PDF report generated for job %s — %d pages", job_id, len(story))
        return buffer
    except Exception as e:
        logger.exception("[EXPORT] Failed to build PDF for job %s", job_id)
        raise