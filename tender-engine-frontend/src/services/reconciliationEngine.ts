/**
 * Reconciliation Engine — Restores frontend state from backend truth.
 *
 * On startup (Dashboard mount), this module:
 *   1. Reads stored job_ids from localStorage (via jobRegistry)
 *   2. Calls backend GET /api/process/status/{job_id} for each job
 *   3. Calls backend GET /api/process/result/{job_id} for terminal jobs
 *   4. Returns classified results — NO fake states, NO cached status
 *
 * CRITICAL RULES:
 *   - Backend is the ONLY source of truth
 *   - Frontend NEVER infers or simulates job state
 *   - NO status caching in localStorage
 *   - NO placeholders or fake data
 */
import { getJobStatus, getJobResult } from './process';
import { getStoredJobIds } from './jobRegistry';
import type {
  ProcessingJobStatus,
  ProcessingResult,
} from '../types/process';

// ── Public types ────────────────────────────────────────────────────

/** Classified jobs returned after reconciliation completes. */
export interface ReconciledState {
  /** Jobs that are still queued or processing */
  activeJobs: ReconciledJob[];
  /** Jobs that completed successfully */
  completedJobs: ReconciledJobResult[];
  /** Jobs that failed */
  failedJobs: ReconciledJobResult[];
  /** Jobs that completed with partial success */
  partialSuccessJobs: ReconciledJobResult[];
  /** Any errors encountered during reconciliation (not job errors) */
  errors: ReconciliationError[];
}

export interface ReconciledJob {
  jobId: string;
  status: ProcessingJobStatus;
}

export interface ReconciledJobResult {
  jobId: string;
  status: ProcessingJobStatus;
  result: ProcessingResult;
}

export interface ReconciliationError {
  jobId: string;
  message: string;
}

// ── Reconciliation ──────────────────────────────────────────────────

/**
 * Full reconciliation: fetch status for ALL stored job IDs and classify them.
 *
 * Returns a ReconciledState with jobs sorted into:
 *   - activeJobs       → queued or processing
 *   - completedJobs    → completed
 *   - failedJobs       → failed
 *   - partialSuccessJobs → partial_success
 *
 * For terminal-state jobs, the result payload is also fetched.
 *
 * This function must be called on Dashboard mount BEFORE rendering
 * any job-dependent UI.
 */
export async function reconcileJobs(): Promise<ReconciledState> {
  const initialState: ReconciledState = {
    activeJobs: [],
    completedJobs: [],
    failedJobs: [],
    partialSuccessJobs: [],
    errors: [],
  };

  // Step 1: Read job IDs from localStorage
  const jobIds = getStoredJobIds();
  if (jobIds.length === 0) {
    return initialState;
  }

  // Step 2: Fetch status for each job in parallel
  const statusResults = await Promise.allSettled(
    jobIds.map(async (jobId) => {
      const status = await getJobStatus(jobId);
      return { jobId, status };
    }),
  );

  // Step 3: Process each result
  const statusMap = new Map<string, ProcessingJobStatus>();

  for (const result of statusResults) {
    if (result.status === 'fulfilled') {
      statusMap.set(result.value.jobId, result.value.status);
    } else {
      // Job might have been deleted from backend — log and move on
      const jobId = extractJobIdFromError(result.reason);
      initialState.errors.push({
        jobId: jobId ?? 'unknown',
        message:
          result.reason instanceof Error
            ? result.reason.message
            : 'Failed to fetch job status',
      });
    }
  }

  // Step 4: Classify and optionally fetch results
  for (const [jobId, status] of statusMap) {
    if (status.status === 'queued' || status.status === 'processing') {
      initialState.activeJobs.push({ jobId, status });
    } else if (status.status === 'completed') {
      const result = await fetchJobResultSafely(jobId);
      if (result) {
        initialState.completedJobs.push({ jobId, status, result });
      }
    } else if (status.status === 'failed') {
      const result = await fetchJobResultSafely(jobId);
      if (result) {
        initialState.failedJobs.push({ jobId, status, result });
      }
    } else if (status.status === 'partial_success') {
      const result = await fetchJobResultSafely(jobId);
      if (result) {
        initialState.partialSuccessJobs.push({ jobId, status, result });
      }
    }
    // Extracting, boq_analysis, pricing are intermediate processing substates
    // they are actively being processed — classify as active
    else if (
      status.status === 'extracting' ||
      status.status === 'boq_analysis' ||
      status.status === 'pricing'
    ) {
      initialState.activeJobs.push({ jobId, status });
    }
  }

  return initialState;
}

/**
 * Fetch the status of a single job from the backend.
 */
export async function fetchJobState(
  jobId: string,
): Promise<ProcessingJobStatus> {
  return getJobStatus(jobId);
}

/**
 * Classify a list of (jobId, status, result) triples into the standard groups.
 *
 * Useful if you already have the data and just need classification.
 */
export function classifyJobs(
  results: Array<{
    jobId: string;
    status: ProcessingJobStatus;
    result?: ProcessingResult;
  }>,
): ReconciledState {
  const state: ReconciledState = {
    activeJobs: [],
    completedJobs: [],
    failedJobs: [],
    partialSuccessJobs: [],
    errors: [],
  };

  for (const entry of results) {
    const status = entry.status.status;

    if (status === 'queued' || status === 'processing' || status === 'extracting' || status === 'boq_analysis' || status === 'pricing') {
      state.activeJobs.push({ jobId: entry.jobId, status: entry.status });
    } else if (status === 'completed' && entry.result) {
      state.completedJobs.push({
        jobId: entry.jobId,
        status: entry.status,
        result: entry.result,
      });
    } else if (status === 'failed' && entry.result) {
      state.failedJobs.push({
        jobId: entry.jobId,
        status: entry.status,
        result: entry.result,
      });
    } else if (status === 'partial_success' && entry.result) {
      state.partialSuccessJobs.push({
        jobId: entry.jobId,
        status: entry.status,
        result: entry.result,
      });
    }
  }

  return state;
}

// ── Helpers ─────────────────────────────────────────────────────────

/**
 * Attempt to extract a job_id from a caught error.
 * Falls back to 'unknown' if extraction fails.
 */
function extractJobIdFromError(error: unknown): string | null {
  if (error && typeof error === 'object' && 'jobId' in error) {
    return (error as { jobId: string }).jobId;
  }
  return null;
}

/**
 * Safely fetch a job result. Returns null on failure.
 * This is intentionally wrapped so one failed result fetch
 * doesn't break the entire reconciliation.
 */
async function fetchJobResultSafely(
  jobId: string,
): Promise<ProcessingResult | null> {
  try {
    return await getJobResult(jobId);
  } catch {
    // Result may not be available yet (race with terminal status)
    return null;
  }
}