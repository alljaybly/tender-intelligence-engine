/**
 * Report Translation Keys
 *
 * This file maps all report section titles and headings to translation keys.
 * It serves as a reference for future translation work on report generators.
 *
 * When translations are added for reports, use these keys with the t() function
 * instead of hardcoded strings in report generation code.
 *
 * Current state: All reports generate English output.
 * These keys are prepared so that switching to translated output requires
 * only changing the key lookup, not the report generation logic.
 */

/**
 * PDF Report (pdf_report_service.py)
 * Section headings and labels used in the generated PDF.
 */
export const PDF_REPORT_KEYS = {
  /** Report title on cover page */
  title: 'report.pdf.title', // "TENDER PROCESSING REPORT"
  /** Confidential disclaimer */
  disclaimer: 'report.pdf.disclaimer',
  /** Section 1 heading */
  section_1: 'report.pdf.section_1', // "1. Executive Summary"
  /** Section 2 heading */
  section_2: 'report.pdf.section_2', // "2. Key Insights"
  /** Section 3 heading */
  section_3: 'report.pdf.section_3', // "3. Pricing Summary"
  /** Section 4 heading */
  section_4: 'report.pdf.section_4', // "4. Workforce Summary"
  /** Section 5 heading */
  section_5: 'report.pdf.section_5', // "5. Risks & Warnings",
  /** Footer generation text */
  footer_generated: 'report.pdf.footer_generated',
  /** Footer disclaimer */
  footer_disclaimer: 'report.pdf.footer_disclaimer',

  // Cover page labels
  cover_job_id: 'report.pdf.cover.job_id',
  cover_sector: 'report.pdf.cover.sector',
  cover_location: 'report.pdf.cover.location',
  cover_date: 'report.pdf.cover.date',
  cover_pipeline: 'report.pdf.cover.pipeline',
  cover_status: 'report.pdf.cover.status',

  // Executive summary labels
  exec_processing_status: 'report.pdf.exec.processing_status',
  exec_total_value: 'report.pdf.exec.total_value',
  exec_duration: 'report.pdf.exec.duration',
  exec_workforce: 'report.pdf.exec.workforce',
  exec_pricing_confidence: 'report.pdf.exec.pricing_confidence',
  exec_sector: 'report.pdf.exec.sector',
  exec_boq_items: 'report.pdf.exec.boq_items',
  exec_confidence_score: 'report.pdf.exec.confidence_score',

  // Key insights labels
  insights_boq_items: 'report.pdf.insights.boq_items',
  insights_boq_confidence: 'report.pdf.insights.boq_confidence',
  insights_extraction_method: 'report.pdf.insights.extraction_method',
  insights_ocr_used: 'report.pdf.insights.ocr_used',
  insights_text_length: 'report.pdf.insights.text_length',
  insights_work_categories: 'report.pdf.insights.work_categories',
  insights_data_gaps: 'report.pdf.insights.data_gaps',

  // Pricing labels
  pricing_unavailable: 'report.pdf.pricing.unavailable',
  pricing_component: 'report.pdf.pricing.component',
  pricing_amount: 'report.pdf.pricing.amount',
  pricing_method: 'report.pdf.pricing.method',
  pricing_confidence: 'report.pdf.pricing.confidence',

  // Workforce labels
  workforce_not_available: 'report.pdf.workforce.not_available',
  workforce_category: 'report.pdf.workforce.category',
  workforce_value: 'report.pdf.workforce.value',
  workforce_confidence: 'report.pdf.workforce.confidence',

  // Risks labels
  risks_failed_stages: 'report.pdf.risks.failed_stages',
  risks_warnings: 'report.pdf.risks.warnings',
  risks_missing_boq: 'report.pdf.risks.missing_boq',
  risks_ocr_fallback: 'report.pdf.risks.ocr_fallback',
  risks_retry_info: 'report.pdf.risks.retry_info',
  risks_no_issues: 'report.pdf.risks.no_issues',
} as const;

/**
 * Submission Letter (submission_letter_service.py)
 */
export const SUBMISSION_LETTER_KEYS = {
  title: 'report.submission_letter.title',
  date: 'report.submission_letter.date',
  to: 'report.submission_letter.to',
  subject: 'report.submission_letter.subject',
  body_intro: 'report.submission_letter.body_intro',
  body_pricing: 'report.submission_letter.body_pricing',
  body_compliance: 'report.submission_letter.body_compliance',
  body_closing: 'report.submission_letter.body_closing',
  signature: 'report.submission_letter.signature',
} as const;

/**
 * Tender Readiness Assessment (tender_readiness_service.py)
 */
export const READINESS_KEYS = {
  title: 'report.readiness.title',
  section_score: 'report.readiness.section.score',
  section_missing_info: 'report.readiness.section.missing_info',
  section_missing_docs: 'report.readiness.section.missing_docs',
  section_risks: 'report.readiness.section.risks',
  section_recommendations: 'report.readiness.section.recommendations',
  label_readiness_score: 'report.readiness.label.readiness_score',
  label_overall_status: 'report.readiness.label.overall_status',
  label_confidence: 'report.readiness.label.confidence',
  label_risk_level: 'report.readiness.label.risk_level',
} as const;

/**
 * Pricing Report (pricing_service.py)
 */
export const PRICING_REPORT_KEYS = {
  title: 'report.pricing.title',
  section_breakdown: 'report.pricing.section.breakdown',
  section_summary: 'report.pricing.section.summary',
  section_assumptions: 'report.pricing.section.assumptions',
  label_total: 'report.pricing.label.total',
  label_subtotal: 'report.pricing.label.subtotal',
  label_vat: 'report.pricing.label.vat',
  label_contingency: 'report.pricing.label.contingency',
  label_escalation: 'report.pricing.label.escalation',
  label_professional_fees: 'report.pricing.label.professional_fees',
} as const;

/**
 * Compliance Report
 */
export const COMPLIANCE_REPORT_KEYS = {
  title: 'report.compliance.title',
  section_gaps: 'report.compliance.section.gaps',
  section_requirements: 'report.compliance.section.requirements',
  section_status: 'report.compliance.section.status',
  label_compliant: 'report.compliance.label.compliant',
  label_non_compliant: 'report.compliance.label.non_compliant',
  label_partial: 'report.compliance.label.partial',
} as const;

/**
 * Executive Summary
 */
export const EXECUTIVE_SUMMARY_KEYS = {
  title: 'report.executive_summary.title',
  section_overview: 'report.executive_summary.section.overview',
  section_key_findings: 'report.executive_summary.section.key_findings',
  section_recommendations: 'report.executive_summary.section.recommendations',
} as const;

/**
 * All report translation keys combined.
 * Use this to ensure all keys are covered when adding translations.
 */
export const ALL_REPORT_KEYS = {
  ...PDF_REPORT_KEYS,
  ...SUBMISSION_LETTER_KEYS,
  ...READINESS_KEYS,
  ...PRICING_REPORT_KEYS,
  ...COMPLIANCE_REPORT_KEYS,
  ...EXECUTIVE_SUMMARY_KEYS,
} as const;

export type ReportKey = keyof typeof ALL_REPORT_KEYS;