# Tender Engine AI — Technical Code Audit

**Auditor:** Senior Software Engineer (Python, Web Apps, Document Processing, Production Reliability)  
**Date:** 7 December 2026  
**Scope:** Full codebase analysis — architecture, reliability, correctness, security, testing, deployment

---

## Executive Verdict

**Code quality is above average for a prototype, but production readiness is poor.**

The codebase shows genuine engineering discipline: consistent error handling patterns, well-structured async pipelines, thorough input validation, and a clear separation of concerns. The upload security layer is particularly well-implemented — it's the strongest part of the system.

However, there are **three critical bugs** that will cause data loss or incorrect outputs in production, and **five high-priority technical debt items** that will make the system painful to operate at any scale beyond 5–10 concurrent users.

The system is **not production-ready** in its current state. With 3–4 weeks of focused work on the critical and high-priority items, it could be deployed for a controlled beta of 10–15 users.

---

## Code Quality Score: 6.2 / 10

| Category | Score | Key Strengths | Key Weaknesses |
|----------|-------|---------------|----------------|
| Architecture | 6 | Pipeline stage isolation, partial-success handling, cascading fallbacks | Dual job systems, SQLite bottleneck, no task queue |
| Reliability | 5 | Timeout protection, OCR fallback, graceful error handling | Pricing fails on most first uploads, no retry limits, no circuit breakers |
| Correctness | 5 | Deterministic extraction, honest fallbacks | Win probability can go negative, compliance gaps are boilerplate, BOQ scoring is wrong for non-construction |
| Security | 8 | Magic byte validation, MIME cross-check, filename sanitization, SQL parameter binding | No rate limiting, no auth on status/result endpoints, file cleanup on failure is best-effort |
| Testing | 5 | Good upload security tests, SQL binding tests, timeout tests | No integration tests, no pricing engine tests, no frontend tests, no E2E tests |
| Deployment | 4 | Multi-stage Docker, non-root user, healthcheck | SQLite in Docker, no migrations, single worker, no monitoring, no backup strategy |
| **Total** | **6.2** | | |

---

## Critical Bugs (Will Cause Data Loss or Incorrect Outputs)

### CRITICAL-1: Win Probability Index Can Produce Negative Values

**File:** `api/services/pipeline.py`, lines 693–704

```python
if critical_traps:
    win_probability -= len(critical_traps) * 15
    win_probability_explanation = f"Win probability lowered due to {len(critical_traps)} critical trap(s) detected."
```

A document with 4+ detected traps produces `50 - (4 × 15) = -10`. The value is clamped to 0 at line 704, but the explanation still says "Win probability lowered due to 4 critical trap(s) detected" — which is meaningless guidance. A score of 0 with no explanation of *why* it's 0 is worse than no score at all.

**Impact:** User sees "Win Probability: 0%" with no actionable explanation. Destroys trust in the tool.

**Fix:** Either remove the Win Probability Index entirely (recommended) or replace it with a "Data Completeness Score" that is purely factual: "12 of 18 required fields detected (67% complete)."

---

### CRITICAL-2: Compliance Gap Analysis Returns Boilerplate for Every Job

**File:** `api/services/pipeline.py`, lines 678–686

```python
standard_sme_requirements = [
    ("CIPC Registration", "Not verified - please confirm your CIPC registration status."),
    ("B-BBEE Certificate", "Not verified - please confirm your B-BBEE status."),
    ("Tax Clearance Certificate", "Not verified - please confirm your tax clearance status."),
    ("CIDB Registration", "Not verified - please confirm your CIDB registration status."),
]

for req, gap in standard_sme_requirements:
    compliance_gaps.append(gap)
```

Every single tender report says exactly the same four things. This is not analysis — it's a template. A user who uploads 10 different tenders gets the exact same compliance gaps every time. This is the single biggest gap between what the README promises and what the code delivers.

**Impact:** Users will quickly realize the "compliance gap analysis" is hardcoded text. Destroys credibility.

**Fix:** Either integrate real OSINT checks (CIPC, CIDB, SARS) or remove the compliance gaps section entirely. A half-implemented feature is worse than no feature.

---

### CRITICAL-3: SQLite Single-Writer Bottleneck Will Cause Data Loss Under Concurrent Load

**File:** `api/services/database.py`, lines 211–217

```python
async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db
```

Every route handler calls `get_db()` → creates a new connection → executes queries → calls `close_db()`. Under concurrent load:
- SQLite WAL mode allows concurrent reads but **serializes writes**
- Two simultaneous uploads will queue on the first `INSERT`
- The pipeline's `_update_job` and `_store_result` calls compete with route handler reads
- No connection pooling — each request opens/closes a connection

