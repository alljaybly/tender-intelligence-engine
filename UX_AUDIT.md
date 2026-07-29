# Tender Engine — Truth in Labeling Audit

**Date:** 2026-07-12  
**Scope:** All user-facing text, README, locale files, component labels, feature names, tooltips, button labels, disclaimers, and backend service docstrings.  
**Goal:** Reposition product as a **deterministic, evidence-based tender document processor** — removing all AI-magic, hallucination, prediction, or synthetic intelligence language.

---

## 1. Summary of Changes Needed

| Category | Count |
|----------|-------|
| Files requiring text changes | 14 |
| Phrases containing "AI" that must be removed/rewritten | ~25 |
| Features to rename | 2 |
| Features to cut (NON-DETERMINISTIC) | 1 |
| Features to downgrade | 1 |

---

## 2. Exact Text Replacements

### 2.1 README.md

| Line(s) | Current Text | Recommended Replacement |
|---------|-------------|------------------------|
| 1 | `# Tender Engine AI` | `# Tender Engine` |
| 4 | `Tender Engine AI is a forensic compliance engine` | `Tender Engine is a deterministic forensic compliance engine` |
| 13 | `All AI-generated outputs include a disclaimer: "This document is AI-generated. Verify all details before submission."` | `All generated outputs include a disclaimer: "This document is system-generated from extracted data. Verify all details before submission."` |
| 44 | `Footer includes the mandatory disclaimer: "This document is AI-generated. Verify all details before submission."` | `Footer includes the mandatory disclaimer: "This document is system-generated from extracted data. Verify all details before submission."` |
| 13 | (general) Replace all "AI-generated" references | "system-generated", "deterministically generated", "extracted from source documents" |

### 2.2 tender-engine-frontend/src/locales/en/common.json

| Key | Current Text | Recommended Replacement |
|-----|-------------|------------------------|
| `app.name` | `Tender Engine` | `Tender Engine` (keep — name is fine) |
| `app.tagline` | `AI tender extraction for Africa` | `Deterministic tender document processing for Africa` |
| `app.tagline_long` | `AI-generated tender insights with visible confidence scoring, warnings, and transparent processing results.` | `Evidence-based tender document processing with visible extraction certainty, warnings, and transparent processing results.` |
| `warnings.generated_from_extraction` | `Generated from verified document extraction. Manual verification required before submission.` | (Keep — already good) |
| `confidence.scores_reflect_model` | `Confidence scores reflect model certainty, not factual correctness. Always review AI-generated outputs before use.` | `Extraction certainty reflects match quality against known patterns, not factual correctness. Always review outputs before use.` |

### 2.3 tender-engine-frontend/src/locales/en/landing.json

| Key | Current Text | Recommended Replacement |
|-----|-------------|------------------------|
| `hero_title` | `AI-Powered Tender Extraction for Africa` | `Deterministic Tender Document Processing for Africa` |
| `hero_subtitle` | `Extract, analyse, and review tender documents with transparent AI. See confidence scores, warnings, and extraction results — all in one dashboard.` | `Extract, analyse, and review tender documents with deterministic, evidence-based processing. See extraction certainty, warnings, and extraction results — all in one dashboard.` |

### 2.4 tender-engine-frontend/src/locales/en/demo.json

| Key | Current Text | Recommended Replacement |
|-----|-------------|------------------------|
| `hero_title` | `See exactly what Tender Engine would extract from a tender PDF.` | (Keep — good) |
| `executive_summary_desc` | `A concise, review-ready interpretation of the extracted tender.` | (Keep — good) |
| `review_signals_desc` | `Tender Engine should be useful even when it is cautious. These flags stay visible for human review.` | (Keep — good) |

### 2.5 PublicHeader.tsx

| Line | Current Text | Recommended Replacement |
|------|-------------|------------------------|
| 56 | `AI tender extraction for Africa` | `Deterministic tender document processing` |

### 2.6 AppFooter.tsx

| Line | Current Text | Recommended Replacement |
|------|-------------|------------------------|
| 16 | `Professional Tender Processing Software` | (Keep — fine) |
| 20 | `AI-generated tender insights with visible confidence scoring, warnings, and transparent processing results.` | `Evidence-based tender document processing with extraction certainty scores, warnings, and transparent processing results.` |

