"""
Permanent Processing Audit Log Service.

This is NOT a debugging tool.
It is a permanent transparency feature.

Every processing job records every stage with:
  - timestamp
  - status (success / warning / failed)
  - duration_ms
  - confidence (if applicable)
  - source module
  - warnings
  - errors

Failures NEVER disappear. They are recorded with explicit reasons.

This becomes one of Tender Engine's core differentiators.
Transparency is a feature.
"""
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..services.database import get_db, close_db, utc_now_naive

logger = logging.getLogger(__name__)

# ── Audit log stage definitions ──────────────────────────────────────
# These are the canonical stages that every processing job must record.

AUDIT_STAGES = [
    "upload_received",
    "pdf_fingerprint",
    "ocr_completed",
    "document_classification",
    "jurisdiction_detection",
    "language_detection",
    "currency_detection",
    "numeric_entity_classification",
    "tender_metadata_extraction",
    "boq_extraction",
    "pricing_completed",
    "workforce_estimation",
    "schedule_extraction",
    "submission_letter_generation",
    "readiness_assessment",
    "audit_report_generation",
    "result_committed",
    "processing_complete",
]

# Mapping from pipeline stages to audit stages
PIPELINE_TO_AUDIT_MAP = {
    "upload_received": "upload_received",
    "metadata_extraction": "tender_metadata_extraction",
    "text_extraction": "ocr_completed",
    "entity_extraction": "document_classification",
    "boq_analysis": "boq_extraction",
    "pricing_calculation": "pricing_completed",
    "finalisation": "result_committed",
}


async def ensure_audit_log_table():
    """Create the audit_log table if it doesn't exist.
    
    This is called at startup alongside init_db().
    """
    from ..services.database import _get_connection
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                tender_id       TEXT NOT NULL,
                stage           TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'pending',
                timestamp       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                duration_ms     INTEGER,
                confidence      TEXT,
                source_module   TEXT,
                warnings        TEXT,
                errors          TEXT,
                details         TEXT,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tender_id) REFERENCES tenders(job_id)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_log_tender_id ON audit_log(tender_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_log_stage ON audit_log(stage)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_log_status ON audit_log(status)
        """)
        conn.commit()
        logger.info("[AUDIT_LOG] Table ensured")
    except Exception as e:
        logger.error("[AUDIT_LOG] Failed to create table: %s", e)
        raise
    finally:
        conn.close()


async def record_audit_event(
    tender_id: str,
    stage: str,
    status: str,
    duration_ms: Optional[int] = None,
    confidence: Optional[str] = None,
    source_module: Optional[str] = None,
    warnings: Optional[List[str]] = None,
    errors: Optional[List[str]] = None,
    details: Optional[str] = None,
) -> None:
    """Record a single audit event for a tender processing stage.
    
    This is the core recording function. Every stage of processing
    must call this to ensure complete transparency.
    
    Args:
        tender_id: The job_id of the tender being processed
        stage: The audit stage name (from AUDIT_STAGES)
        status: 'success', 'warning', or 'failed'
        duration_ms: How long the stage took in milliseconds
        confidence: Confidence level (High, Medium, Low, or None)
        source_module: The module that performed this stage
        warnings: List of warning messages
        errors: List of error messages
        details: Free-text details about the stage
    """
    try:
        db = await get_db()
        try:
            now = utc_now_naive()
            await db.execute(
                """INSERT INTO audit_log
                   (tender_id, stage, status, timestamp, duration_ms,
                    confidence, source_module, warnings, errors, details)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    tender_id,
                    stage,
                    status,
                    now,
                    duration_ms,
                    confidence,
                    source_module,
                    json.dumps(warnings) if warnings else None,
                    json.dumps(errors) if errors else None,
                    details,
                ),
            )
            await db.commit()
        finally:
            await close_db(db)
    except Exception as e:
        logger.error("[AUDIT_LOG] Failed to record event for %s stage=%s: %s",
                      tender_id, stage, e)


async def get_audit_log(tender_id: str) -> List[Dict[str, Any]]:
    """Retrieve the complete audit log for a tender.
    
    Returns all audit events ordered by timestamp ascending.
    This is the complete, permanent record of every processing stage.
    
    Args:
        tender_id: The job_id of the tender
        
    Returns:
        List of audit event dicts, each containing:
          - stage, status, timestamp, duration_ms
          - confidence, source_module, warnings, errors, details
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT stage, status, timestamp, duration_ms,
                      confidence, source_module, warnings, errors, details
               FROM audit_log
               WHERE tender_id = ?
               ORDER BY id ASC""",
            (tender_id,),
        )
        rows = await cursor.fetchall()
        
        events = []
        for row in rows:
            event = dict(row)
            # Parse JSON fields
            if event.get("warnings"):
                try:
                    event["warnings"] = json.loads(event["warnings"])
                except (json.JSONDecodeError, TypeError):
                    event["warnings"] = []
            else:
                event["warnings"] = []
                
            if event.get("errors"):
                try:
                    event["errors"] = json.loads(event["errors"])
                except (json.JSONDecodeError, TypeError):
                    event["errors"] = []
            else:
                event["errors"] = []
                
            events.append(event)
            
        return events
    finally:
        await close_db(db)


