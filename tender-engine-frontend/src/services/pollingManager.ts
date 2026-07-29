/**
 * Polling Manager — Singleton service for job status polling.
 *
 * Manages multiple polling intervals across the application.
 * Prevents duplicate intervals, handles network recovery,
 * and auto-stops on terminal states.
 *
 * CRITICAL RULES:
 *   - NO multiple polling loops per job (Map enforces uniqueness)
 *   - ALL status comes from backend (NEVER infer locally)
 *   - Polling stops immediately on terminal states
 *   - Network errors are retried on next interval tick
 *   - Zombie polling is prevented via cleanup on unmount
 *   - Stale requests are avoided via request tracking
 */
import { getJobStatus, getJobResult } from './process';
import type { ProcessingJobStatus, ProcessingResult, JobStatusValue } from '../types/process';

// ── Constants ───────────────────────────────────────────────────────

const POLL_INTERVAL_MS = 4000; // 4 seconds between polls
const MAX_CONSECUTIVE_ERRORS = 5; // Stop polling after this many consecutive errors

// ── Types ───────────────────────────────────────────────────────────

export type PollingStatus =
  | { type: 'loading'; status: null }
  | { type: 'active'; status: ProcessingJobStatus }
  | { type: 'terminal'; status: ProcessingJobStatus; result: ProcessingResult | null }
  | { type: 'error'; error: string };

export type JobStateChangeHandler = (jobId: string, newStatus: ProcessingJobStatus) => void;
export type JobTerminalHandler = (jobId: string, status: ProcessingJobStatus, result: ProcessingResult | null) => void;
export type JobErrorHandler = (jobId: string, error: string) => void;

export interface PollingSubscribers {
  onStatusChange: JobStateChangeHandler;
  onTerminal: JobTerminalHandler;
  onError: JobErrorHandler;
}

// ── Internal state ──────────────────────────────────────────────────

interface PollingEntry {
  intervalId: ReturnType<typeof setInterval> | null;
  subscribers: PollingSubscribers;
  lastStatus: ProcessingJobStatus | null;
  consecutiveErrors: number;
  /** Monotonically increasing request counter to detect stale responses */
  requestCounter: number;
  /** Whether this entry has been explicitly stopped */
  stopped: boolean;
}

const pollingMap = new Map<string, PollingEntry>();

// ── Helpers ─────────────────────────────────────────────────────────

const TERMINAL_STATUSES: readonly JobStatusValue[] = [
  'completed',
  'partial_success',
  'failed',
];

function isTerminalStatus(status: JobStatusValue): boolean {
  return TERMINAL_STATUSES.includes(status);
}

// ── Core polling function ───────────────────────────────────────────

/**
 * Execute a single poll cycle for a given job.
 * Returns true if the job is still active, false if terminal.
 *
 * Uses a request counter to prevent stale responses:
 * If a new poll cycle starts before a previous one completes,
 * the older response will be discarded (stale request prevention).
 */
async function executePollCycle(jobId: string): Promise<boolean> {
  const entry = pollingMap.get(jobId);
  if (!entry || entry.stopped) return false; // Already stopped

  // Generate a unique request ID for this cycle
  const requestId = ++entry.requestCounter;

  try {
    const status = await getJobStatus(jobId);

    // IMPORTANT: Check if this response is stale — a newer poll cycle
    // may have already started. This prevents zombie polling where
    // a delayed response overwrites newer data.
    const currentEntry = pollingMap.get(jobId);
    if (!currentEntry || currentEntry.stopped || requestId < currentEntry.requestCounter) {
      return false;
    }

    entry.lastStatus = status;
    entry.consecutiveErrors = 0;
    entry.subscribers.onStatusChange(jobId, status);

    // Check if terminal
    if (isTerminalStatus(status.status as JobStatusValue)) {
      // Fetch result for all terminal states
      let result: ProcessingResult | null = null;
      try {
        result = await getJobResult(jobId);
      } catch {
        // Result fetch is best-effort — the user can always
        // click the history entry to retry fetching the result.
      }

      // Notify terminal subscribers (only if entry still exists)
      const terminalEntry = pollingMap.get(jobId);
      if (terminalEntry && !terminalEntry.stopped) {
        terminalEntry.subscribers.onTerminal(jobId, status, result);
      }

      // Stop polling
      stopPolling(jobId);
      return false;
    }

    // Still active — continue polling
    return true;
  } catch (err: unknown) {
    // Check for stale entry before updating
    const errorEntry = pollingMap.get(jobId);
    if (!errorEntry || errorEntry.stopped) return false;

    // Network error — increment counter, notify, keep polling
    errorEntry.consecutiveErrors++;
    const message =
      err instanceof Error ? err.message : 'Failed to poll job status';
    errorEntry.subscribers.onError(jobId, message);

    // After max consecutive errors, stop polling entirely (likely a permanent issue)
    if (errorEntry.consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
      stopPolling(jobId);
      return false;
    }

    // Still return true so polling continues on next interval
    return true;
  }
}

