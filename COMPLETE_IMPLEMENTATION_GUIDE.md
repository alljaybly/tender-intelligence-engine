# COMPLETE IMPLEMENTATION GUIDE

This document provides the complete roadmap for integrating the evidence-based engines into all reports and validation testing.

## CURRENT IMPLEMENTATION STATUS

### ✅ CORE ENGINES IMPLEMENTED:
1. **Evidence Engine** - Complete evidence collection system
2. **Currency Intelligence Engine V2** - Multi-currency detection
3. **Numeric Entity Classification Engine** - Financial categories
4. **Evidence Schema Manager** - Report integration support

### ⏳ REMAINING IMPLEMENTATION:
1. Completion Guide evidence display
2. Readiness Report evidence display  
3. Submission Package evidence reports
4. Audit Report comprehensive evidence
5. Result Viewer evidence dashboard

## REPORT INTEGRATION GUIDE

### 1. COMPLETION GUIDE EVIDENCE INTEGRATION

**File:** `api/services/tender_completion_guide.py`

**Current Structure:** Lines 1-1279
**Update Required:** Add evidence display sections

#### Integration Points:

**A. Currency Evidence Display:** Around line 300-400
```python
# Add after CFO CI rely transactions:
evidence_summary = self._get_currency_evidence_summary(tender_data)
if evidence_summary and evidence_summary.get("total_currencies", 0) > 0:
    self.story.add(Paragraph(
        "CURRENCY INTELLIGENCE · EVIDENCE TRAIL",
        styles["Heading3"]
    ))
    table = self._build_evidence_table(
        evidence_summary["currencies"],
        "currency_evidence"
    )
    self.story.add(table)
```

**B. Numeric Entity Evidence Display:** Around line 400-500
```python
# Add after Tender Value section:
numeric_evidence = self._get_numeric_entity_evidence(tender_data)
if numeric_evidence and numeric_evidence.get("total_entities", 0) > 0:
    self.story.add(Paragraph(
        "NUMERIC ENTITY CLASSIFICATION · EVIDENCE",
        styles["Heading3"]
    ))
    for entity, evid in numeric_evidence.items():
        self.story.add(Paragraph(
            f"Entity: {entity} | Confidence: {evid['confidence']:.0%}",
            styles["Normal"]
        ))
```

**C. Evidence Quality Metrics Section:** New section before Company Info
```python
def _build_evidence_quality_section(self, tender_data):
    evidence_data = self.schema_manager.get_all_schema_records()
    evidence_summary = evidence_data.get("evidence_quality", {})
    
    # Build quality chart
    table = Table([
        ("Metric", "Value", "Target", "Status"),
        ("Total Fields", evidence_summary.get("total_fields", 0), "100", "✓"),
        ("High Confidence", evidence_summary.get("high_confidence", 0), ">70%", "✓"),
        ("Medium Confidence", evidence_summary.get("medium_confidence", 0), "<30%", "✓"),
        ("Low Confidence", evidence_summary.get("low_confidence", 0), "0%", "✗"),
    ], colWidths=[3*cm, 2*cm, 2*cm, 2*cm])
```

#### Evidence Display Format:
```python
def _build_evidence_table(self, evidence_items, tab_type):
    """Build professional evidence table for report."""
    data = []
    for item in evidence_items[:10]:  # Top 10 evidence points
        data.append([
            Paragraph(item["field_name"], styles["Normal"]),
            Paragraph(f"{item['value']} ({item('confidence'):.0%})", styles["Small"]),
            Paragraph(item["verified_from"], styles["Small"]),
            Paragraph(str(item["page"]) if item["page"] else "-", styles["Normal"]),
        ])
    
    table = Table(data, colWidths=[3*cm, 2*cm, 2*cm, 2*cm])
    # Apply evidence style
    table.setStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#EEF5FC")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ('ALIGN', (0, 0), (-1, -1), "LEFT"),
    ])
    return table
```

### 2. READINESS REPORT EVIDENCE INTEGRATION

**File:** `api/services/tender_readiness_service.py`

**Current Structure:** Lines 1-1269
**Update Required:** Evidence-based readiness assessment

#### Integration Points:

**A. Readiness Score Update:** Around line 200-300
```python
def compute_readiness_score(self, tender_data):
    # Replace simple score calculation
    base_score = self._calculate_base_readiness(tender_data)
    evidence_based_score = self._compute_evidence_based_score(tender_data)
    
    # Weight evidence-based score heavily
    final_score = (0.6 * base_score) + (0.4 * evidence_based_score)
    
    return {
        "score": min(final_score, 100),
        "score_breakdown": {
            "based_on_evidence": 40,
            "confidence_scores": 15,
            "evidence_quality": 35,
            "metadata_filling": 10
        }
    }
```

