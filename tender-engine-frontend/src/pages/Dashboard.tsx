/**
 * Dashboard — Tender processing control center.
 *
 * Sections:
 *   1. Upload section (UploadCard)
 *   2. Processing history section (TenderHistory)
 *   3. Result viewer section (ResultViewer)
 *   4. History loading on mount (from backend)
 *   5. Polling manager integration — real-time status updates
 *   6. Warning/error display
 *
 * ── History Loading (Phase 3A) ─────────────────────────────────────
 * On mount → GET /api/process/history → populate history list
 * Backend is the SOLE source of truth for history data.
 * No cached/fake statuses, no synthetic frontend history.
 *
 * ── Refresh-Safe Active Job Restoration (Phase 3A) ─────────────────
 * localStorage (jobRegistry) stores ONLY job IDs for active jobs.
 * After fetching history, we check which jobs are still active
 * (queued/processing) and resume polling for them automatically.
 * This ensures polling resumes after refresh without storing
 * any status data in localStorage.
 *
 * ── Polling Lifecycle ──────────────────────────────────────────────
 * After history load → startPolling() for all active jobs
 * On status change → update history in real-time
 * On terminal → stopPolling() + fetch result
 * On unmount → stopAllPolling() cleanup
 *
 * CRITICAL RULES:
 *   - Backend is ALWAYS the source of truth
 *   - localStorage stores ONLY job IDs (via jobRegistry)
 *   - NO fake statuses, NO cached results
 *   - partial_success must remain visible
 *   - failed stages must remain visible
 *   - warnings must remain visible
 *   - pricing unavailable must remain visible
 */
import { useState, useCallback, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import AppFooter from '../components/layout/AppFooter';
import BackendWakingBanner from '../components/layout/BackendWakingBanner';
import LanguageSelector from '../components/layout/LanguageSelector';
import { useBackendHealth } from '../hooks/useBackendHealth';
import UploadCard from '../components/UploadCard';
import TenderHistory from '../components/TenderHistory';
import type { HistoryItem } from '../components/TenderHistory';
import ResultViewer from '../components/ResultViewer';
import { getJobResult, getJobHistory } from '../services/process';
import { saveJobId, getStoredJobIds, removeJobId } from '../services/jobRegistry';
import {
  startPolling,
  stopAllPolling,
  isPolling,
} from '../services/pollingManager';
import type { PollingSubscribers } from '../services/pollingManager';
import type {
  ProcessUploadResponse,
  ProcessingJobStatus,
  ProcessingResult,
  JobStatusValue,
} from '../types/process';
import { TERMINAL_STATUSES } from '../types/process';

/**
 * Loading skeleton component for the history panel.
 * Shows 3 placeholder cards while history is being fetched.
 * Prevents empty flashing during the backend request.
 */
function HistoryLoadingSkeleton() {
  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm animate-pulse">
      <div className="px-6 py-5 border-b border-gray-200">
        <div className="h-5 bg-gray-200 rounded w-36 mb-1" />
        <div className="h-3 bg-gray-200 rounded w-48" />
      </div>
      {[1, 2, 3].map((i) => (
        <div key={i} className="px-6 py-4 border-b border-gray-100">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 space-y-2">
              <div className="h-4 bg-gray-200 rounded w-3/4" />
              <div className="h-3 bg-gray-200 rounded w-1/2" />
            </div>
            <div className="h-5 bg-gray-200 rounded-full w-20" />
          </div>
          <div className="mt-2 h-1.5 bg-gray-200 rounded-full w-full" />
        </div>
      ))}
    </div>
  );
}

/**
 * Statuses that indicate a job is still actively processing
 * and should be polled for updates.
 */
const ACTIVE_STATUSES: readonly string[] = [
  'queued',
  'processing',
  'extracting',
  'boq_analysis',
  'pricing',
];

function isActiveStatus(status: string): boolean {
  return ACTIVE_STATUSES.includes(status);
}

