# Tender Engine

## Project Vision
Tender Engine is a forensic compliance engine designed to eliminate disqualification traps for SME tenderpreneurs.

## Design Principles

This tool prioritises **data integrity**. We do not use placeholder data, fabricated market statistics, or simulated competitor activity. All outputs are derived directly from provided user data — nothing is invented, extrapolated, or embellished.

- **No synthetic data** — Every number, score, and recommendation comes from the actual tender documents uploaded by the user.
- **No fabricated competition** — We never display "other bidders" or "competitor activity" because we do not track or estimate competitor behaviour.
- **Transparent fallbacks** — When data is missing, the system renders blank underscore fields (PDF) or descriptive labels (UI) rather than hardcoded "N/A" values.
- **Auditable provenance** — All outputs include a disclaimer: *"No guesses. No invented data. Every result is backed by evidence."*

## Key Features

### Deterministic Architecture and No-Hallucination Policy
+ Tender Engine is deterministic by design.
+ No extracted value is invented.
+ No totals, entities, or deadlines are guessed.
+ Every visible output must originate from uploaded tender evidence, deterministic rules, or deterministic calculations based on extracted values.
+
+Evidence chain principles:
+- Raw document text is extracted first.
+- Structured evidence is attached to important fields.
+- Reports and exports reuse existing evidence instead of rescanning documents.
+- Missing values remain missing and trigger guidance rather than synthetic placeholders.
+
+Core evidence contract:
+- `value`
+- `confidence`
+- `page number`
+- `section`
+- `paragraph or sentence`
+- `detection method`
+- `source category`

### Disqualification Trap Detector
- Automated scanning to identify high-risk inconsistencies in tender documentation.
- Flags critical compliance gaps and potential disqualification risks before submission.

### Bid Response Roadmap
- A lean, itemized checklist that strips away legal fluff and provides actionable, page-referenced steps for bid submission.

### Executive Briefing
- An instant 'Go/No-Go' summary tool that empowers SMEs to make data-driven decisions in under 60 seconds.

### Risk Mitigation Dashboard
- 'Confidence Score' and 'Risk Assessment' features provide immediate transparency into tender data quality.
- Automated risk categorization: High/Medium/Low risk alerts with color-coded visual indicators.

### Submission Letter Generation
- Generates a formal, professional PDF submission letter suitable for direct submission with tender responses.
- Smart field auto-population with cascading fallbacks: metadata -> result fields -> full-text heuristic extraction -> blank underscore placeholders.
- Full-text heuristic extraction for missing fields using regex patterns tailored to South African tender documents.
- Professional letterhead styling, conditional body text, KeepTogether page-break protection.
- Missing fields render as blank underscore lines (`____________________`) for manual completion.
- Footer includes the mandatory disclaimer.

### Tender Completion Guide (v4.0)
A production-quality executive document that tells the contractor, estimator, procurement manager, and director what still needs to be completed before submission, who normally handles it, and how to get it done.

**Document sections (executive-quality report):**
1. **Cover Page** — Document metadata, jurisdiction, status badge, generation timestamp
2. **Executive Summary** — One-page director view with verified/missing status for tender number, project, employer, currency, closing date, BOQ, pricing, supporting documents, estimated remaining work, Tender Health Score, and submission recommendation
3. **Completion Status** — Overall readiness assessment with a large executive progress gauge
4. **Document Status Dashboard** — Visual extraction dashboard for Document Metadata, Tender Details, BOQ, Pricing, and Compliance with LOW/MEDIUM/HIGH overall extraction status
5. **Estimated Completion Plan** — Estimated remaining work with Today and Tomorrow completion tasks
6. **Verified Extracted Information** — Extracted values with evidence, page references, and verification context
7. **Evidence-Based Actions** — Deterministic completion actions backed by extracted evidence
8. **Missing Information** — Grouped as Critical Items, Required Items, and Optional Items
9. **Missing Documents** — Split into Tender Documents and Company Documents
10. **Recommended Workflow** — Step-by-step submission preparation sequence
11. **Printable Submission Checklist** — Desk-use tick-box checklist for final pack review
12. **Common Disqualification Mistakes** — Expanded procurement mistake-prevention guide using deterministic rules only
13. **Helpful Tender Tips** — Practical bid-team operational reminders
14. **Final Decision** — Executive sign-off panel with Tender Health Score, reasons, and recommendation
15. **Director Approval** — Printable final approval page for manual sign-off