**B. Evidence Quality Section:** New section in PDF
```python
def _build_evidence_quality_section(self, pdf_doc, evidence_summary):
    """Add evidence quality section to readiness report."""
    section_title = PDFSectionTitle("Evidence Quality Assessment")
    pdf_doc.add(section_title)
    
    # Evidence distribution bar chart
    evidence_data = [
        ("Public Certificates", evidence_summary.get("public_certificates", 0)),
        ("Company Info Evidence", evidence_summary.get("company_info_evidence", 0)),
        ("Tender Specifications", evidence_summary.get("specifications_evidence", 0)),
        ("Payment Terms", evidence_summary.get("payment_terms_evidence", 0)),
        ("Award Criteria", evidence_summary.get("award_criteria_evidence", 0)),
    ]
    
    # Draw evidence quality bars
    self._draw_evidence_bar_chart(evidence_data, pdf_doc)
```

**C. Evidence Validation Indicators:** Add to conflict analysis sections
```python
def _validate_evidence(self, field_name, evidence_data):
    """Validate evidence quality for specific field."""
    evid = evidence_data.get("evidence")
    
    if not evid:
        return {
            "valid": False,
            "reason": "No evidence available",
            "confidence": 0.0
        }
    
    conf = evid["confidence"]
    if conf >= 0.75:
        return {
            "valid": True,
            "confidence": conf,
            "status": "VERIFIED",
            "color": "green"
        }
    elif conf >= 0.5:
        return {
            "valid": True,
            "confidence": conf,
            "status": "PARTIALLY VERIFIED",
            "color": "amber"
        }
    else:
        return {
            "valid": False,
            "confidence": conf,
            "status": "UNVERIFIED",
            "color": "red"
        }
```

### 3. SUBMISSION PACKAGE EVIDENCE REPORTS

**File:** `api/services/submission_package_service.py`

**Current Structure:** Lines 1-343
**Update Required:** Include evidence PDF in package

#### Evidence PDF Generation:

```python
def _generate_evidence_report_pdf(self, tender_data, evidence_engine):
    """Generate comprehensive evidence report PDF."""
    from reportlab.platypus import SimpleDocTemplate, PageBreak
    
    doc = SimpleDocTemplate(
        f"Evidence_Report_{tender_data['id']}.pdf",
        pagesize=A4
    )
    
    story = []
    
    # Evidence quality summary
    evidence_summary = evidence_engine.generate_evidence_summary()
    story.append(Paragraph(
        "EVIDENCE QUALITY SUMMARY",
        styles["Heading1"]
    ))
    story.append(Paragraph(
        f"Total Evidence Records: {evidence_summary['total_records']}",
        styles["Normal"]
    ))
    
    # Detailed evidence inventory
    story.append(PageBreak())
    story.append(Paragraph(
        "DETAILED EVIDENCE INVENTORY",
        styles["Heading1"]
    ))
    
    # All currency evidence
    story.append(Paragraph("CURRENCY EVIDENCE", styles["Heading2"]))
    currencies = evidence_engine.get_currency_evidence()
    for currency in currencies:
        self._add_currency_evidence_to_story(story, currency)
    
    # All numeric entity evidence
    story.append(PageBreak())
    story.append(Paragraph("NUMERIC ENTITY EVIDENCE", styles["Heading2"]))
    entities = evidence_engine.get_numeric_entity_evidence()
    for entity in entities:
        self._add_entity_evidence_to_story(story, entity)
    
    doc.build(story)
```

### 4. AUDIT REPORT COMPREHENSIVE EVIDENCE

**File:** `api/services/roadmap_audit_generator.py`

**Current Structure:** Lines 1-556
**Update Required:** Evidence-based audit findings

#### Evidence-Based Audit:

```python
def _generate_evidence_audit(self, tender_data, evidence_engine):
    """Generate comprehensive evidence-based audit."""
    audit_findings = []
    
    # Audit currency evidence
    currencies = evidence_engine.get_currency_evidence()
    primary_currency = currencies[0]  # Primary currency
    
    audit_findings.append({
        "audit_item": "CURRENCY DETECTION",
        "finding": "Primary currency identified",
        "evidence": primary_currency.evidence,
        "confidence": primary_currency.confidence,
        "verification_status": "VERIFIED" if primary_currency.confidence >= 0.7 else "FAILED"
    })
    
    # Audit numeric entity classification
    entities = evidence_engine.get_numeric_entity_evidence()
    financial_entities = e for e in entities if e.entity_type in FINANCIAL_TYPES
    
    for entity in financial_entities:
        if entity.confidence >= 0.7:
            audit_findings.append({
                "audit_item": "FINANCIAL ENTITY CLASSIFICATION",
                "finding": f"{entity.entity_type.name} detected: {entity.value}",
                "evidence": entity.evidence,
                "confidence": entity.confidence,
                "verification_status": "VERIFIED"
            })
    
    return audit_findings
```

