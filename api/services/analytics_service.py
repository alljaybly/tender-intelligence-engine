"""
Platform Intelligence Engine — deterministic operational analytics.

All analytics are derived from observable processing outputs, persisted
pipeline events, and stored results. No fabricated statistics, no guesses.
"""
from __future__ import annotations

import csv
import io
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

from .database import DB_PATH, get_db, close_db
from .tender_readiness_service import build_readiness_report


ANALYTICS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS platform_analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    processing_duration_ms INTEGER,
    upload_size_bytes INTEGER,
    page_count INTEGER,
    ocr_used INTEGER,
    ocr_page_count INTEGER,
    document_language TEXT,
    detected_jurisdiction TEXT,
    tender_type TEXT,
    procurement_method TEXT,
    detected_currency TEXT,
    currencies_detected_json TEXT,
    employer_detected INTEGER,
    tender_number_detected INTEGER,
    closing_date_detected INTEGER,
    boq_detected INTEGER,
    boq_item_count INTEGER,
    work_categories_detected_json TEXT,
    pricing_executed INTEGER,
    readiness_score REAL,
    submission_package_generated INTEGER,
    completion_guide_generated INTEGER,
    processing_status TEXT,
    warnings_count INTEGER,
    errors_count INTEGER,
    upload_time_ms INTEGER,
    validation_time_ms INTEGER,
    ocr_duration_ms INTEGER,
    text_extraction_duration_ms INTEGER,
    entity_extraction_duration_ms INTEGER,
    boq_duration_ms INTEGER,
    pricing_duration_ms INTEGER,
    report_generation_duration_ms INTEGER,
    zip_package_generation_duration_ms INTEGER,
    total_processing_time_ms INTEGER,
    average_page_processing_time_ms REAL,
    is_scanned INTEGER,
    is_digital INTEGER,
    contains_boq INTEGER,
    contains_drawings INTEGER,
    contains_tables INTEGER,
    contains_appendices INTEGER,
    contains_pricing_schedules INTEGER,
    contains_forms INTEGER,
    contains_signatures INTEGER,
    contains_evaluation_criteria INTEGER,
    contains_mandatory_documentation INTEGER,
    extraction_quality_json TEXT,
    document_characteristics_json TEXT,
    raw_metrics_json TEXT,
    FOREIGN KEY (job_id) REFERENCES tenders(job_id)
);
CREATE INDEX IF NOT EXISTS idx_platform_analytics_job_id ON platform_analytics(job_id);
CREATE INDEX IF NOT EXISTS idx_platform_analytics_completed_at ON platform_analytics(completed_at);
CREATE INDEX IF NOT EXISTS idx_platform_analytics_status ON platform_analytics(processing_status);
"""

TRACKED_FIELDS = {
    "employer": "Employer",
    "tender_number": "Tender Number",
    "project_title": "Project Title",
    "closing_date": "Closing Date",
    "currency": "Currency",
    "location": "Location",
    "contract_duration": "Contract Duration",
    "procurement_method": "Procurement Method",
    "estimated_contract_value": "Estimated Value",
    "mandatory_documents": "Mandatory Documents",
    "evaluation_criteria": "Evaluation Criteria",
    "past_performance": "Past Performance",
    "insurance": "Insurance",
    "guarantees": "Guarantees",
    "payment_terms": "Payment Terms",
    "boq_summary": "BOQ",
    "trade_summary": "Trade Categories",
}


def init_analytics_schema_sync() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.executescript(ANALYTICS_TABLE_DDL)
        conn.commit()
    finally:
        conn.close()


def _safe_json_load(value: Any) -> Any:
    if value in (None, "", b""):
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return None


def _normalize_confidence(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        if value >= 0.8:
            return "High"
        if value >= 0.5:
            return "Medium"
        if value > 0:
            return "Low"
        return None
    text = str(value).strip().title()
    if text in {"High", "Medium", "Low", "Missing", "Not Found"}:
        return text
    return text or None


def _contains_keywords(text: str, keywords: Iterable[str]) -> bool:
    lowered = (text or "").lower()
    return any(keyword.lower() in lowered for keyword in keywords)


async def _fetch_processing_events(job_id: str) -> List[Dict[str, Any]]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT stage, status, details, duration_ms, created_at FROM processing_events WHERE tender_id = ? ORDER BY created_at ASC, id ASC",
            (job_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await close_db(db)


async def _fetch_tender_result_row(job_id: str) -> Optional[Dict[str, Any]]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM tender_results WHERE tender_id = ? ORDER BY id DESC LIMIT 1",
            (job_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await close_db(db)


def _event_duration(events: List[Dict[str, Any]], stage: str) -> Optional[int]:
    for event in reversed(events):
        if event.get("stage") == stage and event.get("duration_ms") is not None:
            return int(event["duration_ms"])
    return None


def _count_event_occurrences(events: List[Dict[str, Any]], stage: str, status: Optional[str] = None) -> int:
    count = 0
    for event in events:
        if event.get("stage") != stage:
            continue
        if status is not None and event.get("status") != status:
            continue
        count += 1
    return count


def _build_field_quality(result_data: Dict[str, Any]) -> Dict[str, Any]:
    evidence_fields = ((result_data.get("evidence") or {}).get("fields", {}) or {})
    full_text = result_data.get("full_text") or ""
    output: Dict[str, Any] = {}

    source_map = {
        "contract_duration": "closing_date",
        "procurement_method": "procurement_method",
        "boq_summary": "boq_summary",
        "trade_summary": "trade_summary",
    }

    heuristic_patterns = {
        "evaluation_criteria": ["evaluation criteria", "technical evaluation", "functionality criteria"],
        "past_performance": ["reference letters", "past performance", "experience and knowledge"],
        "insurance": ["insurance", "insurer", "professional indemnity", "public liability"],
        "guarantees": ["guarantee", "bond", "bid guarantee", "tender guarantee"],
        "payment_terms": ["payment terms", "payment clause", "invoicing instructions", "invoice"],
    }

    for field_key, label in TRACKED_FIELDS.items():
        evidence_key = source_map.get(field_key, field_key)
        evidence = evidence_fields.get(evidence_key, {}) or {}
        value = evidence.get("value")
        extracted = value not in (None, "", [], {})
        confidence = _normalize_confidence(evidence.get("confidence"))
        evidence_count = 1 if extracted else 0
        evidence_source = evidence.get("source_category") or evidence.get("section")

        if field_key in heuristic_patterns:
            extracted = _contains_keywords(full_text, heuristic_patterns[field_key])
            evidence_count = 1 if extracted else 0
            confidence = "Medium" if extracted else None
            evidence_source = "body_text" if extracted else None

        if field_key == "contract_duration":
            extracted = result_data.get("detected_duration_months") is not None
            evidence_count = 1 if extracted else 0
            if extracted and not confidence:
                confidence = "High"
            evidence_source = evidence_source or "body_text"

        if field_key == "procurement_method":
            procurement = (result_data.get("procurement_context") or {}).get("procurement_method", {})
            extracted = bool(procurement.get("value"))
            evidence_count = 1 if extracted else 0
            confidence = _normalize_confidence(procurement.get("confidence") or procurement.get("state")) or confidence
            evidence_source = evidence_source or procurement.get("source")

        output[field_key] = {
            "field_name": label,
            "was_attempted": True,
            "was_successfully_extracted": extracted,
            "confidence": confidence,
            "evidence_count": evidence_count,
            "evidence_source": evidence_source,
        }
    return output


def _build_document_characteristics(result_data: Dict[str, Any], events: List[Dict[str, Any]]) -> Dict[str, Any]:
    full_text = result_data.get("full_text") or ""
    document_sections = result_data.get("document_sections") or []
    boq_items = result_data.get("boq_items") or []
    used_ocr = _count_event_occurrences(events, "ocr_completed", "success") > 0 and _contains_keywords(
        " ".join(str(event.get("details") or "") for event in events if event.get("stage") == "ocr_completed"),
        ["OCR fallback used", "OCR"],
    )

    return {
        "page_count": (result_data.get("metadata") or {}).get("page_count"),
        "is_scanned": used_ocr,
        "is_digital": False if used_ocr else True,
        "contains_boq": bool(boq_items),
        "contains_drawings": _contains_keywords(full_text, ["drawings", "plans", "layout"]) or any((section.get("section_type") == "drawings") for section in document_sections),
        "contains_tables": bool(boq_items) or _contains_keywords(full_text, ["table", "schedule", "pricing schedule"]),
        "contains_appendices": any((section.get("section_type") == "appendices") for section in document_sections),
        "contains_pricing_schedules": _contains_keywords(full_text, ["pricing schedule", "price schedule"]) or any((section.get("section_type") == "pricing") for section in document_sections),
        "contains_forms": _contains_keywords(full_text, ["sbd", "form", "returnable documents"]) or any((section.get("section_type") == "forms") for section in document_sections),
        "contains_signatures": _contains_keywords(full_text, ["signature", "signed at", "sign here"]),
        "contains_evaluation_criteria": _contains_keywords(full_text, ["evaluation criteria", "functionality criteria", "technical evaluation"]) or any((section.get("section_type") == "evaluation_criteria") for section in document_sections),
        "contains_mandatory_documentation": _contains_keywords(full_text, ["mandatory documents", "returnable documents", "required documents"]),
    }


def _json_bool(value: bool) -> int:
    return 1 if value else 0


async def build_platform_analytics_record(job_id: str, result_data: Dict[str, Any]) -> Dict[str, Any]:
    events = await _fetch_processing_events(job_id)
    tender_result_row = await _fetch_tender_result_row(job_id)
    metadata = result_data.get("metadata") or {}
    evidence_fields = ((result_data.get("evidence") or {}).get("fields", {}) or {})
    procurement_context = result_data.get("procurement_context") or {}
    procurement_entities = result_data.get("procurement_entities") or {}
    detected_currency = result_data.get("detected_currency") or {}
    trade_summary = result_data.get("trade_summary") or {}
    warnings = result_data.get("warnings") or []

    readiness_report = build_readiness_report(result_data)
    readiness_score = ((readiness_report.get("readiness_score") or {}).get("overall_score"))

    upload_time_ms = _event_duration(events, "upload_received")
    validation_time_ms = _event_duration(events, "metadata_extraction")
    text_extraction_duration_ms = _event_duration(events, "text_extraction")
    entity_extraction_duration_ms = _event_duration(events, "entity_extraction")
    boq_duration_ms = _event_duration(events, "boq_analysis")
    pricing_duration_ms = _event_duration(events, "pricing_calculation")
    total_processing_time_ms = sum(v for v in [validation_time_ms, text_extraction_duration_ms, entity_extraction_duration_ms, boq_duration_ms, pricing_duration_ms] if isinstance(v, int)) or None

    ocr_used = any("ocr" in str(event.get("details") or "").lower() for event in events if event.get("stage") == "text_extraction")
    ocr_duration_ms = _event_duration(events, "ocr_completed") if ocr_used else None
    page_count = metadata.get("page_count")
    avg_page_processing = round(total_processing_time_ms / page_count, 2) if total_processing_time_ms and page_count else None

    quality = _build_field_quality(result_data)
    doc_characteristics = _build_document_characteristics(result_data, events)

    report_generation_duration_ms = None
    zip_package_generation_duration_ms = None
    submission_package_generated = 0
    completion_guide_generated = 0
    for warning in warnings:
        warning_text = str(warning).lower()
        if "completion guide" in warning_text:
            completion_guide_generated = 1
        if "submission package" in warning_text:
            submission_package_generated = 1

    processing_status = result_data.get("status")
    warnings_count = len(warnings)
    errors_count = len(result_data.get("failed_stages") or [])

    currencies_detected = []
    if detected_currency.get("currency_code"):
        currencies_detected.append(detected_currency.get("currency_code"))

    record = {
        "job_id": job_id,
        "completed_at": datetime.now(timezone.utc).replace(tzinfo=None),
        "processing_duration_ms": total_processing_time_ms,
        "upload_size_bytes": metadata.get("size_bytes"),
        "page_count": page_count,
        "ocr_used": _json_bool(bool(ocr_used)),
        "ocr_page_count": page_count if ocr_used and page_count is not None else None,
        "document_language": (procurement_context.get("language") or {}).get("value"),
        "detected_jurisdiction": (procurement_context.get("jurisdiction") or {}).get("value"),
        "tender_type": (procurement_context.get("tender_type") or {}).get("value"),
        "procurement_method": (procurement_context.get("procurement_method") or {}).get("value"),
        "detected_currency": detected_currency.get("currency_code"),
        "currencies_detected_json": json.dumps(currencies_detected),
        "employer_detected": _json_bool(bool((evidence_fields.get("employer") or {}).get("value") or (procurement_entities.get("employer") or {}).get("value"))),
        "tender_number_detected": _json_bool(bool((evidence_fields.get("tender_number") or {}).get("value"))),
        "closing_date_detected": _json_bool(bool((evidence_fields.get("closing_date") or {}).get("value"))),
        "boq_detected": _json_bool(bool(result_data.get("boq_items"))),
        "boq_item_count": len(result_data.get("boq_items") or []),
        "work_categories_detected_json": json.dumps(sorted(trade_summary.keys())),
        "pricing_executed": _json_bool(bool(result_data.get("pricing_result"))),
        "readiness_score": readiness_score,
        "submission_package_generated": submission_package_generated,
        "completion_guide_generated": completion_guide_generated,
        "processing_status": processing_status,
        "warnings_count": warnings_count,
        "errors_count": errors_count,
        "upload_time_ms": upload_time_ms,
        "validation_time_ms": validation_time_ms,
        "ocr_duration_ms": ocr_duration_ms,
        "text_extraction_duration_ms": text_extraction_duration_ms,
        "entity_extraction_duration_ms": entity_extraction_duration_ms,
        "boq_duration_ms": boq_duration_ms,
        "pricing_duration_ms": pricing_duration_ms,
        "report_generation_duration_ms": report_generation_duration_ms,
        "zip_package_generation_duration_ms": zip_package_generation_duration_ms,
        "total_processing_time_ms": total_processing_time_ms,
        "average_page_processing_time_ms": avg_page_processing,
        "is_scanned": _json_bool(bool(doc_characteristics["is_scanned"])),
        "is_digital": _json_bool(bool(doc_characteristics["is_digital"])),
        "contains_boq": _json_bool(bool(doc_characteristics["contains_boq"])),
        "contains_drawings": _json_bool(bool(doc_characteristics["contains_drawings"])),
        "contains_tables": _json_bool(bool(doc_characteristics["contains_tables"])),
        "contains_appendices": _json_bool(bool(doc_characteristics["contains_appendices"])),
        "contains_pricing_schedules": _json_bool(bool(doc_characteristics["contains_pricing_schedules"])),
        "contains_forms": _json_bool(bool(doc_characteristics["contains_forms"])),
        "contains_signatures": _json_bool(bool(doc_characteristics["contains_signatures"])),
        "contains_evaluation_criteria": _json_bool(bool(doc_characteristics["contains_evaluation_criteria"])),
        "contains_mandatory_documentation": _json_bool(bool(doc_characteristics["contains_mandatory_documentation"])),
        "extraction_quality_json": json.dumps(quality),
        "document_characteristics_json": json.dumps(doc_characteristics),
        "raw_metrics_json": json.dumps({
            "events": events,
            "tender_result_row_present": tender_result_row is not None,
        }),
    }
    return record


async def store_platform_analytics(job_id: str, result_data: Dict[str, Any]) -> None:
    record = await build_platform_analytics_record(job_id, result_data)
    db = await get_db()
    try:
        columns = list(record.keys())
        placeholders = ", ".join(["?"] * len(columns))
        await db.execute(
            f"INSERT OR REPLACE INTO platform_analytics ({', '.join(columns)}) VALUES ({placeholders})",
            tuple(record[column] for column in columns),
        )
        await db.commit()
    finally:
        await close_db(db)


async def _fetch_analytics_rows(days: Optional[int] = None) -> List[Dict[str, Any]]:
    db = await get_db()
    try:
        sql = "SELECT * FROM platform_analytics"
        params: List[Any] = []
        if days is not None:
            cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
            sql += " WHERE completed_at IS NOT NULL AND completed_at >= ?"
            params.append(cutoff)
        sql += " ORDER BY completed_at DESC, id DESC"
        cursor = await db.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await close_db(db)


def _completed_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [row for row in rows if row.get("processing_status") in {"completed", "partial_success"}]


def _avg(values: List[Optional[float]]) -> Optional[float]:
    actual = [float(v) for v in values if v is not None]
    if not actual:
        return None
    return round(sum(actual) / len(actual), 2)


def _counter_from_json_list(rows: List[Dict[str, Any]], field: str) -> Dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        values = _safe_json_load(row.get(field)) or []
        if isinstance(values, list):
            for value in values:
                if value:
                    counter[str(value)] += 1
    return dict(counter.most_common())


async def get_analytics_summary(days: int = 30) -> Dict[str, Any]:
    rows = await _fetch_analytics_rows(days)
    completed = _completed_rows(rows)
    return {
        "total_tenders_processed": len(rows),
        "successful_jobs": sum(1 for row in rows if row.get("processing_status") == "completed"),
        "failed_jobs": sum(1 for row in rows if row.get("processing_status") == "failed"),
        "partial_success_jobs": sum(1 for row in rows if row.get("processing_status") == "partial_success"),
        "average_processing_time_ms": _avg([row.get("total_processing_time_ms") for row in completed]),
        "average_readiness_score": _avg([row.get("readiness_score") for row in completed]),
        "ocr_usage_percent": round((sum(1 for row in completed if row.get("ocr_used")) / len(completed)) * 100, 2) if completed else None,
        "digital_pdf_percent": round((sum(1 for row in completed if row.get("is_digital")) / len(completed)) * 100, 2) if completed else None,
        "average_boq_items": _avg([row.get("boq_item_count") for row in completed]),
    }


async def get_analytics_dashboard(days: int = 30) -> Dict[str, Any]:
    rows = await _fetch_analytics_rows(days)
    completed = _completed_rows(rows)

    currencies = Counter(row.get("detected_currency") for row in completed if row.get("detected_currency"))
    jurisdictions = Counter(row.get("detected_jurisdiction") for row in completed if row.get("detected_jurisdiction"))
    procurement_methods = Counter(row.get("procurement_method") for row in completed if row.get("procurement_method"))
    industries = Counter()
    warnings_counter = Counter()
    failures_counter = Counter()
    missing_documents_counter = Counter()
    field_confidences: Dict[str, List[float]] = defaultdict(list)

    for row in completed:
        quality = _safe_json_load(row.get("extraction_quality_json")) or {}
        raw_metrics = _safe_json_load(row.get("raw_metrics_json")) or {}
        tender_result_row_present = raw_metrics.get("tender_result_row_present")
        if tender_result_row_present:
            industries[row.get("detected_jurisdiction") or "Unknown"] += 0
        for field_key, metric in quality.items():
            conf = _normalize_confidence(metric.get("confidence"))
            if conf == "High":
                field_confidences[field_key].append(1.0)
            elif conf == "Medium":
                field_confidences[field_key].append(0.6)
            elif conf == "Low":
                field_confidences[field_key].append(0.3)
        raw = _safe_json_load(row.get("raw_metrics_json")) or {}
        for event in raw.get("events", []):
            if event.get("status") == "failed":
                failures_counter[str(event.get("stage"))] += 1

    db = await get_db()
    try:
        cursor = await db.execute("SELECT warnings_json FROM tender_results")
        warning_rows = await cursor.fetchall()
        for warning_row in warning_rows:
            warning_list = _safe_json_load(warning_row[0]) or []
            if isinstance(warning_list, list):
                for warning in warning_list:
                    warning_text = str(warning)
                    warnings_counter[warning_text] += 1
                    if "missing" in warning_text.lower():
                        missing_documents_counter[warning_text] += 1
    finally:
        await close_db(db)

    avg_confidence_by_field = {
        field: round(sum(values) / len(values), 3)
        for field, values in field_confidences.items() if values
    }

    return {
        "summary": await get_analytics_summary(days),
        "most_common_currencies": currencies.most_common(10),
        "most_common_jurisdictions": jurisdictions.most_common(10),
        "most_common_procurement_methods": procurement_methods.most_common(10),
        "most_common_industries": industries.most_common(10),
        "most_common_missing_documents": missing_documents_counter.most_common(10),
        "most_common_warnings": warnings_counter.most_common(10),
        "most_common_failures": failures_counter.most_common(10),
        "average_confidence_by_field": avg_confidence_by_field,
    }


async def get_extraction_scorecard(days: int = 30) -> Dict[str, Any]:
    rows = _completed_rows(await _fetch_analytics_rows(days))
    total = len(rows)
    if total == 0:
        return {"total_completed_jobs": 0, "metrics": {}}

    def pct(count: int) -> float:
        return round((count / total) * 100, 2)

    metrics = {
        "employer_extraction_success": pct(sum(1 for row in rows if row.get("employer_detected"))),
        "tender_number_success": pct(sum(1 for row in rows if row.get("tender_number_detected"))),
        "currency_success": pct(sum(1 for row in rows if row.get("detected_currency"))),
        "closing_date_success": pct(sum(1 for row in rows if row.get("closing_date_detected"))),
        "boq_success": pct(sum(1 for row in rows if row.get("boq_detected"))),
        "pricing_success": pct(sum(1 for row in rows if row.get("pricing_executed"))),
        "submission_package_success": pct(sum(1 for row in rows if row.get("submission_package_generated"))),
        "completion_guide_success": pct(sum(1 for row in rows if row.get("completion_guide_generated"))),
        "export_success": pct(sum(1 for row in rows if row.get("completion_guide_generated") or row.get("submission_package_generated"))),
        "zip_success": pct(sum(1 for row in rows if row.get("submission_package_generated"))),
    }
    return {"total_completed_jobs": total, "metrics": metrics}


async def get_performance_metrics(days: int = 30) -> Dict[str, Any]:
    rows = _completed_rows(await _fetch_analytics_rows(days))
    return {
        "average_upload_time_ms": _avg([row.get("upload_time_ms") for row in rows]),
        "average_validation_time_ms": _avg([row.get("validation_time_ms") for row in rows]),
        "average_ocr_duration_ms": _avg([row.get("ocr_duration_ms") for row in rows]),
        "average_text_extraction_duration_ms": _avg([row.get("text_extraction_duration_ms") for row in rows]),
        "average_entity_extraction_duration_ms": _avg([row.get("entity_extraction_duration_ms") for row in rows]),
        "average_boq_duration_ms": _avg([row.get("boq_duration_ms") for row in rows]),
        "average_pricing_duration_ms": _avg([row.get("pricing_duration_ms") for row in rows]),
        "average_report_generation_duration_ms": _avg([row.get("report_generation_duration_ms") for row in rows]),
        "average_zip_package_generation_duration_ms": _avg([row.get("zip_package_generation_duration_ms") for row in rows]),
        "average_total_processing_time_ms": _avg([row.get("total_processing_time_ms") for row in rows]),
        "average_page_processing_time_ms": _avg([row.get("average_page_processing_time_ms") for row in rows]),
    }


async def get_trends(days: int = 365) -> Dict[str, Any]:
    rows = await _fetch_analytics_rows(days)
    daily: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "processed": 0,
        "completed": 0,
        "failed": 0,
        "avg_readiness_score": None,
        "avg_processing_time_ms": None,
    })
    daily_scores: Dict[str, List[float]] = defaultdict(list)
    daily_times: Dict[str, List[float]] = defaultdict(list)

    for row in rows:
        completed_at = row.get("completed_at") or row.get("created_at")
        if not completed_at:
            continue
        day_key = str(completed_at)[:10]
        daily[day_key]["processed"] += 1
        if row.get("processing_status") in {"completed", "partial_success"}:
            daily[day_key]["completed"] += 1
        if row.get("processing_status") == "failed":
            daily[day_key]["failed"] += 1
        if row.get("readiness_score") is not None:
            daily_scores[day_key].append(float(row["readiness_score"]))
        if row.get("total_processing_time_ms") is not None:
            daily_times[day_key].append(float(row["total_processing_time_ms"]))

    trend_rows = []
    for day_key in sorted(daily.keys()):
        entry = daily[day_key]
        entry["avg_readiness_score"] = _avg(daily_scores.get(day_key, []))
        entry["avg_processing_time_ms"] = _avg(daily_times.get(day_key, []))
        trend_rows.append({"date": day_key, **entry})

    return {"range_days": days, "daily": trend_rows}


async def export_analytics_csv(days: int = 30) -> str:
    rows = await _fetch_analytics_rows(days)
    output = io.StringIO()
    if not rows:
        return ""
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue()
