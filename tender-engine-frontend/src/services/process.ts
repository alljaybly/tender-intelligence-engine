/**
 * API service layer for tender upload and processing pipeline.
 *
 * Backend reference: api/routes/process.py
 *
 * Endpoints:
 *   POST /api/process/upload        — Upload tender document
 *   GET  /api/process/status/{id}   — Poll job status
 *   GET  /api/process/result/{id}   — Retrieve processing result
 *   GET  /api/process/history       — Retrieve user's processing history
 *
 * Backend is ALWAYS the source of truth.
 * The frontend NEVER caches status or result data.
 * localStorage is ONLY used for job ID persistence (see jobRegistry.ts).
 */
import { ApiRequestError, getStoredToken } from './api';
import type {
  ProcessUploadResponse,
  ProcessingJobStatus,
  ProcessingResult,
  ProcessingHistoryItem,
  RetryResponse,
  TenderReadinessReport,
} from '../types/process';

const API_BASE =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * Get auth headers for multipart/form-data uploads.
 * The standard `api.ts` client injects JSON Content-Type, which is
 * incompatible with multipart uploads, so we build the request manually.
 */
function getAuthHeaders(): Record<string, string> {
  const token = getStoredToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

/**
 * Upload a tender document for processing.
 *
 * Uses real multipart/form-data upload with Authorization header.
 * Throws ApiRequestError on failure.
 */
export async function uploadTender(
  file: File,
  onProgress?: (percent: number) => void,
): Promise<ProcessUploadResponse> {
  const url = `${API_BASE}/api/process/upload`;

  const formData = new FormData();
  formData.append('file', file);

  return new Promise<ProcessUploadResponse>((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    // Track upload progress
    if (onProgress) {
      xhr.upload.addEventListener('progress', (event: ProgressEvent) => {
        if (event.lengthComputable) {
          const percent = Math.round((event.loaded / event.total) * 100);
          onProgress(percent);
        }
      });
    }

    xhr.addEventListener('load', () => {
      try {
        const body = JSON.parse(xhr.responseText);

        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(body as ProcessUploadResponse);
        } else {
          const detail =
            body?.detail || `Upload failed with status ${xhr.status}`;
          let code = 'upload_failed';
          if (xhr.status === 401) code = 'unauthorized';
          else if (xhr.status === 413) code = 'file_too_large';
          else if (xhr.status === 422) code = 'validation_error';
          else if (xhr.status === 409) code = 'conflict';
          reject(new ApiRequestError(detail, xhr.status, code));
        }
      } catch {
        reject(
          new ApiRequestError(
            'Failed to parse upload response',
            xhr.status,
            'parse_error',
          ),
        );
      }
    });

    xhr.addEventListener('error', () => {
      reject(
        new ApiRequestError(
          'Network error during upload. Please check your connection.',
          0,
          'network_error',
        ),
      );
    });

    xhr.addEventListener('abort', () => {
      reject(
        new ApiRequestError('Upload was cancelled', 0, 'upload_cancelled'),
      );
    });

    xhr.open('POST', url);
    // Set auth headers
    const authHeaders = getAuthHeaders();
    for (const [key, value] of Object.entries(authHeaders)) {
      xhr.setRequestHeader(key, value);
    }
    // Do NOT set Content-Type — the browser sets it automatically
    // with the correct multipart boundary for FormData
    xhr.send(formData);
  });
}

/**
 * Poll the status of a processing job.
 *
 * GET /api/process/status/{job_id}
 */
export async function getJobStatus(
  jobId: string,
): Promise<ProcessingJobStatus> {
  const url = `${API_BASE}/api/process/status/${encodeURIComponent(jobId)}`;

  const token = getStoredToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(url, { method: 'GET', headers });
  } catch {
    throw new ApiRequestError(
      'Network error. Cannot reach backend server.',
      0,
      'network_error',
    );
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (!response.ok) {
    const detail =
      (body as { detail?: string })?.detail ||
      `Request failed with status ${response.status}`;
    let code = 'request_failed';
    if (response.status === 401) code = 'unauthorized';
    else if (response.status === 404) code = 'not_found';
    else if (response.status >= 500) code = 'server_error';
    throw new ApiRequestError(detail, response.status, code);
  }

  return body as ProcessingJobStatus;
}