**Tender Health Score (signature feature):**
- A deterministic `0–100` submission-readiness score
- Answers the business question: *"How close is this tender to being submission-ready?"*
- Uses only deterministic inputs already present in the live result:
  - document completeness
  - mandatory fields found
  - BOQ availability
  - pricing completion
  - supporting-documents checklist presence
- Displayed in both the Executive Summary and Final Decision section
- Separate from extraction confidence: it measures submission readiness, not extraction certainty

**Professional typography:**
- ReportLab engine with A4 pages, 2.2cm margins, clean hierarchy
- 10pt section headers in PRIMARY_BLUE (#1F4E79)
- 9pt body text in TEXT_DARK (#222222)
- Courier confidence bars, Monospace code-style progress meters
- Helvetica font family throughout

**Status badges (coloured, bordered, background-filled):**
- `● Critical` — Red badge on pink background
- `● High` — Amber badge on yellow background
- `● Medium` — Blue badge on light blue background
- `✓ Complete` — Green badge on light green background
- `○ Pending` — Amber badge (for manual checks)
- `✗ Missing` — Red badge (for absent data)

**Table layout (no overlap, no truncation):**
- All cell content wrapped in ReportLab Paragraph for auto word-wrap
- Column widths explicitly calculated to sum to available page width (16.6cm)
- 6px horizontal padding, 5px vertical padding in every cell
- Alternating row colours (white / light blue (#EEF5FC))
- Header row: white text on PRIMARY_BLUE background
- Grid lines at 0.4pt in #D0D7DE
- Dynamic row height — rows expand as needed, never clip text

**Footer (every page):**
```
Tender Engine                        v4.0.0 | Generated: 2026-07-15 10:20                   Page X of Y
Evidence-Based Document Processing
[QR Code] (links to Processing Audit)
```

**QR Code:**
- Generated using `qrcode` library with PIL backend
- Links to `{FRONTEND_URL}/audit/{job_id}` for real-time processing audit
- Configurable via `PUBLIC_URL` or `FRONTEND_URL` environment variables
- Falls back to `https://tender-engine.app/audit/{job_id}`

**Helpful Contacts mapping (who provides what):**
| Field | Contact |
|-------|---------|
| Sector | Estimator |
| Duration | Employer / Director |
| Locations | Employer / Engineer |
| BOQ Items | Estimator / Quantity Surveyor |
| Pricing | Estimator / Accountant |
| Workforce | Estimator / Contracts Manager |
| Schedule | Employer / Engineer / Architect |
| Currency | Accountant / Director |
| Tax Clearance | Accountant / Tax Practitioner |
| CSD Registration | Company Secretary / Director |
| B-BBEE Certificate | Director / Verification Agency |
| Company Registration | Company Secretary / Director |
| CIDB Registration | Director / Contracts Manager |
| Proof of Address | Admin Team / Finance Office |
| Bank Confirmation | Finance Team / Director |

**API:**
```python
from api.services.tender_completion_guide import generate_completion_guide

pdf_buffer = generate_completion_guide(job_id, result_data)
# Returns BytesIO with valid PDF content
```

**Architecture:**
- `api/services/tender_completion_guide.py` — Main generation module (718 lines)
- `api/services/report_framework.py` — Shared DataCompleteness, build_extracted_fields, build_missing_information
- `api/services/schema_manager.py` — Jurisdiction detection
- Dependencies: `reportlab`, `qrcode[pil]`, `Pillow`

### Comprehensive Export Suite
| Format | Endpoint | Description |
|--------|----------|-------------|
| Excel | `/api/export/{job_id}/excel` | Full tender data with BOQ, pricing, metadata |
| CSV | `/api/export/{job_id}/csv` | Lightweight data for spreadsheet analysis |
| PDF Report | `/api/export/{job_id}/pdf` | Professional summary report |
| Bid Response Roadmap | `/api/export/{job_id}/roadmap` | Actionable submission checklist (PDF) |
| Tender Integrity Audit | `/api/export/{job_id}/audit` | Compliance and risk audit report (PDF) |
| Submission Letter | `/api/export/{job_id}/submission-letter` | Formal cover letter for bid submission (PDF) |
| Tender Completion Guide | `/api/export/{job_id}/completion-guide` | Contractor completion manual (PDF) |

### Submission Package (NEW)
- **Package Manifest** — Full inventory of all generated documents with checksums
- **ZIP Package** — Single-file download containing all export formats
- **Processing Audit** — Immutable audit trail of all pipeline stages
- **Readiness Assessment** — Pre-submission readiness evaluation
- **Executive Summary** — Condensed decision-support briefing

### Platform Analytics
- Frontend route: `/analytics`
- Accessible directly from the application router, the main header navigation, and a dashboard card
- Uses live backend analytics endpoints only
- No mock analytics, no synthetic statistics, no fake fallback values
- Displays platform performance, extraction scorecard, trend data, document statistics, and export analytics
- Includes loading states, informative backend error states, and an empty state when no analytics exist
- Supports CSV export and print-to-PDF from the Analytics page

### Evidence-Based Processing
Every extraction decision is backed by:
- **Currency Engine** — Deterministic currency detection from document evidence (symbols, ISO codes, context)
- **Numeric Classifier** — ML-free heuristic classification of document regions
- **Entity Classifier** — Rule-based entity extraction (employer, project, location)
- **BOQ Engine v2** — Table-aware BOQ extraction with line-item reconstruction
- **Pricing Engine** — Deterministic pricing calculation from BOQ rates and quantities
- **Procurement Intelligence Engine** — Deterministic procurement entity extraction, procurement context detection, and document structure detection with section/page evidence
- **Decision Support Engine** — Evidence-based actions with priority, reason, evidence, responsible person, required documents, completion steps, and risk if ignored
- **Compliance Engine** — Missing information and missing document guidance that explains what is missing, why it matters, where it should be found, who usually supplies it, and what happens if ignored

### Evidence Chain in Reports and API
The following outputs reuse the same evidence chain:
- API processing result
- Tender Readiness Assessment
- Tender Completion Guide
- Submission Package ZIP
- Package Manifest
- Executive Summary
- Evidence Report

Cross-referencing is built into exported outputs so users can move between:
- Completion Guide
- Readiness Report
- Submission Letter
- Audit Report
- Roadmap
- Manifest

### International Support
- **South Africa** — Full compliance schema (CIDB, CSD, B-BBEE, SARS tax clearance)
- **Multi-currency** — ZAR, USD, EUR, GBP, and 24+ additional currencies
- **Jurisdiction-adaptive** — Automatic detection and document set switching
- **Extensible** — Add new jurisdiction schemas via JSON configuration

### Processing Workflow
```
Upload -> Parse -> Extract BOQ -> Detect Currency -> Calculate Pricing -> 
Generate Summary -> Build Reports -> Package Exports -> Return Result
```
Each stage reports independently, enabling partial-success handling.

## Technical Specifications

### Tender Completion Guide Service (`api/services/tender_completion_guide.py`)

A standalone PDF generation utility built on **ReportLab** that produces a professional 10-page Tender Completion Guide.

**Architecture:**
- `generate_completion_guide(job_id, result_data)` — Main entry point, returns `BytesIO` with PDF
- `_status_summary(result_data)` — Determines READY/PARTIAL/NOT_READY status with completeness metrics
- `_build_executive_summary(result_data, status)` — Director-facing one-page summary for fast review, including Tender Health Score
- `_build_confidence_summary(result_data)` — Executive document-status dashboard
- `_build_estimated_completion(result_data, status)` — Estimated completion plan with Today/Tomorrow tasks
- `_calculate_tender_health_score(result_data)` — Deterministic 0–100 submission-readiness score used in the executive summary and final decision panel
- `_build_missing_information_rows(result_data)` — Gaps with guidance and contact assignment
- `_build_document_rows(profile)` — Jurisdiction-specific document checklist with priority badges
- `_workflow_steps(result_data, status)` — Context-aware submission workflow
- `_checklist_items(result_data)` — Dynamic 11-item pre-submission checklist
- `_readiness_questions(result_data)` — 6-question sign-off grid with status badges
- `_build_table(headers, rows, col_widths)` — Generic table builder with auto-wrapping cells
- `_generate_qr_code(job_id)` — QR code generator linking to processing audit
- `_build_footer_table(canvas, doc, job_id)` — Multi-line footer with brand, version, timestamp, page numbers, QR code

**Status determination logic:**
```python
hard_stops = count([pricing_missing, boq_missing, duration_missing, sector_missing])
if hard_stops == 0 and completeness >= 80% -> READY FOR FINAL ASSEMBLY
if hard_stops <= 2 and completeness >= 50% -> PARTIALLY READY
else -> NOT READY TO SUBMIT
```

**Confidence scoring:**
```python
overall = metadata(15%) + BOQ(30%) + pricing(30%) + compliance(25%)
# Weighted average displayed with colour-coded bar
# Green >= 80%, Amber >= 50%, Red < 50%
```

**Jurisdiction support:**
- `south_africa` — 7 compliance documents, 5 common mistakes
- `default` — 4 compliance documents, 5 common mistakes
- Auto-detected via `SchemaManager.detect_jurisdiction(result_data)`

### Pipeline Architecture
The processing pipeline (`api/services/pipeline.py`) orchestrates:
- Document parsing and text extraction
- BOQ extraction (`api/services/boq_extractor.py`)
- Pricing calculation (`api/services/pricing_service.py`)
- Summary generation (`api/services/summary_builder.py`)
- PDF report generation (`api/services/pdf_report_service.py`)
- Roadmap and audit generation (`api/services/roadmap_audit_generator.py`)
- Submission letter generation (`api/services/submission_letter_service.py`)
- Tender Completion Guide generation (`api/services/tender_completion_guide.py`)
- Submission Package assembly (`api/services/submission_package_service.py`)

Each stage reports its status (completed/failed) independently, enabling partial-success handling in the UI.

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- Docker (optional, for containerised deployment)

### Backend Setup
```bash
# Install Python dependencies
pip install -r requirements.txt

# Run the API server
uvicorn api.main:app --reload --port 8000
```

### Frontend Setup
```bash
cd tender-engine-frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### Docker Deployment
```bash
docker-compose up --build
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/process` | Upload and process a tender document |
| GET | `/api/result/{job_id}` | Retrieve processing result |
| GET | `/api/export/{job_id}/excel` | Download Excel export |
| GET | `/api/export/{job_id}/csv` | Download CSV export |
| GET | `/api/export/{job_id}/pdf` | Download PDF report |
| GET | `/api/export/{job_id}/roadmap` | Download bid response roadmap |
| GET | `/api/export/{job_id}/audit` | Download tender integrity audit |
| GET | `/api/export/{job_id}/submission-letter` | Download submission letter PDF |
| GET | `/api/export/{job_id}/completion-guide` | Download tender completion guide PDF |
| GET | `/api/export/{job_id}/package` | Download full submission package (ZIP) |
| GET | `/api/export/{job_id}/manifest` | Download package manifest |

## Testing

```bash
# Run all tests
pytest tests/

# Run specific test suites
pytest tests/test_pipeline.py
pytest tests/test_pricing.py
pytest tests/test_boq_extractor.py
pytest tests/test_upload_security.py
pytest tests/test_hardening.py

# Generate sample Tender Completion Guide for visual validation
python tests/test_completion_guide_generation.py
# Output: sample_completion_guide.pdf
```

## Screenshots

| Screen | Description |
|--------|-------------|
| `screenshots/Processing Dashboard.jpg` | Main processing interface |
| `screenshots/Executive Dashboard.jpg` | Executive summary view |
| `screenshots/Detailed BOQ & Pricing.jpg` | BOQ and pricing breakdown |
| `screenshots/PDF Export.jpg` | PDF report output |
| `screenshots/Demo2.jpg` | Processing result view |
| `screenshots/Pricing Breakdown1.jpg` | Pricing details |
| `screenshots/Transparency Is Built In.jpg` | Evidence-based processing showcase |

## License
See [LICENSE.txt](LICENSE.txt) for details.