// ── Public API ──────────────────────────────────────────────────────

/**
 * Start polling for a given job ID.
 *
 * Automatically prevents duplicate intervals — if a polling loop already
 * exists for this job_id, it will NOT create a second one.
 * Instead, it updates the subscribers so live callbacks remain accurate.
 *
 * @param jobId - The job ID to poll
 * @param subscribers - Callback handlers for status changes, terminal states, and errors
 */
export function startPolling(
  jobId: string,
  subscribers: PollingSubscribers,
): void {
  if (!jobId) return;

  // Guard: no duplicate intervals
  if (pollingMap.has(jobId)) {
    // Update subscribers in case they changed (e.g., after re-render)
    const existing = pollingMap.get(jobId)!;
    existing.subscribers = subscribers;
    return;
  }

  // Create entry
  const entry: PollingEntry = {
    intervalId: null,
    subscribers,
    lastStatus: null,
    consecutiveErrors: 0,
    requestCounter: 0,
    stopped: false,
  };

  pollingMap.set(jobId, entry);

  // Do an immediate first poll
  executePollCycle(jobId).then(() => {
    // Set up interval (only if still polling after the immediate poll)
    const currentEntry = pollingMap.get(jobId);
    if (!currentEntry || currentEntry.stopped) return;

    currentEntry.intervalId = setInterval(() => {
      executePollCycle(jobId);
    }, POLL_INTERVAL_MS);
  });
}

/**
 * Stop polling for a specific job ID.
 * Cleans up the interval and removes the entry from the manager.
 */
export function stopPolling(jobId: string): void {
  const entry = pollingMap.get(jobId);
  if (!entry) return;

  entry.stopped = true;

  if (entry.intervalId !== null) {
    clearInterval(entry.intervalId);
    entry.intervalId = null;
  }
  pollingMap.delete(jobId);
}

/**
 * Stop ALL active polling intervals.
 * Call this on Dashboard unmount to prevent memory leaks and zombie polling.
 *
 * IMPORTANT: This is called during cleanup to ensure no orphaned intervals
 * continue after the component unmounts.
 */
export function stopAllPolling(): void {
  for (const [jobId] of pollingMap) {
    stopPolling(jobId);
  }
}

/**
 * Check if a job is currently being polled.
 */
export function isPolling(jobId: string): boolean {
  const entry = pollingMap.get(jobId);
  return entry !== undefined && !entry.stopped;
}

/**
 * Get the last known status for a job (if polling).
 * Returns null if the job is not being polled or no status has been fetched yet.
 */
export function getLastStatus(jobId: string): ProcessingJobStatus | null {
  const entry = pollingMap.get(jobId);
  return entry?.lastStatus ?? null;
}

/**
 * Get the number of active polling jobs.
 */
export function getActivePollCount(): number {
  return pollingMap.size;
}

/**
 * Update the polling interval for a job after it reaches partial_success.
 * This is a no-op implementation stub for future slow-down mode.
 * Currently partial_success still stops polling via terminal detection.
 */
export function slowDownPolling(_jobId: string): void {
  // Future: Change interval to 15s for partial_success jobs
  // For now, partial_success is treated as terminal (stops polling)
}

export default {
  startPolling,
  stopPolling,
  stopAllPolling,
  isPolling,
  getLastStatus,
  getActivePollCount,
};