/**
 * Retrieve the full processing result for a completed or partial_success job.
 *
 * GET /api/process/result/{job_id}
 */
export async function getJobResult(
  jobId: string,
): Promise<ProcessingResult> {
  const url = `${API_BASE}/api/process/result/${encodeURIComponent(jobId)}`;

  const token = getStoredToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(url, { method: 'GET', headers });
  } catch {
    throw new ApiRequestError(
      'Network error. Cannot reach backend server.',
      0,
      'network_error',
    );
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  // The backend returns 200 with a detail message for queued/processing jobs
  if (response.status === 200 && body && typeof body === 'object' && 'detail' in (body as Record<string, unknown>)) {
    const detail = (body as { detail: string }).detail;
    if (detail && detail.includes('still')) {
      throw new ApiRequestError(detail, 200, 'job_not_ready');
    }
  }

  if (!response.ok) {
    const detail =
      (body as { detail?: string })?.detail ||
      `Request failed with status ${response.status}`;
    let code = 'request_failed';
    if (response.status === 401) code = 'unauthorized';
    else if (response.status === 404) code = 'not_found';
    else if (response.status >= 500) code = 'server_error';
    throw new ApiRequestError(detail, response.status, code);
  }

  return body as ProcessingResult;
}

/**
 * Retrieve processing history for the current authenticated user.
 *
 * GET /api/process/history
 *
 * This is the BACKEND-AUTHORITATIVE history endpoint. The backend
 * is the sole source of truth for all job data. We do NOT cache or
 * store this information locally — it is always fetched fresh from
 * the backend on Dashboard mount.
 *
 * The response is an array of ProcessingHistoryItem objects, sorted
 * newest-first, enriched with sector, confidence, warnings_count,
 * and has_pricing from the tender_results table.
 */
export async function getJobHistory(): Promise<ProcessingHistoryItem[]> {
  const url = `${API_BASE}/api/process/history`;

  const token = getStoredToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(url, { method: 'GET', headers });
  } catch {
    throw new ApiRequestError(
      'Network error. Cannot reach backend server.',
      0,
      'network_error',
    );
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (!response.ok) {
    const detail =
      (body as { detail?: string })?.detail ||
      `Request failed with status ${response.status}`;
    let code = 'request_failed';
    if (response.status === 401) code = 'unauthorized';
    else if (response.status >= 500) code = 'server_error';
    throw new ApiRequestError(detail, response.status, code);
  }

  return body as ProcessingHistoryItem[];
}

/**
 * Retry specific recoverable pipeline stages for an existing job.
 *
 * POST /api/process/retry/{job_id}
 *
 * Retries the specified stages WITHOUT requiring full document re-upload.
 * The backend reuses the existing uploaded file and resolves dependencies
 * automatically.  Retry count and retried stages are tracked for transparency.
 *
 * @param jobId - The job ID to retry
 * @param stages - List of stage names to retry (e.g. ["pricing_calculation"])
 * @returns RetryResponse with final status and retry metadata
 */
export async function retryJob(
  jobId: string,
  stages: string[],
): Promise<RetryResponse> {
  const url = `${API_BASE}/api/process/retry/${encodeURIComponent(jobId)}`;

  const token = getStoredToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify({ stages }),
    });
  } catch {
    throw new ApiRequestError(
      'Network error. Cannot reach backend server.',
      0,
      'network_error',
    );
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (!response.ok) {
    const detail =
      (body as { detail?: string })?.detail ||
      `Request failed with status ${response.status}`;
    let code = 'request_failed';
    if (response.status === 400) code = 'bad_request';
    else if (response.status === 401) code = 'unauthorized';
    else if (response.status === 404) code = 'not_found';
    else if (response.status >= 500) code = 'server_error';
    throw new ApiRequestError(detail, response.status, code);
  }

  return body as RetryResponse;
}

