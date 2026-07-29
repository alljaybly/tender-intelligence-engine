/**
 * TenderHistory — Displays uploaded processing jobs with status badges.
 *
 * Persists history in frontend state during session.
 * Provides status badges with appropriate styling:
 *   - queued / processing → blue (informational)
 *   - completed → green (success)
 *   - partial_success → amber/yellow (WARNING, NOT success)
 *   - failed → red (error)
 */
import { Clock, Inbox, AlertTriangle, Loader2 } from 'lucide-react';
import type { ProcessingJobStatus, JobStatusValue } from '../types/process';
import { STATUS_LABELS, TERMINAL_STATUSES } from '../types/process';

interface HistoryItem {
  jobId: string;
  filename: string;
  uploadedAt: string;
  status: ProcessingJobStatus;
}

interface TenderHistoryProps {
  /** List of job history items from the dashboard state. */
  items: HistoryItem[];
  /** Called when user clicks on a job to view its result. */
  onSelectJob: (jobId: string) => void;
  /** The currently selected job ID (if any). */
  selectedJobId: string | null;
}

function StatusBadge({ status }: { status: JobStatusValue }) {
  const label = STATUS_LABELS[status] || status;

  let bgColor: string;
  let textColor: string;
  let dotColor: string;

  switch (status) {
    case 'queued':
    case 'processing':
    case 'extracting':
    case 'boq_analysis':
    case 'pricing':
      bgColor = 'bg-blue-50';
      textColor = 'text-blue-700';
      dotColor = 'bg-blue-500';
      break;
    case 'completed':
      bgColor = 'bg-emerald-50';
      textColor = 'text-emerald-700';
      dotColor = 'bg-emerald-500';
      break;
    case 'partial_success':
      // Use WARNING (amber) styling — NOT success styling
      bgColor = 'bg-amber-50';
      textColor = 'text-amber-700';
      dotColor = 'bg-amber-500';
      break;
    case 'failed':
      bgColor = 'bg-red-50';
      textColor = 'text-red-700';
      dotColor = 'bg-red-500';
      break;
    default:
      bgColor = 'bg-gray-50';
      textColor = 'text-gray-700';
      dotColor = 'bg-gray-500';
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold ${bgColor} ${textColor}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
      {label}
    </span>
  );
}

export default function TenderHistory({
  items,
  onSelectJob,
  selectedJobId,
}: TenderHistoryProps) {
  if (items.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
        <div className="px-5 py-4 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-gray-100 flex items-center justify-center">
              <Clock className="h-4 w-4 text-gray-500" />
            </div>
            <h2 className="text-sm font-semibold text-gray-900">
              Processing History
            </h2>
          </div>
        </div>
        <div className="px-5 py-10 text-center">
          <Inbox className="mx-auto h-10 w-10 text-gray-300 mb-3" />
          <p className="text-sm text-gray-500">
            No processing jobs yet. Upload a tender document to get started.
          </p>
        </div>
      </div>
    );
  }

  // Sort by uploadedAt descending (most recent first)
  const sortedItems = [...items].sort(
    (a, b) => new Date(b.uploadedAt).getTime() - new Date(a.uploadedAt).getTime(),
  );

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
      <div className="px-5 py-4 border-b border-gray-200">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-lg bg-gray-100 flex items-center justify-center">
            <Clock className="h-4 w-4 text-gray-500" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-gray-900">
              Processing History
            </h2>
            <p className="text-xs text-gray-400">
              {items.length} job{items.length !== 1 ? 's' : ''}
            </p>
          </div>
        </div>
      </div>

      <div className="divide-y divide-gray-100 max-h-[480px] overflow-y-auto">
        {sortedItems.map((item) => {
          const isSelected = item.jobId === selectedJobId;
          const isTerminal = TERMINAL_STATUSES.includes(
            item.status.status as JobStatusValue,
          );

          return (
            <button
              key={item.jobId}
              onClick={() => onSelectJob(item.jobId)}
              className={`w-full text-left px-5 py-3.5 hover:bg-gray-50 transition-colors ${
                isSelected
                  ? 'bg-blue-50/70 border-l-2 border-l-blue-500'
                  : 'border-l-2 border-l-transparent'
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-gray-900 truncate">
                    {item.filename}
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {new Date(item.uploadedAt).toLocaleDateString(undefined, {
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </p>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {item.status.progress && !isTerminal && (
                    <span className="text-xs text-gray-400 truncate max-w-[100px]">
                      {item.status.progress}
                    </span>
                  )}
                  <StatusBadge status={item.status.status as JobStatusValue} />
                </div>
              </div>

              {/* Progress indicator for non-terminal jobs */}
              {!isTerminal && (
                <div className="mt-2 flex items-center gap-2">
                  <Loader2 className="h-3 w-3 animate-spin text-blue-500" />
                  <div className="flex-1 bg-gray-100 rounded-full h-1.5 overflow-hidden">
                    <div
                      className="bg-blue-500 h-full rounded-full animate-pulse"
                      style={{ width: '50%' }}
                    />
                  </div>
                </div>
              )}

              {/* Error message for failed jobs */}
              {item.status.status === 'failed' && item.status.error_message && (
                <p className="mt-1.5 text-xs text-red-600 truncate">
                  {item.status.error_message}
                </p>
              )}

              {/* Warning indicator for partial_success */}
              {item.status.status === 'partial_success' && (
                <div className="mt-1.5 flex items-center gap-1">
                  <AlertTriangle className="h-3 w-3 text-amber-500" />
                  <span className="text-xs text-amber-600">
                    Completed with warnings
                  </span>
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export type { HistoryItem };