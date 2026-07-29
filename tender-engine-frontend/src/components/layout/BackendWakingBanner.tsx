/**
 * BackendWakingBanner — A friendly, non-blocking banner shown when the
 * backend is waking up from sleep (free-tier cold start).
 *
 * Renders a notice with a small loading spinner and a clear explanation,
 * providing visual feedback so the user understands why initial requests
 * may take 15-40 seconds.
 *
 * Usage:
 *   <BackendWakingBanner isChecking={isChecking} />
 *
 * When isChecking is false, nothing is rendered.
 */
export function BackendWakingBanner({ isChecking }: { isChecking: boolean }) {
  if (!isChecking) return null;

  return (
    <div className="bg-blue-50 border-b border-blue-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
        <div className="flex items-center gap-3">
          {/* Small animated spinner */}
          <svg
            className="h-5 w-5 animate-spin text-blue-500 flex-shrink-0"
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
          <div className="text-sm text-blue-800">
            <span className="font-semibold">Backend is waking up</span>
            {' '}(free hosting — this usually takes{' '}
            <span className="font-semibold">15–40 seconds</span>
            {' '}on first use). The page will update automatically once
            connected.
          </div>
        </div>
      </div>
    </div>
  );
}

export default BackendWakingBanner;