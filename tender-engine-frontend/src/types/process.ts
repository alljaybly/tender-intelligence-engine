/**
 * TypeScript types matching the backend process schemas exactly.
 *
 * Backend reference: api/schemas/process.py
 */
export interface ProcessUploadResponse {
  job_id: string;
  status: string;
  filename: string;
  message: string;
}

export type JobStatusValue =
  | 'queued'
  | 'processing'
  | 'extracting'
  | 'boq_analysis'
  | 'pricing'
  | 'completed'
  | 'partial_success'
  | 'failed';

export interface ProcessingJobStatus {
  job_id: string;
  status: JobStatusValue;
  progress: string | null;
  created_at: string | null;
  updated_at: string | null;
  error_message: string | null;
}

export interface ExtractedBOQItem {
  item_no: string | null;
  description: string;
  quantity: number | null;
  unit: string | null;
  rate: number | null;
  amount: number | null;
}

export interface WorkforceData {
  [key: string]: unknown;
}

export interface ScheduleData {
  [key: string]: unknown;
}

export type ResultStatus = 'completed' | 'partial_success' | 'failed';

/**
 * Currency Evidence — deterministic currency detection result.
 * 
 * Every currency detection produces a CurrencyEvidence object.
 * Currency is NEVER defaulted. Unknown is better than incorrect.
 * 
 * Backend reference: api/schemas/currency.py :: CurrencyEvidence
 */
export interface CurrencyEvidence {
  currency_code: string | null;       // ISO 4217 code (e.g. "ZAR", "USD")
  currency_name: string | null;       // Human-readable name (e.g. "South African Rand")
  currency_symbol: string | null;     // Symbol (e.g. "R", "$", "€")
  confidence: number;                 // 0.0 (none) to 1.0 (certain)
  detection_method: string;           // "iso_code_with_amount", "symbol_with_amount", "explicit_wording", "country_detection", "procurement_portal", "iso_code_only", "symbol_only", "jurisdiction", "none"
  evidence: string[];                 // Human-readable evidence strings
  source_pages: number[];             // Page numbers where evidence found
  source_text: string[];              // Text snippets containing evidence
  reason: string;                     // Plain English explanation
  is_detected: boolean;               // True only if confidence >= threshold
}

export interface ProcessingResult {
  job_id: string;
  status: ResultStatus;
  filename: string | null;

  /** Stage tracking (present for completed and partial_success) */
  completed_stages: string[];
  failed_stages: string[];

  /** Stage 1: Metadata */
  metadata: Record<string, unknown>;

  /** Stage 2: Document text */
  full_text: string | null;
  text_length: number | null;

  /** Stage 3: Extracted entities */
  detected_sector: string | null;
  detected_duration_months: number | null;
  detected_locations: string[];
  detected_workforce: Record<string, unknown>;
  detected_schedule: Record<string, unknown>;
  detected_currency: CurrencyEvidence | null;

  /** Stage 4: BOQ items */
  boq_items: ExtractedBOQItem[];
  boq_confidence: string | null;

  /** Stage 5: Pricing */
  pricing_result: Record<string, unknown> | null;
  pricing_status: string | null;
  pricing_unavailable_reason: string | null;

  /** Forensic Compliance Engine Features */
  win_probability_index: number | null;
  win_probability_explanation: string | null;
  critical_traps: string[];
  compliance_gaps: string[];

  /** Stage 6: Final combined output */
  warnings: string[];
  extraction_method: string | null;
  pipeline_version: string | null;
}

/**
 * Lightweight history summary returned by GET /api/process/history.
 *
 * Backend reference: api/schemas/process.py :: ProcessingHistoryItem
 *
 * This is the BACKEND-AUTHORITATIVE source of truth for the user's job history.
 * The frontend does NOT cache full results here — only lightweight summary fields
 * that are safe to display without fetching the full result payload.
 */
export interface ProcessingHistoryItem {
  job_id: string;
  filename: string | null;
  status: string;
  created_at: string | null;
  updated_at: string | null;
  sector: string | null;
  confidence: string | null;
  warnings_count: number;
  has_pricing: boolean;
  error_message: string | null;
}

/** Statuses that indicate a job has finished processing. */
export const TERMINAL_STATUSES: readonly JobStatusValue[] = [
  'completed',
  'partial_success',
  'failed',
];

/** Mapping from status to human-readable label. */
export const STATUS_LABELS: Record<JobStatusValue, string> = {
  queued: 'Queued',
  processing: 'Processing',
  extracting: 'Extracting',
  boq_analysis: 'BOQ Analysis',
  pricing: 'Pricing',
  completed: 'Completed',
  partial_success: 'Partial Success',
  failed: 'Failed',
};

/**
 * Request body for POST /api/process/retry/{job_id}.
 */
export interface RetryRequest {
  stages: string[];
}

/**
 * Response from a retry operation.
 */