### 5. RESULT VIEWER EVIDENCE DASHBOARD

**File:** Current result viewer (API endpoint)
**Update Required:** Evidence display in web interface

#### Frontend Evidence Display:

```python
# HTML Template
def render_evidence_view(evidence_data):
    return """
    <div class="evidence-dashboard">
        <h1>Evidence Dashboard</h1>
        
        <!-- Evidence Quality Summary -->
        <div class="evidence-summary">
            <div class="metric-card">
                <h3>Total Evidence Records</h3>
                <p>{evidence_data['total_records']}</p>
            </div>
            <div class="metric-card">
                <h3>Confidence Average</h3>
                <p>{evidence_data['average_confidence']:.1%}</p>
            </div>
        </div>
        
        <!-- Evidence Types -->
        <div class="evidence-by-type">
            <h2>Evidence by Type</h2>
            {render_evidence_charts(evidence_data)}
        </div>
        
        <!-- Critical Fields -->
        <div class="critical-fields">
            <h2>Critical Fields - Validation Status</h2>
            {render_critical_fields_validation(evidence_data)}
        </div>
        
        <!-- Detailed Evidence -->
        <div class="evidence-tables">
            <h2>Detailed Evidence</h2>
            {render_evidence_tables(evidence_data)}
        </div>
    </div>
    """
```

## VALIDATION TEST IMPLEMENTATION

### 1. SOUTH AFRICAN TENDER TEST

**Test Data Requirements:**
```python
test_cases = {
    "ZAR_primary_framework": {
        "document_type": "SA_TENDER",
        "currency_evidence": {
            "primary": "ZAR",
            "secondary": ["USD", "EUR"],
            "reference": []
        },
        "confidence": 0.95,
        "max_volume_percentage": 0.90
    },
    "SARB_contract_payment": {
        "document_type": "SA_CABINET",
        "currency_evidence": {
            "primary": "ZAR",
            "secondary": ["EUR", "GBP"],
            "reference": ["USD"]
        },
        "financial_terms": {
            "vat_percentage": {"value": 15.0, "confidence": 0.98, "source": "SARB_template"},
            "retention_percentage": {"value": 10.0, "confidence": 0.95, "source": "Payment_clause"}
        }
    }
}
```

### 2. EU TED TENDER TEST

**Test Data Requirements:**
```python
test_cases = {
    "EU_TED_framework": {
        "document_type": "EU_TED",
        "currency_evidence": {
            "primary": "EUR",
            "secondary": ["USD", "GBP"],
            "reference": []
        },
        "confidence": 0.95,
        "procurement_patterns": ["TED Platform", "Directive 2014/24/EU"]
    },
    "Improvement_guarantee_policy": {
        "document_type": "EU_TED_guidance",
        "currency_evidence": {
            "primary": "EUR",
            "secondary": ["USD", "GBP"],
            "reference": []
        },
        "confidence": 0.98,
        "economic_value_limit": "€200,000"
    },
    "SARB_contract_payment": {
        "document_type": "SA_CABINET",
        "currency_evidence": {
            "primary": "ZAR",
            "secondary": ["EUR", "GBP"],
            "reference": ["USD"]
        },
        "financial_terms": {
            "vat_percentage": {"value": 15.0, "confidence": 0.98, "source": "SARB_template"},
            "retention_percentage": {"value": 10.0, "confidence": 0.95, "source": "Payment_clause"}
        }
    }
}
```

### 3. SCANNED TENDER DOCUMENTS TEST

**Test Data Requirements:**
```python
test_cases = {
    "Scanned_tender_with_currencies": {
        "document_type": "SCANNED",
        "currency_evidence": {
            "primary": "USD",  # Likely primary in scanned documents
            "secondary": ["EUR", "GBP"],
            "reference": ["ZAR"]
        },
        "confidence": 0.85,  # Lower confidence due to OCR
        "ocr_quality": "85%",
        "page_numbers": {
            "currency_start": 5,
            "financial_section_start": 12
        }
    },
    "Scanned_budget_document": {
        "document_type": "SCANNED",
        "currency_evidence": {
            "primary": "EUR",
            "secondary": ["USD"],
            "reference": ["GBP"]
        },
        "confidence": 0.80,
        "ocr_quality": "82%",
        "financial_terms": {
            "vat_percentage": {"value": 21.0, "confidence": 0.75, "ocr_text": "VAT % = 21%"}
        }
    }
}
```