### 2.7 ForProcurement.tsx

| Line(s) | Current Text | Recommended Replacement |
|---------|-------------|------------------------|
| 67 (step 2 title) | `AI Analysis & Health Check` | `Document Analysis & Health Check` |
| 72 (step 2 desc) | `Our engine extracts and analyzes every section — BOQ items, specifications, pricing, schedules, and workforce requirements.` | (Remove "AI", just "Our engine extracts...") |
| 104-105 | `Our AI analyzes it and flags ambiguous BOQ items` | `Our system analyzes it and flags ambiguous BOQ items` |
| 143 | `From draft to published — add an AI quality check before your tender goes to market.` | `From draft to published — add a deterministic compliance check before your tender goes to market.` |
| 163 | `Why Use AI for Tender Quality Assurance?` | `Why Use Document Analysis for Quality Assurance?` |
| 192 | `Our AI tender analysis is designed` | `Our document analysis is designed` |

### 2.8 LandingPage.tsx

| Line | Current Text | Recommended Replacement |
|------|-------------|------------------------|
| 67 | `From draft to published — add an AI quality check before your tender goes to market.` | (Mirrors ForProcurement.tsx changes) |

### 2.9 ResultViewer.tsx

| Line | Current Text | Recommended Replacement |
|------|-------------|------------------------|
| 698 | `result?.win_probability_index` (entire block) | **CUT** — non-deterministic predictive metric |
| 873 | `Confidence scores reflect model certainty, not factual correctness. Always review AI-generated outputs before use.` | `Extraction certainty reflects match quality. Always review outputs before use.` |

### 2.10 HeroSection.tsx

| Line | Current Text | Recommended Replacement |
|------|-------------|------------------------|
| 25 | `Turn tender PDFs into priced BOQs you can trust, not guess from.` | (Keep — excellent positioning) |

### 2.11 FeatureGrid.tsx

| Feature | Current Description | Recommended Replacement |
|---------|-------------------|------------------------|
| Workforce Estimation | `Identify skill categories, personnel counts, and inferred roles that affect delivery planning.` | Change `inferred roles` → `extracted role categories` |
| Pricing Intelligence | (Feature name) | Rename to `Pricing Calculation` |
| Confidence Scoring | `See how reliable each extraction stage is before you rely on the result.` | Change to `See how reliably each extraction stage matched its source data before you rely on the result.` |

---

## 3. Features to Rename

| Current Name | Recommended Name | Reason |
|-------------|-----------------|--------|
| `Pricing Intelligence` | `Pricing Calculation` | "Intelligence" implies AI/ML magic. The pricing is a deterministic arithmetic calculation with defined rules (VAT, contingency %, escalation %). |
| `Confidence Score` (in some contexts) | `Extraction Certainty` (preferred) or keep as `Confidence Score` but clarify it's deterministic | "Confidence" can imply subjective AI certainty. If the score is deterministic (derived from pattern-match quality), rename to `Extraction Certainty`. If it's genuinely based on deterministic rules, `Match Certainty` is more honest. |

---

## 4. Features to Cut (NON-DETERMINISTIC)

### 4.1 Win Probability Index — **CUT IMMEDIATELY**

**Violation:** Calculates a "win probability" for the tender — this is a fabricated/ predictive metric with no deterministic basis.

**Found in:**
- `tender-engine-frontend/src/components/ResultViewer.tsx` lines 698-707
- Backend processing result schema

**Reasoning:**
- Tender Engine's philosophy: *Never guess. Never fabricate. Never invent missing values.*
- A "Win Probability Index" is inherently a guess/prediction about external outcomes the system cannot know
- It has no evidence source — it cannot cite which document field produced this number
- It encourages exactly the kind of blind trust the Honesty Architecture is built to prevent