export default function Dashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { isChecking } = useBackendHealth();

  // ── History loading state ──────────────────────────────────────────
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);

  // ── Core state ───────────────────────────────────────────────────
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [result, setResult] = useState<ProcessingResult | null>(null);
  const [resultLoading, setResultLoading] = useState(false);
  const [resultError, setResultError] = useState<string | null>(null);
  const [pollingErrors, setPollingErrors] = useState<Map<string, string>>(new Map());

  // Track whether we've already started polling during this mount.
  // We use a ref (not state) because this doesn't affect rendering.
  const pollingStarted = useRef(false);

  // ── History loading on mount ─────────────────────────────────────
  /**
   * On Dashboard mount, fetch the user's processing history from the
   * backend. This is the authoritative source of truth — we NEVER
   * reconstruct history from localStorage alone.
   *
   * After fetching history, we check for active jobs and resume polling
   * automatically. This ensures that if the user refreshes the browser
   * while a job is processing, polling resumes seamlessly.
   */
  useEffect(() => {
    console.log('[Dashboard] Mounted — fetching history from backend');
    let cancelled = false;

    async function loadHistory() {
      try {
        console.log('[Dashboard] Fetching /api/process/history...');
        const historyItems = await getJobHistory();
        console.log('[Dashboard] History loaded:', historyItems.length, 'jobs');

        if (cancelled) {
          console.log('[Dashboard] History load cancelled (strict mode teardown) — skipping state update');
          return;
        }

        // Convert backend ProcessingHistoryItems to frontend HistoryItems.
        // The backend already returns data sorted newest-first.
        const items: HistoryItem[] = historyItems.map((item) => ({
          jobId: item.job_id,
          filename: item.filename ?? item.job_id.slice(0, 8) + '...',
          uploadedAt: item.created_at ?? new Date().toISOString(),
          status: {
            job_id: item.job_id,
            status: item.status as JobStatusValue,
            progress: null,
            created_at: item.created_at,
            updated_at: item.updated_at,
            error_message: item.error_message,
          },
        }));

        setHistory(items);

        // ── Refresh-Safe Active Job Restoration ──────────────────────
        // After loading history, check which jobs are still active
        // (queued, processing) and resume polling for them.
        // This is how we survive browser refreshes — the backend
        // tells us what's still running, and we restart polling.
        const activeJobs = items.filter((item) =>
          isActiveStatus(item.status.status),
        );

        if (activeJobs.length > 0) {
          console.log('[Dashboard] Active jobs found:', activeJobs.length, '- resuming polling');
          startPollingForActiveJobs(activeJobs.map((j) => j.jobId));

          // Select the most recent active job so the user sees progress
          const mostRecent = activeJobs.sort(
            (a, b) =>
              new Date(b.uploadedAt).getTime() -
              new Date(a.uploadedAt).getTime(),
          )[0];
          setActiveJobId(mostRecent.jobId);
          setSelectedJobId(mostRecent.jobId);
        } else {
          console.log('[Dashboard] No active jobs found');

          // If there are completed jobs, select the most recent one
          if (items.length > 0) {
            setSelectedJobId(items[0].jobId);
          }
        }

        // Check for any orphaned job IDs in localStorage that the
        // backend doesn't know about (e.g., deleted jobs). These are
        // stale entries we should clean up.
        const storedIds = getStoredJobIds();
        const backendIds = new Set(items.map((i) => i.jobId));
        const staleIds = storedIds.filter((id) => !backendIds.has(id));
        if (staleIds.length > 0) {
          console.log('[Dashboard] Cleaning up', staleIds.length, 'stale job IDs from localStorage');
          for (const staleId of staleIds) {
            removeJobId(staleId);
          }
        }
      } catch (err: unknown) {
        console.error('[Dashboard] Failed to load history:', err);
        if (!cancelled) {
          setHistoryError(
            err instanceof Error
              ? err.message
              : 'Failed to load processing history',
          );
        }
      } finally {
        if (!cancelled) {
          setHistoryLoading(false);
          console.log('[Dashboard] History loading complete');
        }
      }
    }

    loadHistory();

    return () => {
      cancelled = true;
    };
  }, []); // Run once on mount

  // ── Cleanup on unmount ─────────────────────────────────────────
  useEffect(() => {
    return () => {
      console.log('[Dashboard] Unmount — stopping all polling');
      stopAllPolling();
    };
  }, []);

  // ── Polling handler factory ─────────────────────────────────────
  function buildPollingSubscribers(): PollingSubscribers {
    return {
      onStatusChange: (jobId: string, newStatus: ProcessingJobStatus) => {
        // Update history whenever polling discovers a new status
        setHistory((prev) => {
          const exists = prev.some((item) => item.jobId === jobId);
          if (exists) {
            return prev.map((item) =>
              item.jobId === jobId
                ? { ...item, status: newStatus }
                : item,
            );
          }
          // New job discovered via polling (e.g., from another session)
          return [
            ...prev,
            {
              jobId,
              filename: jobId.slice(0, 8) + '...',
              uploadedAt: newStatus.created_at ?? new Date().toISOString(),
              status: newStatus,
            },
          ];
        });

        // Clear any polling error for this job
        setPollingErrors((prev) => {
          const next = new Map(prev);
          next.delete(jobId);
          return next;
        });
      },

      onTerminal: (jobId: string, terminalStatus: ProcessingJobStatus, terminalResult: ProcessingResult | null) => {
        // Update history to reflect terminal state
        setHistory((prev) =>
          prev.map((item) =>
            item.jobId === jobId
              ? { ...item, status: terminalStatus }
              : item,
          ),
        );

        // If the terminal job is the currently selected one, show the result
        setSelectedJobId((currentSelected) => {
          if (currentSelected === jobId && terminalResult) {
            setResult(terminalResult);
            setResultLoading(false);
            setResultError(null);
          }
          return currentSelected;
        });

        // If the terminal job is the active one, clear the active pointer
        setActiveJobId((currentActive) => {
          if (currentActive === jobId) {
            return null;
          }
          return currentActive;
        });
      },

      onError: (jobId: string, error: string) => {
        // Track polling errors per job
        setPollingErrors((prev) => {
          const next = new Map(prev);
          next.set(jobId, error);
          return next;
        });
      },
    };
  }

  function startPollingForActiveJobs(jobIds: string[]) {
    if (pollingStarted.current) return;
    pollingStarted.current = true;

    const subscribers = buildPollingSubscribers();
    for (const jobId of jobIds) {
      if (!isPolling(jobId)) {
        startPolling(jobId, subscribers);
      }
    }
  }

  // ── When a new job is uploaded, start polling ────────────────────
  useEffect(() => {
    if (!activeJobId) return;
    if (isPolling(activeJobId)) return;

    // Check if the job is already terminal
    const existing = history.find((item) => item.jobId === activeJobId);
    if (existing) {
      const isTerminalExisting = TERMINAL_STATUSES.includes(
        existing.status.status as JobStatusValue,
      );
      if (isTerminalExisting) {
        // Don't poll terminal jobs — fetch result directly if needed
        return;
      }
    }

    startPolling(activeJobId, buildPollingSubscribers());
  }, [activeJobId, history]);

  // ── Handlers ───────────────────────────────────────────────────────
  function handleLogout() {
    stopAllPolling();
    logout();
    navigate('/login', { replace: true });
  }

  const handleUploadSuccess = useCallback(
    (response: ProcessUploadResponse) => {
      // Persist job ID to localStorage (survives refresh)
      // This is the ONLY thing we store in localStorage — the backend
      // is the source of truth for all status and result data.
      saveJobId(response.job_id);

      // Add to history immediately so the user sees it in the list
      const newItem: HistoryItem = {
        jobId: response.job_id,
        filename: response.filename,
        uploadedAt: new Date().toISOString(),
        status: {
          job_id: response.job_id,
          status: 'queued' as JobStatusValue,
          progress: null,
          created_at: null,
          updated_at: null,
          error_message: null,
        },
      };

      setHistory((prev) => [newItem, ...prev]);

      // Set as active job (triggers polling via useEffect above)
      setActiveJobId(response.job_id);
      setSelectedJobId(response.job_id);
      setResult(null);
      setResultError(null);

      console.log('[Dashboard] Upload success — job', response.job_id, 'queued');
    },
    [],
  );

  const handleSelectJob = useCallback(
    async (jobId: string) => {
      setSelectedJobId(jobId);
      setResultLoading(true);
      setResultError(null);

      // Check if we already have the status in history
      const existing = history.find((item) => item.jobId === jobId);
      const isTerminalExisting = existing
        ? TERMINAL_STATUSES.includes(
            existing.status.status as JobStatusValue,
          )
        : false;

      if (isTerminalExisting) {
        // Fetch result directly from the backend
        // The backend is the authoritative source for all result data
        try {
          const res = await getJobResult(jobId);
          setResult(res);
        } catch (err: unknown) {
          const message =
            err instanceof Error ? err.message : 'Failed to fetch result';
          setResultError(message);
        } finally {
          setResultLoading(false);
        }
      } else {
        // Set as active job to trigger/continue polling
        setActiveJobId(jobId);
        setResult(null);
        setResultLoading(false);
      }
    },
    [history],
  );

  // ── Render helpers ─────────────────────────────────────────────────

  function renderLoadingSkeleton() {
    return (
      <div className="min-h-screen bg-gray-50">
        {/* ── Backend waking-up banner (free-tier cold start) ──────────── */}
        <BackendWakingBanner isChecking={isChecking} />

        {/* Header skeleton */}
        <div className="bg-white border-b border-gray-200 shadow-sm mb-8">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between h-16 animate-pulse">
              <div className="flex items-center gap-3">
                <div className="h-8 w-8 bg-gray-200 rounded" />
                <div className="space-y-1.5">
                  <div className="h-4 bg-gray-200 rounded w-28" />
                  <div className="h-3 bg-gray-200 rounded w-36" />
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="h-8 bg-gray-200 rounded-lg w-40" />
                <div className="h-8 bg-gray-200 rounded-lg w-20" />
              </div>
            </div>
          </div>
        </div>

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left column skeleton */}
            <div className="lg:col-span-1 space-y-6">
              <div className="bg-white rounded-lg border border-gray-200 shadow-sm animate-pulse">
                <div className="px-5 py-4 border-b border-gray-200">
                  <div className="flex items-center gap-2">
                    <div className="h-8 w-8 bg-gray-200 rounded-lg" />
                    <div className="space-y-1">
                      <div className="h-4 bg-gray-200 rounded w-24" />
                      <div className="h-3 bg-gray-200 rounded w-32" />
                    </div>
                  </div>
                </div>
                <div className="px-5 py-4 space-y-4">
                  <div className="h-10 bg-gray-200 rounded w-full" />
                  <div className="h-9 bg-gray-200 rounded w-36" />
                </div>
              </div>

              <HistoryLoadingSkeleton />
            </div>

            {/* Right column skeleton */}
            <div className="lg:col-span-2">
              <div className="bg-white rounded-lg border border-gray-200 shadow-sm animate-pulse">
                <div className="px-6 py-16 text-center space-y-4">
                  <div className="h-16 w-16 bg-gray-200 rounded-full mx-auto" />
                  <div className="h-5 bg-gray-200 rounded w-64 mx-auto" />
                  <div className="h-4 bg-gray-200 rounded w-80 mx-auto" />
                  <div className="flex justify-center gap-8 pt-2">
                    <div className="space-y-2">
                      <div className="h-3 bg-gray-200 rounded w-16 mx-auto" />
                      <div className="h-3 bg-gray-200 rounded w-20 mx-auto" />
                    </div>
                    <div className="space-y-2">
                      <div className="h-3 bg-gray-200 rounded w-16 mx-auto" />
                      <div className="h-3 bg-gray-200 rounded w-20 mx-auto" />
                    </div>
                    <div className="space-y-2">
                      <div className="h-3 bg-gray-200 rounded w-16 mx-auto" />
                      <div className="h-3 bg-gray-200 rounded w-20 mx-auto" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  function renderMainContent() {
    // Get current active status from history
    const activeStatus = activeJobId
      ? history.find((item) => item.jobId === activeJobId)?.status ?? null
      : null;

    const isActiveTerminal = activeStatus
      ? TERMINAL_STATUSES.includes(activeStatus.status as JobStatusValue)
      : false;

    // Get polling error for active job
    const activePollingError = activeJobId ? pollingErrors.get(activeJobId) : null;

    return (
      <div className="min-h-screen bg-gray-50">
        {/* ── Backend waking-up banner (free-tier cold start) ──────────── */}
        <BackendWakingBanner isChecking={isChecking} />

        {/* ── Reconciliation error banner ─────────────────────────────── */}
        {historyError && (
          <div className="bg-amber-50 border-b border-amber-200">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2">
              <div className="flex items-center gap-2">
                <svg
                  className="h-4 w-4 text-amber-500 flex-shrink-0"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
                  />
                </svg>
                <p className="text-sm text-amber-700">{historyError}</p>
              </div>
            </div>
          </div>
        )}

      {/* ── Header ───────────────────────────────────────────────── */}
        <header className="bg-white border-b border-gray-200 shadow-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between h-16">
              <div className="flex items-center gap-3">
                <img
                  src="/images/logo.png"
                  alt="Tender Engine"
                  className="h-8 w-auto"
                />
                <div className="hidden sm:block">
                  <h1 className="text-base font-bold text-gray-900">
                    Tender Engine
                  </h1>
                  <p className="text-xs text-gray-400 leading-tight">
                    Processing Dashboard
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <LanguageSelector />
                <button
                  onClick={() => navigate('/analytics')}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-blue-700 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors border border-blue-100"
                >
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 3v18h18M7 14l3-3 3 2 5-6" />
                  </svg>
                  <span className="hidden sm:inline">Analytics</span>
                </button>
                <div className="hidden sm:flex items-center gap-2 bg-gray-50 rounded-lg px-3 py-1.5 border border-gray-100">
                  <div className="h-6 w-6 rounded-full bg-blue-100 flex items-center justify-center">
                    <svg className="h-3.5 w-3.5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
                    </svg>
                  </div>
                  <span className="text-sm text-gray-600 font-medium">{user?.email}</span>
                </div>
                <button
                  onClick={handleLogout}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-red-600 bg-red-50 rounded-lg hover:bg-red-100 transition-colors border border-red-100"
                >
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" />
                  </svg>
                  <span className="hidden sm:inline">Logout</span>
                </button>
              </div>
            </div>
          </div>
        </header>

        {/* ── Main Content ──────────────────────────────────────────── */}
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* ── Left Column: Upload + History ───────────────────── */}
            <div className="lg:col-span-1 space-y-6">
              {/* Upload Section */}
              <UploadCard onUploadSuccess={handleUploadSuccess} />

              {/* Currently processing indicator */}
              {activeJobId && !isActiveTerminal && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3">
                  <div className="flex items-center gap-2">
                    <svg
                      className="animate-spin h-4 w-4 text-blue-500"
                      fill="none"
                      viewBox="0 0 24 24"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                      />
                    </svg>
                    <div className="text-sm text-blue-700">
                      <span className="font-medium">Processing:</span>{' '}
                      {activeStatus?.progress || 'Waiting...'}
                    </div>
                  </div>
                </div>
              )}

              {/* Polling error indicator */}
              {activePollingError && !isActiveTerminal && (
                <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3">
                  <div className="flex items-start gap-2">
                    <svg
                      className="h-4 w-4 text-red-500 flex-shrink-0 mt-0.5"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
                      />
                    </svg>
                    <div>
                      <p className="text-sm font-medium text-red-700">
                        Status Update Failed
                      </p>
                      <p className="text-xs text-red-500 mt-0.5">
                        {activePollingError}
                      </p>
                      <p className="text-xs text-red-400 mt-0.5">
                        Auto-retrying...
                      </p>
                    </div>
                  </div>
                </div>
              )}

              <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
                <div className="px-5 py-4 border-b border-gray-200">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-xl bg-blue-50 flex items-center justify-center">
                      <svg className="h-5 w-5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M3 3v18h18M7 14l3-3 3 2 5-6" />
                      </svg>
                    </div>
                    <div>
                      <h2 className="text-base font-semibold text-gray-900">Platform Analytics</h2>
                      <p className="text-sm text-gray-500">View platform performance, extraction accuracy, document trends, processing statistics, and export analytics.</p>
                    </div>
                  </div>
                </div>
                <div className="px-5 py-4">
                  <button
                    onClick={() => navigate('/analytics')}
                    className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-blue-700"
                  >
                    Open Analytics
                  </button>
                </div>
              </div>

              {/* Processing History — shows loading skeleton while fetching */}
              {historyLoading ? (
                <HistoryLoadingSkeleton />
              ) : (
                <TenderHistory
                  items={history}
                  onSelectJob={handleSelectJob}
                  selectedJobId={selectedJobId}
                />
              )}
            </div>

            {/* ── Right Column: Result Viewer ──────────────────────── */}
            <div className="lg:col-span-2">
              {selectedJobId && resultLoading && (
                <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
                  <div className="px-6 py-5 border-b border-gray-200">
                    <h2 className="text-lg font-semibold text-gray-900">
                      Loading Result
                    </h2>
                  </div>
                  <div className="px-6 py-12 text-center">
                    <svg
                      className="animate-spin mx-auto h-8 w-8 text-blue-500 mb-3"
                      fill="none"
                      viewBox="0 0 24 24"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                      />
                    </svg>
                    <p className="text-sm text-gray-500">
                      Retrieving processing result...
                    </p>
                  </div>
                </div>
              )}

              {selectedJobId && resultError && (
                <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
                  <div className="px-6 py-5 border-b border-gray-200">
                    <h2 className="text-lg font-semibold text-gray-900">
                      Error
                    </h2>
                  </div>
                  <div className="px-6 py-8">
                    <div className="bg-red-50 border border-red-200 rounded-md px-4 py-3">
                      <div className="flex items-start gap-2">
                        <svg
                          className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                          strokeWidth={2}
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
                          />
                        </svg>
                        <div>
                          <p className="text-sm font-medium text-red-800">
                            Failed to Load Result
                          </p>
                          <p className="text-sm text-red-600 mt-1">
                            {resultError}
                          </p>
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => handleSelectJob(selectedJobId)}
                      className="mt-4 px-4 py-2 text-sm font-medium text-blue-700 bg-blue-50 rounded-md hover:bg-blue-100 transition-colors"
                    >
                      Retry
                    </button>
                  </div>
                </div>
              )}

              {selectedJobId && result && !resultLoading && !resultError && (
                <ResultViewer result={result} />
              )}

              {selectedJobId &&
                !result &&
                !resultLoading &&
                !resultError &&
                activeStatus &&
                !isActiveTerminal && (
                  <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
                    <div className="px-6 py-5 border-b border-gray-200">
                      <h2 className="text-lg font-semibold text-gray-900">
                        Processing
                      </h2>
                    </div>
                    <div className="px-6 py-12 text-center">
                      <svg
                        className="animate-spin mx-auto h-10 w-10 text-blue-500 mb-4"
                        fill="none"
                        viewBox="0 0 24 24"
                      >
                        <circle
                          className="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="4"
                        />
                        <path
                          className="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                        />
                      </svg>
                      <p className="text-sm font-medium text-gray-700 mb-1">
                        Your document is being processed
                      </p>
                      <p className="text-sm text-gray-500">
                        Status:{' '}
                        <span className="font-medium text-blue-600">
                          {activeStatus.progress || 'Queued'}
                        </span>
                      </p>
                      <p className="text-xs text-gray-400 mt-2">
                        This page will update automatically once processing
                        completes.
                      </p>
                    </div>
                  </div>
                )}

              {/* Empty state when no job is selected and no history */}
              {!selectedJobId && !activeJobId && history.length === 0 && !historyLoading && (
                <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
                  <div className="px-6 py-12 text-center">
                    <svg
                      className="mx-auto h-16 w-16 text-gray-300 mb-4"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={1}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
                      />
                    </svg>
                    <h2 className="text-xl font-semibold text-gray-700 mb-2">
                      Tender Processing Dashboard
                    </h2>
                    <p className="text-gray-500 max-w-md mx-auto mb-4">
                      Upload a tender document to get started. Once processed,
                      you'll see extracted data including sector, duration,
                      locations, BOQ items, and pricing.
                    </p>
                    <div className="flex justify-center gap-8 mb-6 text-sm text-gray-400">
                      <div className="text-center">
                        <p className="font-medium text-gray-600">Step 1</p>
                        <p>Upload document</p>
                      </div>
                      <div className="text-center">
                        <p className="font-medium text-gray-600">Step 2</p>
                        <p>Auto-processing</p>
                      </div>
                      <div className="text-center">
                        <p className="font-medium text-gray-600">Step 3</p>
                        <p>View results</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-2.5 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-left max-w-md mx-auto">
                      <svg className="h-4 w-4 text-amber-500 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                      </svg>
                      <p className="text-xs text-amber-700 leading-relaxed">
                        <span className="font-semibold">Heads up:</span> This app runs on free Render infrastructure. The first request each session may take <span className="font-semibold">~30s</span> for the backend to wake up — after that, processing runs at normal speed.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Existing jobs but none selected */}
              {!selectedJobId && !activeJobId && history.length > 0 && (
                <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
                  <div className="px-6 py-12 text-center">
                    <p className="text-gray-500">
                      Select a job from the history to view its result.
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </main>

        {/* Disclaimer */}
        <div className="bg-blue-50 border-t border-blue-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
            <div className="flex items-start gap-3">
              <svg className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-sm text-blue-900 leading-relaxed">
                <span className="font-semibold">About this tool:</span> I've built this to be a partner to the human expert. It does the hard work, but you're still the one in the driver's seat. Always review extracted data carefully before using it in production decisions.
              </p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <AppFooter />
      </div>
    );
  }

  // ── Render ─────────────────────────────────────────────────────────
  // Show a loading skeleton while history is being fetched from the backend.
  // This prevents "empty flashing" — the UI stays visually populated
  // during the brief loading period.
  if (historyLoading) {
    return renderLoadingSkeleton();
  }

  return renderMainContent();
}