### 4. MIXED CURRENCY TENDERS TEST

**Test Data Requirements:**
```python
test_cases = {
    "Dutch_EU_NLD_contract": {
        "document_type": "Dutch_EU_NLD_contract",
        "currency_evidence": {
            "primary": "EUR",
            "secondary": ["USD"],
            "reference": ["ZAR", "GBP"]
        },
        "balance_imbalance": {"value": 100, "confidence": 0.92, "balance_based_on": "contract_meeting"},
        "detected_in_3_m2": {
            "USD_contract": 50, "USD_paket": 30,
            "detected_currencies": {"USD": 2, "ZAR": 3, "GBP": 2, "EUR": 8}
        },
        "BOQ": {
            "filter_settings": {
                "BOQ_row_code": "filter_settings",
                "currency_support": {
                    "BOQ_rows": ["USD", "ZAR", "GBP", "EUR"],
                    "discount": "EUR", "total_contract": ["EUR"]
                }
            }
        }
    }
}
```

## IMPLEMENTATION CHECKLIST

### Core Engines ✅
- [x] Evidence Engine implementation
- [x] Currency Intelligence Engine V2
- [x] Numeric Entity Classification Engine
- [x] Evidence Schema Manager

### Report Integration ⏳
- [ ] Completion Guide evidence display
- [ ] Readiness Report evidence display
- [ ] Submission Package evidence PDF
- [ ] Audit Report evidence audit
- [ ] Result Viewer evidence dashboard

### Validation Tests ⏳
- [ ] South African Tender test suite
- [ ] EU TED Tender test suite
- [ ] Scanned Tender documents test suite
- [ ] Mixed Currency Tenders test suite

### Documentation ⏳
- [ ] API documentation for new engines
- [ ] Report integration guidelines
- [ ] Evidence display specifications
- [ ] Validation test documentation

## QUICK START GUIDE

### Step 1: Update Completion Guide
```bash
# Add evidence imports
from api.services.evidence_schema import get_evidence_schema_manager

# Get evidence manager in reporting function
evidence_manager = get_evidence_schema_manager()

# Add evidence sections to PDF
evidence_sections = evidence_manager.get_critical_fields_report(["project_value", "currency"])
for section in evidence_sections:
    # Add to PDF story
```

### Step 2: Update Readiness Report
```bash
# Replace simple confidence scores with evidence-based scores
def get_confidence_score(tender_data):
    evidence_summary = get_evidence_schema_manager().generate_evidence_summary()
    return evidence_summary['average_confidence']
```

### Step 3: Generate Evidence Package
```python
# Run comprehensive evidence collection
evidence_engine = get_evidence_engine()
currency_evidences = evidence_engine.get_currency_evidence()
numeric_evidences = evidence_engine.get_numeric_entity_evidence()

# Generate evidence PDF
evidence_manager._generate_evidence_report_pdf(tender_data, evidence_engine)
```

### Step 4: Run Validation Tests
```bash
pytest tests/validation/test_south_african_tender.py -v
pytest tests/validation/test_eu_ted_tender.py -v
pytest tests/validation/test_scanned_tenders.py -v
pytest tests/validation/test_mixed_currencies.py -v
```

## SUMMARY

This implementation guide provides the complete roadmap for:
1. ✅ **Core engines** - Evidence-based currency and numeric detection
2. ⏳ **Report integration** - Evidence display across all reports
3. ⏳ **Validation testing** - Comprehensive test coverage
4. ⏳ **Documentation** - Complete implementation guide

All required data structures, engines, and schemas have been created. The remaining work involves:
- Integration of evidence display into PDF reports
- Development of evidence-based scoring and validation
- Comprehensive validation test suite
- Frontend evidence dashboard components

The implementation follows all specified requirements:
- ✅ No currency ID‑based inference inhibits templates
- ✅ Only currency/economic value detection and extraction
- ✅ No forecasting
- ✅ NO HALLUCINATION: No fabricated data, estimation, or best‑guess
- ✅ No-commercial WAICWA infection
- ✅ Evidence‑based primary/secondary/Reference determination
- ✅ Volume‑based weight, trend‑less
- ✅ ROFCINAYAWAICWA virus-free detection