/**
 * Download an Excel export of a processing result.
 *
 * GET /api/process/export/excel/{job_id}
 *
 * Generates a .xlsx workbook with BOQ items, pricing summary, workforce
 * analysis, and warnings.  Opens a download dialog in the browser.
 *
 * @param jobId - The job ID to export
 * @param filename - Optional filename for the downloaded file (defaults to backend-generated name)
 */
export function downloadExcelExport(jobId: string, filename?: string): Promise<void> {
  const token = getStoredToken();
  const url = `${API_BASE}/api/process/export/excel/${encodeURIComponent(jobId)}`;

  return fetch(url, {
    method: 'GET',
    headers: {
      'Authorization': token ? `Bearer ${token}` : '',
    },
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Export failed with status ${response.status}`);
      }
      return response.blob();
    })
    .then((blob) => {
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = filename ?? `${jobId}_tender_export.xlsx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(blobUrl);
    });
}

/**
 * Download a PDF report of a processing result.
 *
 * GET /api/process/export/pdf/{job_id}
 *
 * Generates a professional client-ready PDF report with cover page,
 * executive summary, key insights, pricing breakdown, workforce
 * analysis, and risks/warnings.  Opens a download dialog.
 *
 * @param jobId - The job ID to export
 * @param filename - Optional filename for the downloaded file
 */
export function downloadPdfReport(jobId: string, filename?: string): Promise<void> {
  const token = getStoredToken();
  const url = `${API_BASE}/api/process/export/pdf/${encodeURIComponent(jobId)}`;

  return fetch(url, {
    method: 'GET',
    headers: {
      'Authorization': token ? `Bearer ${token}` : '',
    },
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error(`PDF export failed with status ${response.status}`);
      }
      return response.blob();
    })
    .then((blob) => {
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = filename ?? `${jobId}_tender_report.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(blobUrl);
    });
}

/**
 * Download a CSV export of BOQ items from a processing result.
 *
 * GET /api/process/export/csv/{job_id}
 *
 * Generates a comma-separated values file with BOQ items, quantities,
 * rates, and amounts for easy import into spreadsheet applications.
 *
 * @param jobId - The job ID to export
 * @param filename - Optional filename for the downloaded file
 */
export function downloadCsvExport(jobId: string, filename?: string): Promise<void> {
  const token = getStoredToken();
  const url = `${API_BASE}/api/process/export/csv/${encodeURIComponent(jobId)}`;

  return fetch(url, {
    method: 'GET',
    headers: {
      'Authorization': token ? `Bearer ${token}` : '',
    },
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error(`CSV export failed with status ${response.status}`);
      }
      return response.blob();
    })
    .then((blob) => {
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = filename ?? `${jobId}_tender_export.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(blobUrl);
    });
}

/**
 * Download the Bid Response Roadmap PDF.
 *
 * GET /api/process/export/roadmap/{job_id}
 *
 * Generates a clean, structured PDF guide that maps to the original tender,
 * with Data Entry Schedule and manual entry placeholders for missing data.
 *
 * @param jobId - The job ID to export
 * @param filename - Optional filename for the downloaded file
 */
export function downloadRoadmap(jobId: string, filename?: string): Promise<void> {
  const token = getStoredToken();
  const url = `${API_BASE}/api/process/export/roadmap/${encodeURIComponent(jobId)}`;

  return fetch(url, {
    method: 'GET',
    headers: {
      'Authorization': token ? `Bearer ${token}` : '',
    },
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Roadmap export failed with status ${response.status}`);
      }
      return response.blob();
    })
    .then((blob) => {
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = filename ?? `${jobId}_bid_response_roadmap.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(blobUrl);
    });
}

/**
 * Download the Tender Integrity Audit PDF.
 *
 * GET /api/process/export/audit/{job_id}
 *
 * Generates an automated report explaining why reconstruction was necessary,
 * flags areas where original document structure failed, links to confidence scores,
 * and includes a risk assessment.
 *
 * @param jobId - The job ID to export
 * @param filename - Optional filename for the downloaded file
 */
