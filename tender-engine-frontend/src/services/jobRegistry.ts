/**
 * Job Registry — Persistence layer for job IDs.
 *
 * Stores ONLY job_id strings in localStorage under a dedicated key.
 * This is the system's ONLY source of job tracking across page refreshes.
 *
 * Authentication owns "access_token" — we do NOT touch it.
 * Backend owns status/result — we do NOT cache any of that here.
 */
const STORAGE_KEY = 'tender_job_ids';

/**
 * Read all stored job IDs from localStorage.
 * Returns an empty array if none are stored.
 */
export function getStoredJobIds(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      // Corrupted data — reset
      clearJobRegistry();
      return [];
    }
    // Filter to only strings, discard any garbage
    const ids = parsed.filter(
      (item): item is string => typeof item === 'string' && item.length > 0,
    );
    // Deduplicate
    return [...new Set(ids)];
  } catch {
    // JSON parse failure — reset
    clearJobRegistry();
    return [];
  }
}

/**
 * Persist a job_id to localStorage.
 * Deduplicates automatically — if the ID already exists, it won't be added twice.
 */
export function saveJobId(jobId: string): void {
  if (!jobId || typeof jobId !== 'string') return;
  try {
    const current = getStoredJobIds();
    const updated = [...new Set([...current, jobId])];
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  } catch {
    // localStorage full or unavailable — fail silently, the app still works
    // without persistence across refreshes for this particular job.
  }
}

/**
 * Remove a specific job_id from localStorage.
 * No-op if the job_id is not stored.
 */
export function removeJobId(jobId: string): void {
  if (!jobId || typeof jobId !== 'string') return;
  try {
    const current = getStoredJobIds();
    const updated = current.filter((id) => id !== jobId);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  } catch {
    // Best-effort
  }
}

/**
 * Clear ALL stored job IDs from localStorage.
 * Use with caution — this is unrecoverable.
 */
export function clearJobRegistry(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Best-effort
  }
}