**Impact:** Under 5+ concurrent uploads, users will experience timeout errors and failed jobs. Under 10+, the database will become a bottleneck that causes cascading failures.

**Fix:** Replace SQLite with PostgreSQL (or at minimum add aiosqlite connection pooling with WAL mode properly configured). This is a prerequisite for any paid tier.

---

## High-Priority Technical Debt

### HIGH-1: No Task Queue — Background Jobs Run in the API Process

**File:** `api/routes/process.py`, lines 442–447

```python
asyncio.create_task(
    run_pipeline(
        job_id, file_path, original_name, user_email,
        file_hash=file_hash, mime_type=mime_type, file_size=len(contents),
    )
)
```

The pipeline runs as an asyncio task in the same process as the API server. This means:
- A long-running OCR job (up to 300s) blocks the event loop for other requests
- If the API server restarts, all in-flight jobs are lost
- No visibility into queue depth or job progress
- No way to distribute work across multiple workers

**Impact:** Any OCR-heavy upload will degrade API responsiveness for all users. Server restarts lose in-flight work.

**Fix:** Extract pipeline execution to a task queue (Redis + Celery, or at minimum a separate process with a job table polled by a scheduler).

---

### HIGH-2: Pricing Engine Fails on Most First-Time Uploads

**File:** `api/services/pricing_service.py`, lines 276–301

```python
if not sector:
    raise PricingServiceError(...)
if cost_per_hour is None or cost_per_hour <= 0:
    raise PricingServiceError(...)
if duration_months is None or duration_months <= 0:
    raise PricingServiceError(...)
```

Pricing requires sector, cost_per_hour, and duration_months. For a first-time user uploading a tender document:
- Sector detection is heuristic and often fails (returns None)
- Duration detection is heuristic and often fails (returns None)
- cost_per_hour defaults to 100.0 (hardcoded in pipeline.py line 391)

When pricing fails, the entire pipeline still returns `partial_success`, but the user sees "Pricing Unavailable" in the readiness report. This is the **most common user flow** and it ends in failure.

**Impact:** The majority of first-time users will see a failed pricing stage. This kills conversion.

**Fix:** Make pricing optional. If sector/duration can't be extracted, skip pricing gracefully and show "Pricing requires manual input — provide sector and duration to enable." Do not fail the stage.

---

### HIGH-3: No Rate Limiting or Auth Enforcement on Status/Result Endpoints

**File:** `api/routes/process.py`, lines 461–503

```python
async def process_status(
    job_id: str,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
```