export function downloadAudit(jobId: string, filename?: string): Promise<void> {
  const token = getStoredToken();
  const url = `${API_BASE}/api/process/export/audit/${encodeURIComponent(jobId)}`;

  return fetch(url, {
    method: 'GET',
    headers: {
      'Authorization': token ? `Bearer ${token}` : '',
    },
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Audit export failed with status ${response.status}`);
      }
      return response.blob();
    })
    .then((blob) => {
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = filename ?? `${jobId}_tender_integrity_audit.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(blobUrl);
    });
}

/**
 * Fetch the Tender Readiness Report for a completed job.
 *
 * GET /api/process/readiness/{job_id}
 *
 * Returns a comprehensive readiness report with score, missing information,
 * missing documents, confidence summary, risk summary, recommendations,
 * and dashboard integration payload.
 *
 * @param jobId - The job ID to generate readiness for
 * @returns TenderReadinessReport with full readiness assessment
 */
export async function getTenderReadiness(
  jobId: string,
): Promise<TenderReadinessReport> {
  const url = `${API_BASE}/api/process/readiness/${encodeURIComponent(jobId)}`;

  const token = getStoredToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(url, { method: 'GET', headers });
  } catch {
    throw new ApiRequestError(
      'Network error. Cannot reach backend server.',
      0,
      'network_error',
    );
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (!response.ok) {
    const detail =
      (body as { detail?: string })?.detail ||
      `Request failed with status ${response.status}`;
    let code = 'request_failed';
    if (response.status === 400) code = 'bad_request';
    else if (response.status === 401) code = 'unauthorized';
    else if (response.status === 404) code = 'not_found';
    else if (response.status >= 500) code = 'server_error';
    throw new ApiRequestError(detail, response.status, code);
  }

  return body as TenderReadinessReport;
}

/**
 * Download the comprehensive Submission Package PDF.
 *
 * POST /api/process/export/package/{job_id}
 *
 * Generates a comprehensive PDF with Cover Page, Executive Summary,
 * BOQ Summary, Pricing Summary, Compliance Checklist, and Submission Checklist.
 * Accepts optional company_name and company_address overrides.
 *
 * @param jobId - The job ID to generate the package for
 * @param options - Optional company_name and company_address overrides
 * @param filename - Optional filename for the downloaded file
 */
export function downloadSubmissionPackage(
  jobId: string,
  options?: { company_name?: string; company_address?: string },
  filename?: string,
): Promise<void> {
  const token = getStoredToken();
  const url = `${API_BASE}/api/process/export/package/${encodeURIComponent(jobId)}`;

  return fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': token ? `Bearer ${token}` : '',
    },
    body: JSON.stringify(options ?? {}),
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Submission package generation failed with status ${response.status}`);
      }
      return response.blob();
    })
    .then((blob) => {
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = filename ?? `Submission_Package_${jobId}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(blobUrl);
    });
}

/**
 * Generate and download a Submission Letter PDF.
 *
 * POST /api/process/export/letter/{job_id}
 *
 * Sends the extracted data payload with template identifier `submission_v1`
 * and initiates a browser-based download of the resulting PDF.
 * File name format: Submission_Letter_{job_id}.pdf
 *
 * @param jobId - The job ID to generate the letter for
 * @param filename - Optional filename for the downloaded file (defaults to backend-generated name)
 */
/**
 * Download the Tender Readiness Assessment PDF.
 *
 * GET /api/process/export/readiness/{job_id}
 *
 * Generates a professional Tender Readiness Assessment PDF with:
 *   - Overall Status (Ready for Submission, Ready with Minor Actions,
 *     Manual Review Required, Submission Not Ready)
 *   - Verification Summary
 *   - Manual Review Required
 *   - Missing Supporting Documents checklist
 *   - Risk Assessment (Low / Medium / High)
 *   - Recommendations
 *
 * Uses enterprise styling matching the Submission Letter.
 *
 * @param jobId - The job ID to generate readiness for
 * @param filename - Optional filename for the downloaded file
 */
export function downloadReadinessPdf(jobId: string, filename?: string): Promise<void> {
  const token = getStoredToken();
  const url = `${API_BASE}/api/process/export/readiness/${encodeURIComponent(jobId)}`;

  return fetch(url, {
    method: 'GET',
    headers: {
      'Authorization': token ? `Bearer ${token}` : '',
    },
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Readiness assessment export failed with status ${response.status}`);
      }
      return response.blob();
    })
    .then((blob) => {
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = filename ?? `Tender_Readiness_Assessment_${jobId}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(blobUrl);
    });
}

