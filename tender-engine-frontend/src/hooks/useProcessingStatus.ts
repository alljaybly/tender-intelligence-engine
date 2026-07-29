/**
 * Polling hook for processing job status.
 *
 * Polls GET /api/process/status/{job_id} every 2 seconds while the job
 * is queued or processing. Stops polling on terminal states
 * (completed, partial_success, failed).
 *
 * Handles:
 * - Network interruption
 * - Unauthorized (401)
 * - Backend errors (5xx)
 * - Job not found (404)
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { getJobStatus } from '../services/process';
import type { ProcessingJobStatus, JobStatusValue } from '../types/process';
import { TERMINAL_STATUSES } from '../types/process';

const POLL_INTERVAL_MS = 2000; // 2 seconds

export interface UseProcessingStatusOptions {
  /** The job ID to poll. If null/undefined, polling is disabled. */
  jobId: string | null;
  /** Whether to automatically start polling. Defaults to true. */
  autoStart?: boolean;
}

export interface UseProcessingStatusResult {
  /** Current job status, or null if not yet loaded. */
  status: ProcessingJobStatus | null;
  /** True while a poll request is in flight. */
  isLoading: boolean;
  /** Error message if the last poll failed. */
  error: string | null;
  /** Whether the job has reached a terminal state. */
  isTerminal: boolean;
  /** Manually start/resume polling. */
  start: () => void;
  /** Manually stop polling. */
  stop: () => void;
  /** Reset to initial state. */
  reset: () => void;
}

export function useProcessingStatus(
  options: UseProcessingStatusOptions,
): UseProcessingStatusResult {
  const { jobId, autoStart = true } = options;

  const [status, setStatus] = useState<ProcessingJobStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isTerminal, setIsTerminal] = useState(false);

  // Use refs to avoid stale closures in intervals
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const statusRef = useRef<ProcessingJobStatus | null>(null);
  const shouldPollRef = useRef(false);

  const clearPolling = useCallback(() => {
    if (pollingRef.current !== null) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    shouldPollRef.current = false;
  }, []);

  const stop = useCallback(() => {
    clearPolling();
  }, [clearPolling]);

  const reset = useCallback(() => {
    clearPolling();
    setStatus(null);
    setIsLoading(false);
    setError(null);
    setIsTerminal(false);
    statusRef.current = null;
  }, [clearPolling]);

  const pollOnce = useCallback(async (id: string) => {
    setIsLoading(true);
    setError(null);

    try {
      const result = await getJobStatus(id);
      statusRef.current = result;
      setStatus(result);

      const terminal = TERMINAL_STATUSES.includes(result.status as JobStatusValue);
      if (terminal) {
        setIsTerminal(true);
        // Stop polling on terminal state
        if (pollingRef.current) {
          clearInterval(pollingRef.current);
          pollingRef.current = null;
          shouldPollRef.current = false;
        }
      }
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to check job status';
      setError(message);

      // Stop polling on fatal errors
      if (err && typeof err === 'object' && 'status' in err) {
        const statusCode = (err as { status: number }).status;
        if (statusCode === 401 || statusCode === 404 || (statusCode >= 500 && statusCode < 600)) {
          if (pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
            shouldPollRef.current = false;
          }
        }
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  const start = useCallback(() => {
    if (!jobId) return;

    shouldPollRef.current = true;

    // Do an immediate poll
    pollOnce(jobId);

    // Then poll every POLL_INTERVAL_MS
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
    }
    pollingRef.current = setInterval(() => {
      if (shouldPollRef.current && jobId) {
        pollOnce(jobId);
      }
    }, POLL_INTERVAL_MS);
  }, [jobId, pollOnce]);

  // Start/stop based on jobId and autoStart
  useEffect(() => {
    if (!jobId || !autoStart) {
      return;
    }

    start();

    return () => {
      clearPolling();
    };
  }, [jobId, autoStart, start, clearPolling]);

  return {
    status,
    isLoading,
    error,
    isTerminal,
    start,
    stop,
    reset,
  };
}

export default useProcessingStatus;