async def get_audit_summary(tender_id: str) -> Dict[str, Any]:
    """Get a summary of the audit log for a tender.
    
    Returns:
        - total_stages: Total number of stages recorded
        - successful: Number of successful stages
        - warnings: Number of stages with warnings
        - failed: Number of failed stages
        - total_duration_ms: Total processing duration
        - stages: List of all stages with their status
    """
    events = await get_audit_log(tender_id)
    
    successful = sum(1 for e in events if e["status"] == "success")
    warning_count = sum(1 for e in events if e["status"] == "warning")
    failed = sum(1 for e in events if e["status"] == "failed")
    total_duration = sum(e.get("duration_ms") or 0 for e in events)
    
    return {
        "tender_id": tender_id,
        "total_stages": len(events),
        "successful": successful,
        "warnings": warning_count,
        "failed": failed,
        "total_duration_ms": total_duration,
        "stages": [
            {
                "stage": e["stage"],
                "status": e["status"],
                "timestamp": e["timestamp"],
                "duration_ms": e.get("duration_ms"),
                "confidence": e.get("confidence"),
                "source_module": e.get("source_module"),
                "warnings": e.get("warnings", []),
                "errors": e.get("errors", []),
                "details": e.get("details"),
            }
            for e in events
        ],
    }


async def record_pipeline_stage(
    tender_id: str,
    pipeline_stage: str,
    success: bool,
    duration_ms: Optional[int] = None,
    confidence: Optional[str] = None,
    warnings: Optional[List[str]] = None,
    errors: Optional[List[str]] = None,
    details: Optional[str] = None,
) -> None:
    """Record a pipeline stage in the audit log.
    
    Maps the internal pipeline stage name to the canonical audit stage name.
    
    Args:
        tender_id: The job_id
        pipeline_stage: The internal pipeline stage name
        success: Whether the stage succeeded
        duration_ms: Duration in milliseconds
        confidence: Confidence level
        warnings: List of warnings
        errors: List of errors
        details: Additional details
    """
    audit_stage = PIPELINE_TO_AUDIT_MAP.get(pipeline_stage, pipeline_stage)
    
    if success:
        status = "success"
    else:
        status = "failed"
        if not errors:
            errors = [f"Stage '{pipeline_stage}' failed"]
    
    await record_audit_event(
        tender_id=tender_id,
        stage=audit_stage,
        status=status,
        duration_ms=duration_ms,
        confidence=confidence,
        source_module=f"pipeline.{pipeline_stage}",
        warnings=warnings,
        errors=errors,
        details=details,
    )


async def record_failure(
    tender_id: str,
    stage: str,
    reason: str,
    duration_ms: Optional[int] = None,
    source_module: Optional[str] = None,
) -> None:
    """Record a permanent failure for a stage.
    
    Failures NEVER disappear. They are always recorded with an explicit reason.
    
    Args:
        tender_id: The job_id
        stage: The audit stage name
        reason: Human-readable explanation of why it failed
        duration_ms: Duration before failure
        source_module: The module that failed
    """
    await record_audit_event(
        tender_id=tender_id,
        stage=stage,
        status="failed",
        duration_ms=duration_ms,
        source_module=source_module,
        errors=[reason],
        details=f"FAILED: {reason}",
    )


async def record_success(
    tender_id: str,
    stage: str,
    duration_ms: Optional[int] = None,
    confidence: Optional[str] = None,
    source_module: Optional[str] = None,
    warnings: Optional[List[str]] = None,
    details: Optional[str] = None,
) -> None:
    """Record a successful stage completion.
    
    Args:
        tender_id: The job_id
        stage: The audit stage name
        duration_ms: Duration in milliseconds
        confidence: Confidence level
        source_module: The module that completed
        warnings: Any warnings that occurred
        details: Additional details
    """
    status = "warning" if warnings else "success"
    await record_audit_event(
        tender_id=tender_id,
        stage=stage,
        status=status,
        duration_ms=duration_ms,
        confidence=confidence,
        source_module=source_module,
        warnings=warnings,
        details=details,
    )