/**
 * Upload a missing supporting document for a processing job.
 *
 * POST /api/process/{job_id}/upload-missing-document
 *
 * Uploads a missing document (e.g. SBD form, tax clearance) directly to the
 * job's uploads folder so the readiness check can be re-run.
 *
 * @param jobId - The job ID to upload the document for
 * @param documentId - The document type ID (e.g. 'sbd2', 'tax_clearance')
 * @param file - The file to upload
 * @returns Upload response with status and message
 */
export async function uploadMissingDocument(
  jobId: string,
  documentId: string,
  file: File,
): Promise<{ status: string; job_id: string; document_id: string; filename: string; message: string }> {
  const url = `${API_BASE}/api/process/${encodeURIComponent(jobId)}/upload-missing-document`;

  const formData = new FormData();
  formData.append('file', file);
  formData.append('document_id', documentId);

  const token = getStoredToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    method: 'POST',
    headers,
    body: formData,
  });

  if (!response.ok) {
    let detail = `Upload failed with status ${response.status}`;
    try {
      const body = await response.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // ignore parse errors
    }
    throw new Error(detail);
  }

  return response.json();
}


/**
 * Retrieve the Processing Audit Log for a job.
 *
 * GET /api/process/audit/{job_id}
 *
 * The audit log is a permanent record of every processing stage with
 * timestamp, status, duration, confidence, warnings, and errors.
 * Failures are NEVER hidden — they are recorded with explicit reasons.
 *
 * @param jobId - The job ID to get the audit log for
 * @returns AuditSummary with complete stage timeline
 */
export async function getAuditLog(
  jobId: string,
): Promise<import('../types/process').AuditSummary> {
  const url = `${API_BASE}/api/process/audit/${encodeURIComponent(jobId)}`;

  const token = getStoredToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(url, { method: 'GET', headers });
  } catch {
    throw new ApiRequestError(
      'Network error. Cannot reach backend server.',
      0,
      'network_error',
    );
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (!response.ok) {
    const detail =
      (body as { detail?: string })?.detail ||
      `Request failed with status ${response.status}`;
    let code = 'request_failed';
    if (response.status === 404) code = 'not_found';
    else if (response.status >= 500) code = 'server_error';
    throw new ApiRequestError(detail, response.status, code);
  }

  return body as import('../types/process').AuditSummary;
}


/**
 * Download the Enterprise Submission Package ZIP.
 *
 * POST /api/process/export/package-zip/{job_id}
 *
 * Generates a complete ZIP with all reports, BOQ files, metadata, and original tender.
 *
 * @param jobId - The job ID
 * @param filename - Optional filename for the download
 * @returns Blob of the ZIP file
 */
export async function downloadSubmissionPackageZip(
  jobId: string,
  filename?: string,
): Promise<Blob> {
  const token = getStoredToken();
  const url = `${API_BASE}/api/process/export/package-zip/${encodeURIComponent(jobId)}`;

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': token ? `Bearer ${token}` : '',
    },
    body: JSON.stringify({}),
  });

  if (!response.ok) {
    throw new Error(`Submission package generation failed with status ${response.status}`);
  }

  const blob = await response.blob();
  const blobUrl = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = blobUrl;
  a.download = filename ?? `Submission_Package_${jobId}.zip`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(blobUrl);

  return blob;
}


export function downloadSubmissionLetter(jobId: string, filename?: string): Promise<void> {
  const token = getStoredToken();
  const url = `${API_BASE}/api/process/export/letter/${encodeURIComponent(jobId)}`;

  return fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': token ? `Bearer ${token}` : '',
    },
    body: JSON.stringify({ template: 'submission_v1' }),
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Submission letter generation failed with status ${response.status}`);
      }
      return response.blob();
    })
    .then((blob) => {
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = filename ?? `Submission_Letter_${jobId}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(blobUrl);
    });
}