**Action:** Remove the `win_probability_index` field from:
1. `ResultViewer.tsx` (UI rendering)
2. `types/process.ts` (TypeScript types)
3. Backend result schema (wherever it's set)
4. Any tests that assert on it

### 4.2 "inferred roles" in Workforce Estimation — **DOWNGRADE**

**Current:** `Identify skill categories, personnel counts, and inferred roles that affect delivery planning.`

**Problem:** "Inferred" means guessed — the system is fabricating role categories it didn't find evidence for.

**Fix:** Remove "inferred" entirely. Only report roles that were explicitly extracted from the document. Change to: `Identify skill categories and personnel counts extracted from the document.`

---

## 5. Remaining Concerns (Potentially Misleading)

| Item | Issue | Recommendation |
|------|-------|---------------|
| `Confidence Score` label throughout UI | Users may interpret this as "this is how likely the answer is right" rather than "this is how well the pattern matched" | Add tooltip: *"Extraction certainty is derived from pattern-match quality against known tender formats. It is not a prediction of correctness."* |
| `Executive Summary` in demo/result | "Executive Summary" could be read as AI-generated narrative. If it's a template-based aggregation of extracted fields, this is fine. If it's LLM-generated, it must be flagged as requiring review. | Verify what generates the executive summary. If template-based, keep. If ML-generated, add: *"Summarised from extracted fields. Verify all details."* |
| `Smart field auto-population` in README | "Smart" is vague marketing language | Replace with `Deterministic field extraction with cascading fallbacks` |
| `Intelligent Submission Letter Generation` in README | "Intelligent" implies AI | Replace with `Submission Letter Generation` |
| `Pricing Intelligence` (FeatureGrid) | Already flagged for rename above | |

---

## 6. Final Positioning Statement

```
Tender Engine is a deterministic, evidence-based tender document processor.

It extracts, analyses, and validates information from South African tender
documents using rule-based extraction, pattern matching, and deterministic
business rules. Every value has a traceable source. Every calculation is
explainable. Every output warns which fields require manual verification.

Tender Engine does not guess. It does not fabricate. It does not invent
missing values. Unknown is better than incorrect.
```

This statement should appear:
1. In the README.md (replacing current description)
2. In the `app.description` locale key (replacing `Professional Tender Processing Software`)
3. As a footer tagline on the landing page
4. In the site meta description

---

## 7. Summary of Files Changed

| # | File | Changes Required |
|---|------|-----------------|
| 1 | `README.md` | Title, descriptions, all "AI-generated" references, disclaimers |
| 2 | `tender-engine-frontend/src/locales/en/common.json` | tagline, tagline_long, confidence.scores_reflect_model |
| 3 | `tender-engine-frontend/src/locales/en/landing.json` | hero_title, hero_subtitle |
| 4 | `tender-engine-frontend/src/locales/en/dashboard.json` | (minor review — probably clean) |
| 5 | `tender-engine-frontend/src/locales/en/demo.json` | (mostly clean, check hero_title) |
| 6 | `tender-engine-frontend/src/components/layout/PublicHeader.tsx` | Line 56 tagline |
| 7 | `tender-engine-frontend/src/components/layout/AppFooter.tsx` | Line 20 description |
| 8 | `tender-engine-frontend/src/components/landing/HeroSection.tsx` | (mostly clean) |
| 9 | `tender-engine-frontend/src/components/landing/FeatureGrid.tsx` | "Pricing Intelligence" rename, "inferred roles" fix |
| 10 | `tender-engine-frontend/src/components/ResultViewer.tsx` | Remove Win Probability Index, fix confidence tooltip |
| 11 | `tender-engine-frontend/src/pages/ForProcurement.tsx` | Multiple "AI" references |
| 12 | `tender-engine-frontend/src/pages/LandingPage.tsx` | Inherits locale strings |
| 13 | `tender-engine-frontend/src/pages/DemoPage.tsx` | (mostly clean — check for AI references) |
| 14 | `api/services/extraction_service.py` | (already clean — keep as-is) |
| 15 | `api/services/submission_letter_service.py` | (already clean — keep as-is) |

---

## 8. Enforcement Checklist

Before shipping, verify:

- [ ] No use of "AI", "artificial intelligence", "machine learning", "smart", "intelligent" in user-facing text
- [ ] All "confidence score" references are renamed to "extraction certainty" or have clarifying tooltips
- [ ] Win Probability Index is fully removed (frontend + backend + types + tests)
- [ ] Every extractable value has a documented evidence source
- [ ] Every calculated value documents how it was derived
- [ ] Every report indicates which fields require manual verification
- [ ] Footer disclaimer says "system-generated from extracted data" not "AI-generated"
- [ ] README uses the Final Positioning Statement
- [ ] No predictive, probabilistic, or hallucinatory language remains