The `get_current_user_optional` dependency means anyone can poll any job's status and results if they know the job_id. Job IDs are UUID4 hex strings (32 chars, 128 bits of entropy), so brute-forcing is impractical. But:
- No rate limiting on any endpoint
- No per-user job isolation (user A can see user B's results if they have the job_id)
- No request size limits on upload (beyond the 50MB file size check)
- No IP-based throttling

**Impact:** An attacker with a valid job_id can access another user's tender documents. No protection against DoS via repeated uploads.

**Fix:** Add rate limiting (slowapi or custom middleware). Enforce job ownership for authenticated users. Add IP-based throttling for anonymous uploads.

---

### HIGH-4: No Database Migration System

**File:** `api/services/database.py`, lines 76–83, 156–175

```python
try:
    cursor.execute("ALTER TABLE processing_jobs ADD COLUMN retry_count INTEGER DEFAULT 0")
except sqlite3.OperationalError:
    pass  # Column already exists
```

Schema changes are handled via `try/except OperationalError: pass`. This means:
- No versioned migrations
- No rollback capability
- Silent failures if a column addition fails for unexpected reasons
- Impossible to know what schema version is deployed

**Impact:** Any schema change in production requires manual intervention. A failed migration could corrupt the database with no recovery path.

**Fix:** Use Alembic or a simple versioned migration system. At minimum, track schema version in a metadata table.

---

### HIGH-5: Uploaded Files Are Never Cleaned Up

**File:** `api/routes/process.py`, lines 395–396

```python
with open(file_path, "wb") as f:
    f.write(contents)
```

Files are written to `storage/uploads/` and never deleted. There is:
- No cleanup job for old files
- No storage quota per user
- No maximum file age
- No cleanup on job deletion

**Impact:** Storage will grow unbounded. A user uploading 10 50MB PDFs per day will consume 15GB/month. No mechanism to reclaim space.

**Fix:** Add a periodic cleanup task (delete files older than 30 days). Add per-user storage quotas. Clean up files when jobs are deleted.

---

## Medium/Low Issues

### MEDIUM-1: `_is_binary_content` Only Samples First 512 Bytes

**File:** `api/routes/process.py`, line 153

```python
sample = data[:sample_size]
```

A file with 512 bytes of ASCII text followed by binary content would pass the binary check. This is a low-risk bypass for .txt uploads, but should be noted.

**Fix:** Sample the entire file or at minimum check the first and last 512 bytes.

---

### MEDIUM-2: `_sanitise_filename` Has a Logic Gap for Backslash Path Traversal

**File:** `api/routes/process.py`, lines 93–94

```python
filename = re.sub(r"[/\\\x00-\x1f]", "", filename)
```

Backslashes are removed, then `".."` is checked in the cleaned result. But the route handler (line 322) checks `".." in file.filename` on the *original* filename. A filename like `..\\..\\file.txt` would:
1. Pass the route handler's `..` check (because the original has `..\\..` not `..`)
2. Have backslashes removed by `_sanitise_filename`, becoming `....file.txt`
3. Then `".." in safe_name` would catch it

So this is actually caught, but by coincidence rather than design. The route handler and sanitisation function have overlapping but inconsistent checks.

**Fix:** Centralize all filename validation in `_sanitise_filename` and remove the redundant checks from the route handler.

---

### MEDIUM-3: BOQ Scoring Penalizes Non-Construction Tenders

**File:** `api/services/tender_readiness_service.py`, lines 195–202

```python
WEIGHTS = {
    "extraction_quality": 0.15,
    "entity_completeness": 0.20,
    "boq_completeness": 0.20,
    "pricing_availability": 0.20,
    "workforce_availability": 0.10,
    "document_integrity": 0.15,
}
```

BOQ completeness (20%) and pricing availability (20%) together account for 40% of the readiness score. For framework agreements, maintenance contracts, or professional service tenders that don't have BOQs, the score will be unfairly penalized.

**Fix:** Make BOQ scoring optional or context-aware. If no BOQ is detected, redistribute its weight to entity_completeness and document_integrity.

---

### MEDIUM-4: No Logging Configuration in Production

**File:** `api/main.py`, line 104

```python
logging.basicConfig(level=logging.INFO)
```

Logging goes to stdout with no structured format, no log levels beyond INFO, and no log rotation. In production:
- Cannot filter logs by module or severity
- Cannot ship logs to a centralized system
- No request IDs for tracing
- No performance metrics

**Fix:** Add structured logging (structlog or json-logging). Add request ID middleware. Configure log levels per module.

---

### MEDIUM-5: Frontend Has No Error Boundaries

**File:** `tender-engine-frontend/src/components/ReadinessAssessment.tsx`

The frontend component assumes `report.readiness_score`, `report.missing_information`, etc. are always present. If the API returns a malformed response, the component will crash with an unhandled TypeError.

**Fix:** Add null-checking and default values for all API response fields. Add React error boundaries.

---

### LOW-1: Hardcoded `cost_per_hour` Default of 100.0

**File:** `api/services/pipeline.py`, line 391

```python
cost_per_hour = 100.0  # default fallback
```

This is used when no BOQ rates are available. R100/hour is reasonable for cleaning but wrong for electrical (R300–R500) or IT consulting (R800–R1500). This should be sector-aware or configurable.

---

### LOW-2: `_load_existing_result` in retry_pipeline.py Returns None Always

**File:** `api/services/retry_pipeline.py`, lines 132–140

```python
def _load_existing_result(job_id: str) -> Optional[Dict[str, Any]]:
    return None  # Placeholder — actual loading happens in retry function
```

Dead code. The function is never called. Remove it.

---

### LOW-3: French i18n Files Exist But No French Market

**File:** `tender-engine-frontend/src/locales/fr/common.json`, `fr/landing.json`

Internationalization for French is implemented but the product targets South African SMEs. This adds maintenance overhead for zero business value.

**Fix:** Remove French i18n until there's a validated need.

---

## What to Fix First (Ordered by Impact)

| Priority | Fix | Effort | Why Now |
|----------|-----|--------|---------|
| 1 | Fix Win Probability Index (CRITICAL-1) | 1 day | Current implementation produces meaningless/negative values. Undermines all credibility. |
| 2 | Fix Compliance Gap Analysis (CRITICAL-2) | 2 weeks | Boilerplate text is worse than no text. Either integrate OSINT or remove the feature. |
| 3 | Replace SQLite with PostgreSQL (CRITICAL-3) | 3 weeks | Required for any concurrent usage. Without this, the system cannot scale past 5 users. |
| 4 | Add task queue for pipeline jobs (HIGH-1) | 2 weeks | OCR jobs block the API process. Server restarts lose in-flight work. |
| 5 | Make pricing optional/graceful (HIGH-2) | 3 days | Most first-time users see pricing failure. This kills conversion. |
| 6 | Add rate limiting + auth enforcement (HIGH-3) | 2 days | Security gap. No protection against DoS or cross-user data access. |
| 7 | Add database migration system (HIGH-4) | 2 days | Schema changes are fragile. No rollback capability. |
| 8 | Add file cleanup mechanism (HIGH-5) | 1 day | Storage grows unbounded. No way to reclaim space. |
| 9 | Fix BOQ scoring for non-construction tenders (MEDIUM-3) | 1 day | False low scores for valid tenders without BOQs. |
| 10 | Add structured logging (MEDIUM-4) | 1 day | Cannot debug production issues without it. |

---

## What Is Safe to Leave Alone for Now

| Component | Why It's Safe |
|-----------|---------------|
| Upload security validation | Thorough, well-tested, production-quality. Magic byte detection, MIME cross-check, filename sanitization are all solid. |
| Pipeline stage isolation | Partial-success handling, timeout protection, and per-stage event logging are well-designed. |
| Cascading field extraction | The metadata → result fields → full-text regex → blank underscore pattern is correct and maintainable. |
| Submission letter PDF generation | Professional-quality output. Reportlab formatting is solid. |
| Export suite (Excel, CSV, PDF) | Works correctly. No bugs found in export generation. |
| Retry pipeline logic | Dependency resolution, stage ordering, and metadata tracking are well-implemented. |
| Frontend integrity enforcement | "Manual Review Required" header persistence is correct UX. |
| Audit logging | Per-stage audit with timestamps, confidence, warnings, and errors. Good transparency feature. |
| OCR fallback with confidence reporting | Appropriate caution about OCR quality. Correct two-phase approach. |
| Dockerfile structure | Multi-stage build, non-root user, healthcheck, dependency isolation. Well-structured. |

---

## Production Readiness: NO-GO

**The system is not production-ready.** Three critical bugs and five high-priority debt items must be addressed before any paid deployment.

### Minimum Viable Production Checklist

Before opening to paying customers:

- [ ] **CRITICAL-1**: Fix or remove Win Probability Index
- [ ] **CRITICAL-2**: Fix compliance gap analysis (integrate OSINT or remove)
- [ ] **CRITICAL-3**: Replace SQLite with PostgreSQL
- [ ] **HIGH-1**: Add task queue (Redis + Celery or equivalent)
- [ ] **HIGH-2**: Make pricing optional/graceful on failure
- [ ] **HIGH-3**: Add rate limiting and auth enforcement
- [ ] **HIGH-4**: Add database migration system
- [ ] **HIGH-5**: Add file cleanup mechanism
- [ ] **MEDIUM-3**: Fix BOQ scoring for non-construction tenders
- [ ] **MEDIUM-4**: Add structured logging

### Estimated Effort: 4–6 weeks for a single developer

### Recommended Approach

1. **Week 1:** Fix CRITICAL-1, CRITICAL-2, HIGH-2, MEDIUM-3 (surgical fixes, no infrastructure changes)
2. **Week 2:** Add HIGH-3, HIGH-4, HIGH-5, MEDIUM-4 (operational hardening)
3. **Weeks 3–4:** CRITICAL-3 + HIGH-1 (infrastructure — PostgreSQL + task queue)
4. **Week 5:** Integration testing, load testing, security review
5. **Week 6:** Controlled beta launch (10–15 users, hand-hold, iterate)

---

## Summary

The codebase has genuine engineering strengths — the upload security layer, pipeline architecture, cascading field extraction, and frontend integrity enforcement are all well-implemented. The developer(s) understand async Python, error handling patterns, and defensive coding.

But the system has three critical flaws that make it unsuitable for production:

1. **The analysis features don't deliver what the README promises.** Win Probability is arithmetic, compliance gaps are boilerplate, trap detection is keyword search. This is the biggest risk — not because the code crashes, but because users will quickly realize the tool doesn't provide the value it claims.

2. **SQLite cannot handle concurrent users.** This is a hard scalability ceiling. Any paid tier requires PostgreSQL.

3. **Background jobs in the API process are fragile.** OCR-heavy uploads degrade responsiveness. Server restarts lose work. No monitoring.

Fix these three things, and the rest of the system is solid enough for a controlled beta.