export interface RetryResponse {
  job_id: string;
  status: string;
  retry_count: number;
  retried_stages: string[];
  last_retry_at: string | null;
  stage_failures: Array<{
    stage: string;
    reason: string;
    recoverable: boolean;
    retryable: boolean;
    description: string;
  }>;
}

/**
 * Tender Readiness Report types.
 * Matches the backend response from api/services/tender_readiness_service.py
 */
export interface ReadinessScoreCategory {
  score: number;
  weight: number;
  label: string;
}

export interface ReadinessScoreData {
  overall_score: number;
  label: string;
  label_description: string;
  categories: Record<string, ReadinessScoreCategory>;
  breakdown: Record<string, number>;
}

export interface MissingField {
  field: string;
  label: string;
  severity: string;
  reason: string;
}

export interface MissingInformation {
  count: number;
  total_required: number;
  completeness_percentage: number;
  missing_fields: MissingField[];
  summary: string;
}

export interface MissingDocument {
  id: string;
  name: string;
  status: string;
  severity?: string;
}

export interface MissingDocumentsData {
  total_required: number;
  detected_count: number;
  missing_count: number;
  detected: MissingDocument[];
  missing: MissingDocument[];
  summary: string;
}

export interface ConfidenceBreakdown {
  extraction: number;
  boq: number;
  pricing: number;
  ocr_penalty: number;
  missing_penalty: number;
}

export interface ConfidenceLevels {
  extraction: string;
  boq: string;
  pricing: string;
}

export interface ConfidenceSummary {
  overall_score: number;
  label: string;
  summary_text: string;
  breakdown: ConfidenceBreakdown;
  levels: ConfidenceLevels;
}

export interface RiskItem {
  category: string;
  severity: string;
  title: string;
  description: string;
  actionable: boolean;
}

export interface RiskSummary {
  overall_risk_level: string;
  overall_assessment: string;
  risk_count: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  risks: RiskItem[];
}

export interface Recommendation {
  priority: string;
  category: string;
  title: string;
  message: string;
  action: string;
}

export interface DashboardPayload {
  readiness_score: number;
  readiness_label: string;
  risk_level: string;
  risk_count: number;
  missing_fields_count: number;
  missing_documents_count: number;
  confidence_label: string;
  status: string;
  has_pricing: boolean;
  has_boq: boolean;
  has_workforce: boolean;
}

export interface TenderReadinessReport {
  job_id: string;
  filename: string;
  status: string;
  generated_at: string;
  readiness_score: ReadinessScoreData;
  missing_information: MissingInformation;
  missing_documents: MissingDocumentsData;
  confidence_summary: ConfidenceSummary;
  risk_summary: RiskSummary;
  recommendations: Recommendation[];
  dashboard: DashboardPayload;
  raw: {
    extraction_method: string | null;
    pipeline_version: string | null;
    text_length: number;
  };
}

/**
 * Request body for POST /api/process/export/package/{job_id}
 * and POST /api/process/export/package-zip/{job_id}
 */
export interface SubmissionPackageRequest {
  company_name?: string;
  company_address?: string;
}

/** Allowed file types for upload. */
export const ALLOWED_FILE_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain',
] as const;

export const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.txt'] as const;

export const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB

/**
 * Processing Audit Log types.
 * 
 * The audit log is a permanent transparency record of every processing stage.
 * Failures NEVER disappear - they are recorded with explicit reasons.
 */
export interface AuditStage {
  stage: string;
  status: 'success' | 'warning' | 'failed';
  timestamp: string | null;
  duration_ms: number | null;
  confidence: string | null;
  source_module: string | null;
  warnings: string[];
  errors: string[];
  details: string | null;
}

export interface AuditSummary {
  tender_id: string;
  total_stages: number;
  successful: number;
  warnings: number;
  failed: number;
  total_duration_ms: number;
  stages: AuditStage[];
}

/** Human-readable labels for audit stages */
export const AUDIT_STAGE_LABELS: Record<string, string> = {
  upload_received: 'Upload Received',
  pdf_fingerprint: 'PDF Fingerprint Calculated',
  ocr_completed: 'OCR Completed',
  document_classification: 'Document Classification',
  jurisdiction_detection: 'Jurisdiction Detected',
  language_detection: 'Language Detected',
  currency_detection: 'Currency Detected',
  numeric_entity_classification: 'Numeric Entity Classification',
  tender_metadata_extraction: 'Tender Metadata Extracted',
  boq_extraction: 'BOQ Extraction',
  pricing_completed: 'Pricing Completed',
  workforce_estimation: 'Workforce Estimation',
  schedule_extraction: 'Schedule Extraction',
  submission_letter_generation: 'Submission Letter Generated',
  readiness_assessment: 'Readiness Assessment',
  audit_report_generation: 'Audit Report Generated',
  result_committed: 'Result Committed to Database',
  processing_complete: 'Processing Complete',
};