/**
 * useBackendHealth — pings the backend /api/health endpoint on mount
 * and exposes the connection state so the UI can show a friendly
 * "waking up" message during free-tier cold starts.
 *
 * The hook:
 *  - Pings /api/health every 3 seconds until the backend responds
 *  - Exposes `isChecking` while polling is active
 *  - Exposes `isReady` once the backend responds
 *  - Stops polling once connected (or after component unmounts)
 *  - Tracks whether we've EVER connected during this session via a
 *    module-level flag, so subsequent navigations don't show the
 *    banner again.
 */
import { useState, useEffect, useRef } from 'react';

const API_BASE =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const POLL_INTERVAL_MS = 3000;
const MAX_POLL_SECONDS = 90; // safety limit: stop after 90s

/**
 * Module-level flag that persists across component re-mounts.
 * Once the backend has responded during this page session, we
 * never show the waking-up banner again.
 */
let hasConnectedThisSession = false;

export function useBackendHealth() {
  const [isChecking, setIsChecking] = useState(!hasConnectedThisSession);
  const [isReady, setIsReady] = useState(hasConnectedThisSession);
  const mountedRef = useRef(true);
  const startTimeRef = useRef(Date.now());

  useEffect(() => {
    mountedRef.current = true;

    // Already connected this session — skip immediately
    if (hasConnectedThisSession) {
      setIsChecking(false);
      setIsReady(true);
      return;
    }

    let pollTimer: ReturnType<typeof setTimeout> | null = null;

    async function ping() {
      if (!mountedRef.current) return;

      // Safety limit — stop after MAX_POLL_SECONDS
      if (Date.now() - startTimeRef.current > MAX_POLL_SECONDS * 1000) {
        if (mountedRef.current) {
          setIsChecking(false);
          setIsReady(true); // Give up gracefully — let the app try anyway
        }
        return;
      }

      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 8000);

        const response = await fetch(`${API_BASE}/api/health`, {
          method: 'GET',
          signal: controller.signal,
        });
        clearTimeout(timeoutId);

        // Any successful response means the backend is alive
        if (response.ok || response.status < 500) {
          hasConnectedThisSession = true;
          if (mountedRef.current) {
            setIsChecking(false);
            setIsReady(true);
          }
          return;
        }
      } catch {
        // Network error — backend is still sleeping, keep polling
      }

      // Schedule next ping
      if (mountedRef.current) {
        pollTimer = setTimeout(ping, POLL_INTERVAL_MS);
      }
    }

    // Start pinging immediately
    ping();

    return () => {
      mountedRef.current = false;
      if (pollTimer) clearTimeout(pollTimer);
    };
  }, []);

  return { isChecking, isReady };
}

export default useBackendHealth;