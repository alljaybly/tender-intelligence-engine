import api, { ApiRequestError } from './api';

export interface AnalyticsSummary {
  total_tenders_processed: number;
  successful_jobs: number;
  failed_jobs: number;
  partial_success_jobs: number;
  average_processing_time_ms: number | null;
  average_readiness_score: number | null;
  ocr_usage_percent: number | null;
  digital_pdf_percent: number | null;
  average_boq_items: number | null;
}

export interface AnalyticsDashboardResponse {
  summary: AnalyticsSummary;
  most_common_currencies: Array<[string, number]>;
  most_common_jurisdictions: Array<[string, number]>;
  most_common_procurement_methods: Array<[string, number]>;
  most_common_industries: Array<[string, number]>;
  most_common_missing_documents: Array<[string, number]>;
  most_common_warnings: Array<[string, number]>;
  most_common_failures: Array<[string, number]>;
  average_confidence_by_field: Record<string, number>;
}

export interface ExtractionScorecardResponse {
  total_completed_jobs: number;
  metrics: Record<string, number>;
}

export interface PerformanceResponse {
  average_upload_time_ms: number | null;
  average_validation_time_ms: number | null;
  average_ocr_duration_ms: number | null;
  average_text_extraction_duration_ms: number | null;
  average_entity_extraction_duration_ms: number | null;
  average_boq_duration_ms: number | null;
  average_pricing_duration_ms: number | null;
  average_report_generation_duration_ms: number | null;
  average_zip_package_generation_duration_ms: number | null;
  average_total_processing_time_ms: number | null;
  average_page_processing_time_ms: number | null;
}

export interface TrendsResponse {
  range_days: number;
  daily: Array<{
    date: string;
    processed: number;
    completed: number;
    failed: number;
    avg_readiness_score: number | null;
    avg_processing_time_ms: number | null;
  }>;
}

export async function getAnalyticsSummary(days = 30): Promise<AnalyticsSummary> {
  return api.get<AnalyticsSummary>(`/api/analytics/summary?days=${days}`);
}

export async function getAnalyticsDashboard(days = 30): Promise<AnalyticsDashboardResponse> {
  return api.get<AnalyticsDashboardResponse>(`/api/analytics/dashboard?days=${days}`);
}

export async function getExtractionScorecard(days = 30): Promise<ExtractionScorecardResponse> {
  return api.get<ExtractionScorecardResponse>(`/api/analytics/extraction-scorecard?days=${days}`);
}

export async function getPerformance(days = 30): Promise<PerformanceResponse> {
  return api.get<PerformanceResponse>(`/api/analytics/performance?days=${days}`);
}

export async function getTrends(days = 365): Promise<TrendsResponse> {
  return api.get<TrendsResponse>(`/api/analytics/trends?days=${days}`);
}

export async function downloadAnalyticsCsv(days = 30): Promise<void> {
  const base = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
  const response = await fetch(`${base}/api/analytics/export/csv?days=${days}`);
  if (!response.ok) {
    throw new ApiRequestError('Failed to export analytics CSV', response.status, 'export_failed');
  }
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `platform_analytics_${days}d.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
