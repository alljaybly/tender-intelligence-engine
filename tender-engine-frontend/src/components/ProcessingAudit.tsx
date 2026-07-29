/**
 * ProcessingAudit — Permanent Processing Audit Log Viewer.
 *
 * This is NOT a debugging tool.
 * It is a permanent transparency feature.
 *
 * Displays the complete processing timeline with color-coded stages:
 *   Green  = Success
 *   Amber  = Warning
 *   Red    = Failure
 *
 * Every warning explains WHY.
 * Never displays "Unknown Error".
 *
 * Transparency is a feature.
 */
import { useState, useEffect, useCallback } from 'react';
import {
  CheckCircle,
  AlertTriangle,
  XCircle,
  Clock,
  ChevronDown,
  ChevronUp,
  Shield,
  RefreshCw,
} from 'lucide-react';
import { getAuditLog } from '../services/process';
import {
  AUDIT_STAGE_LABELS,
  type AuditSummary,
  type AuditStage,
} from '../types/process';

interface ProcessingAuditProps {
  jobId: string;
}

/* ------------------------------------------------------------------ */
/*  Helper: format duration                                           */
/* ------------------------------------------------------------------ */

function formatDuration(ms: number | null): string {
  if (ms == null) return '-';
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`;
}

function formatFullTimestamp(ts: string | null): string {
  if (!ts) return '-';
  try {
    const d = new Date(ts);
    return d.toLocaleString('en-ZA', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return ts;
  }
}

/* ------------------------------------------------------------------ */
/*  Helper: stage display name                                        */
/* ------------------------------------------------------------------ */

function getStageLabel(stage: string): string {
  return AUDIT_STAGE_LABELS[stage] || stage.replace(/_/g, ' ');
}

/* ------------------------------------------------------------------ */
/*  Individual Stage Row                                              */
/* ------------------------------------------------------------------ */

function StageRow({ stage, isLast }: { stage: AuditStage; isLast: boolean }) {
  const [expanded, setExpanded] = useState(false);

  const statusConfig = {
    success: {
      dot: 'bg-emerald-500',
      border: 'border-emerald-200',
      bg: 'bg-emerald-50',
      icon: CheckCircle,
      iconColor: 'text-emerald-600',
      textColor: 'text-emerald-800',
    },
    warning: {
      dot: 'bg-amber-500',
      border: 'border-amber-200',
      bg: 'bg-amber-50',
      icon: AlertTriangle,
      iconColor: 'text-amber-600',
      textColor: 'text-amber-800',
    },
    failed: {
      dot: 'bg-red-500',
      border: 'border-red-200',
      bg: 'bg-red-50',
      icon: XCircle,
      iconColor: 'text-red-600',
      textColor: 'text-red-800',
    },
  };

  // Fallback for unknown status
  const cfg = statusConfig[stage.status] || statusConfig.failed;
  const StatusIcon = cfg.icon;

  const hasWarnings = stage.warnings && stage.warnings.length > 0;
  const hasErrors = stage.errors && stage.errors.length > 0;
  const hasDetails = stage.details != null;
  const hasExpandable = hasWarnings || hasErrors || hasDetails;

  return (
    <div className={`relative ${!isLast ? 'pb-3' : ''}`}>
      {/* Timeline connector line */}
      {!isLast && (
        <div className="absolute left-4 top-8 bottom-0 w-0.5 bg-gray-200" />
      )}

      <div
        className={`relative flex items-start gap-3 rounded-xl border ${cfg.border} ${cfg.bg} p-4 transition-colors`}
      >
        {/* Timeline dot */}
        <div className={`mt-2 h-2.5 w-2.5 rounded-full ${cfg.dot} flex-shrink-0 ring-2 ring-white`} />

        {/* Status icon */}
        <div className="flex-shrink-0 mt-0.5">
          <StatusIcon className={`h-5 w-5 ${cfg.iconColor}`} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Stage name & timestamp */}
          <div className="flex items-start justify-between gap-2">
            <div>
              <h4 className={`text-sm font-semibold ${cfg.textColor}`}>
                {getStageLabel(stage.stage)}
              </h4>
              <p className="text-xs text-gray-500 mt-0.5">
                {formatFullTimestamp(stage.timestamp)}
              </p>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              {stage.duration_ms != null && (
                <span className="inline-flex items-center gap-1 text-xs text-gray-500 bg-white rounded-md px-2 py-0.5 border border-gray-200">
                  <Clock className="h-3 w-3" />
                  {formatDuration(stage.duration_ms)}
                </span>
              )}
              {stage.confidence && (
                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-white border border-gray-200 text-gray-600">
                  {stage.confidence}
                </span>
              )}
              {stage.source_module && (
                <span className="hidden sm:inline text-xs text-gray-400 bg-white rounded px-1.5 py-0.5 border border-gray-200">
                  {stage.source_module.split('.').pop()}
                </span>
              )}
            </div>
          </div>

          {/* Details (if present) */}
          {stage.details && !hasExpandable && (
            <p className="mt-1.5 text-xs text-gray-600 line-clamp-2">
              {stage.details}
            </p>
          )}

          {/* Expandable warnings/errors */}
          {hasExpandable && (
            <>
              <button
                onClick={() => setExpanded(!expanded)}
                className="mt-1.5 inline-flex items-center gap-1 text-xs font-medium text-gray-500 hover:text-gray-700 transition-colors"
              >
                {expanded ? (
                  <ChevronUp className="h-3 w-3" />
                ) : (
                  <ChevronDown className="h-3 w-3" />
                )}
                {expanded ? 'Hide details' : 'Show details'}
              </button>

              {expanded && (
                <div className="mt-2 space-y-2">
                  {/* Warnings */}
                  {hasWarnings && (
                    <div>
                      <p className="text-xs font-semibold text-amber-700 mb-1">
                        Warnings:
                      </p>
                      <ul className="space-y-0.5">
                        {stage.warnings.map((w, i) => (
                          <li
                            key={i}
                            className="text-xs text-amber-600 flex items-start gap-1.5"
                          >
                            <span className="mt-1 h-1.5 w-1.5 rounded-full bg-amber-400 flex-shrink-0" />
                            {w}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Errors */}
                  {hasErrors && (
                    <div>
                      <p className="text-xs font-semibold text-red-700 mb-1">
                        Errors:
                      </p>
                      <ul className="space-y-0.5">
                        {stage.errors.map((err, i) => (
                          <li
                            key={i}
                            className="text-xs text-red-600 flex items-start gap-1.5"
                          >
                            <span className="mt-1 h-1.5 w-1.5 rounded-full bg-red-400 flex-shrink-0" />
                            {err}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Details text */}
                  {hasDetails && (
                    <div>
                      <p className="text-xs font-semibold text-gray-500 mb-0.5">
                        Details:
                      </p>
                      <p className="text-xs text-gray-600">{stage.details}</p>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Summary Header                                                    */
/* ------------------------------------------------------------------ */

function SummaryHeader({ summary }: { summary: AuditSummary }) {
  const successPct =
    summary.total_stages > 0
      ? Math.round((summary.successful / summary.total_stages) * 100)
      : 0;

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex items-center gap-3 mb-4">
        <div className="h-10 w-10 rounded-xl bg-blue-600 flex items-center justify-center">
          <Shield className="h-5 w-5 text-white" />
        </div>
        <div>
          <h2 className="text-lg font-bold text-gray-900">
            Processing Audit Log
          </h2>
          <p className="text-xs text-gray-500">
            Permanent transparency record of every processing stage
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="rounded-lg bg-gray-50 border border-gray-200 p-3 text-center">
          <p className="text-2xl font-bold text-gray-900">{summary.total_stages}</p>
          <p className="text-xs text-gray-500 mt-0.5">Total Stages</p>
        </div>
        <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-3 text-center">
          <p className="text-2xl font-bold text-emerald-700">{summary.successful}</p>
          <p className="text-xs text-emerald-600 mt-0.5">Successful</p>
        </div>
        <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 text-center">
          <p className="text-2xl font-bold text-amber-700">{summary.warnings}</p>
          <p className="text-xs text-amber-600 mt-0.5">Warnings</p>
        </div>
        <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-center">
          <p className="text-2xl font-bold text-red-700">{summary.failed}</p>
          <p className="text-xs text-red-600 mt-0.5">Failed</p>
        </div>
      </div>

      {/* Success rate bar */}
      <div className="mt-4">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-medium text-gray-500">Success Rate</span>
          <span className="text-xs font-bold text-gray-700">{successPct}%</span>
        </div>
        <div className="h-2 rounded-full bg-gray-200 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${
              successPct >= 80
                ? 'bg-emerald-500'
                : successPct >= 50
                ? 'bg-amber-500'
                : 'bg-red-500'
            }`}
            style={{ width: `${successPct}%` }}
          />
        </div>
      </div>

      {summary.total_duration_ms > 0 && (
        <p className="mt-3 text-xs text-gray-400 text-center">
          Total processing time: {formatDuration(summary.total_duration_ms)}
        </p>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main ProcessingAudit Component                                    */
/* ------------------------------------------------------------------ */

export default function ProcessingAudit({ jobId }: ProcessingAuditProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [auditData, setAuditData] = useState<AuditSummary | null>(null);

  const fetchAudit = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAuditLog(jobId);
      setAuditData(data);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to load audit log';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    fetchAudit();
  }, [fetchAudit]);

  /* ── Loading state ───────────────────────────────────────────── */
  if (loading) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-8">
        <div className="flex items-center justify-center gap-3">
          <RefreshCw className="h-5 w-5 text-blue-500 animate-spin" />
          <p className="text-sm text-gray-500">Loading audit log...</p>
        </div>
      </div>
    );
  }

  /* ── Error state ─────────────────────────────────────────────── */
  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6">
        <div className="flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-red-800">
              Failed to load audit log
            </p>
            <p className="text-sm text-red-600 mt-1">{error}</p>
            <button
              onClick={fetchAudit}
              className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border border-red-300 bg-white text-red-700 hover:bg-red-50 transition-colors"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  /* ── Empty state ─────────────────────────────────────────────── */
  if (!auditData || auditData.stages.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-8">
        <div className="text-center">
          <Shield className="h-10 w-10 text-gray-300 mx-auto mb-3" />
          <p className="text-sm font-semibold text-gray-700">
            No audit log entries yet
          </p>
          <p className="text-sm text-gray-500 mt-1">
            Audit log will be populated as the job processes.
          </p>
        </div>
      </div>
    );
  }

  /* ── Legend ──────────────────────────────────────────────────── */
  const legend = [
    { color: 'bg-emerald-500', label: 'Success' },
    { color: 'bg-amber-500', label: 'Warning' },
    { color: 'bg-red-500', label: 'Failure' },
  ];

  return (
    <div className="space-y-4">
      {/* Summary */}
      <SummaryHeader summary={auditData} />

      {/* Legend */}
      <div className="flex items-center gap-4 px-1">
        {legend.map((item) => (
          <div key={item.label} className="flex items-center gap-1.5">
            <span className={`h-2.5 w-2.5 rounded-full ${item.color}`} />
            <span className="text-xs text-gray-500">{item.label}</span>
          </div>
        ))}
      </div>

      {/* Timeline */}
      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-900">
            Stage Timeline
          </h3>
        </div>

        <div className="space-y-0">
          {auditData.stages.map((stage, index) => (
            <StageRow
              key={`${stage.stage}-${index}`}
              stage={stage}
              isLast={index === auditData.stages.length - 1}
            />
          ))}
        </div>

        {/* Unique identifier footer */}
        <div className="mt-4 pt-3 border-t border-gray-200">
          <p className="text-xs text-gray-400 text-center">
            Audit Log ID: {auditData.tender_id} |{' '}
            {auditData.total_stages} stages recorded |{' '}
            Permanent record — never modified or deleted
          </p>
        </div>
      </div>
    </div>
  );
}