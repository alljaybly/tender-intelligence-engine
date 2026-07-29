/**
 * ReadinessAssessment — Tender Readiness Report with Quick-Upload & Transparency Logs.
 *
 * Features:
 *   1. Displays the full Tender Readiness Report (score, missing info, missing docs, risks, recs)
 *   2. "Upload" button on each "Not detected" missing document row (Task 2)
 *   3. "View Processing Logs" link at the bottom with a modal showing warnings (Task 3)
 *   4. Integrity enforcement: "Manual Review Required" header stays if critical data missing (Task 4)
 *
 * HONESTY RULES:
 *   - Warnings are NEVER hidden
 *   - "Manual Review Required" persists if Pricing or BOQ is missing
 *   - All confidence levels are preserved as-is from the backend
 */
import { useState, useRef } from 'react';
import {
  AlertTriangle,
  CheckCircle,
  XCircle,
  Upload,
  FileText,
  Eye,
  X,
  BarChart3,
  ShieldAlert,
  RefreshCw,
} from 'lucide-react';
import { uploadMissingDocument, getTenderReadiness } from '../services/process';
import type { TenderReadinessReport, MissingDocument } from '../types/process';

interface ReadinessAssessmentProps {
  report: TenderReadinessReport;
  jobId: string;
  warnings?: string[];
  onReadinessUpdated?: (updatedReport: TenderReadinessReport) => void;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                           */
/* ------------------------------------------------------------------ */

function getScoreColor(score: number): string {
  if (score >= 80) return 'text-emerald-700';
  if (score >= 50) return 'text-amber-700';
  if (score >= 25) return 'text-orange-700';
  return 'text-red-700';
}

function getScoreBg(score: number): string {
  if (score >= 80) return 'bg-emerald-50 border-emerald-200';
  if (score >= 50) return 'bg-amber-50 border-amber-200';
  if (score >= 25) return 'bg-orange-50 border-orange-200';
  return 'bg-red-50 border-red-200';
}

function getRiskBadge(level: string): { bg: string; text: string; label: string } {
  switch (level) {
    case 'low':
      return { bg: 'bg-emerald-100', text: 'text-emerald-800', label: 'Low Risk' };
    case 'medium':
      return { bg: 'bg-amber-100', text: 'text-amber-800', label: 'Medium Risk' };
    case 'high':
      return { bg: 'bg-red-100', text: 'text-red-800', label: 'High Risk' };
    default:
      return { bg: 'bg-gray-100', text: 'text-gray-800', label: level };
  }
}

function getSeverityBadge(severity: string): { bg: string; text: string } {
  switch (severity) {
    case 'critical':
      return { bg: 'bg-red-100', text: 'text-red-800' };
    case 'high':
      return { bg: 'bg-orange-100', text: 'text-orange-800' };
    case 'medium':
      return { bg: 'bg-amber-100', text: 'text-amber-800' };
    case 'low':
      return { bg: 'bg-blue-100', text: 'text-blue-800' };
    default:
      return { bg: 'bg-gray-100', text: 'text-gray-800' };
  }
}

function getPriorityColor(priority: string): string {
  switch (priority) {
    case 'critical': return 'text-red-700';
    case 'high': return 'text-orange-700';
    case 'medium': return 'text-amber-700';
    case 'low': return 'text-blue-700';
    default: return 'text-gray-700';
  }
}

/* ------------------------------------------------------------------ */
/*  Processing Logs Modal (Task 3)                                    */
/* ------------------------------------------------------------------ */

function ProcessingLogsModal({
  warnings,
  onClose,
}: {
  warnings: string[];
  onClose: () => void;
}) {
  if (warnings.length === 0) return null;

  // Parse warnings to identify which extraction stage triggered them
  const parsedWarnings = warnings.map((w) => {
    const lower = w.toLowerCase();
    let stage = 'General';
    if (lower.includes('pricing') || lower.includes('calculation')) stage = 'Pricing';
    else if (lower.includes('ocr') || lower.includes('text') || lower.includes('extraction')) stage = 'OCR / Extraction';
    else if (lower.includes('boq') || lower.includes('bill of quantities')) stage = 'BOQ Analysis';
    else if (lower.includes('sector') || lower.includes('entity') || lower.includes('metadata')) stage = 'Entity Extraction';
    else if (lower.includes('workforce') || lower.includes('labour')) stage = 'Workforce Analysis';
    else if (lower.includes('confidence') || lower.includes('quality')) stage = 'Quality Check';
    else if (lower.includes('duplicate') || lower.includes('file')) stage = 'File Validation';
    return { message: w, stage };
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full mx-4 max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-amber-50 flex items-center justify-center">
              <FileText className="h-4.5 w-4.5 text-amber-600" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-gray-900">Processing Logs</h2>
              <p className="text-sm text-gray-500">
                {warnings.length} warning{warnings.length !== 1 ? 's' : ''} recorded
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
            aria-label="Close"
          >
            <X className="h-5 w-5 text-gray-500" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
          {parsedWarnings.map((pw, i) => (
            <div
              key={i}
              className="rounded-lg border border-amber-100 bg-amber-50/50 p-4"
            >
              <div className="flex items-start gap-3">
                <AlertTriangle className="h-4 w-4 text-amber-500 flex-shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-amber-800">{pw.message}</p>
                  <span className="inline-flex items-center mt-1.5 px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-700">
                    Stage: {pw.stage}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 bg-gray-50 rounded-b-2xl">
          <p className="text-xs text-gray-500">
            These logs are generated deterministically from the processing pipeline.
            Each warning identifies which extraction stage triggered it.
          </p>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Missing Document Row with Upload Button (Task 2)                  */
/* ------------------------------------------------------------------ */

function MissingDocumentRow({
  doc,
  jobId,
  onUploadSuccess,
}: {
  doc: MissingDocument;
  jobId: string;
  onUploadSuccess: (message: string) => void;
}) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setError(null);
    try {
      const result = await uploadMissingDocument(jobId, doc.id, file);
      onUploadSuccess(result.message);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Upload failed';
      setError(message);
    } finally {
      setUploading(false);
      // Reset the file input so the same file can be re-selected
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const severityBadge = getSeverityBadge(doc.severity || 'medium');

  return (
    <tr className="border-b border-gray-100 hover:bg-gray-50/50 transition-colors">
      <td className="py-3 px-4">
        <div className="flex items-center gap-2">
          <XCircle className="h-4 w-4 text-red-400 flex-shrink-0" />
          <span className="text-sm text-gray-700">{doc.name}</span>
        </div>
      </td>
      <td className="py-3 px-4">
        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${severityBadge.bg} ${severityBadge.text}`}>
          {doc.severity || 'medium'}
        </span>
      </td>
      <td className="py-3 px-4">
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-700">
          <XCircle className="h-3 w-3" />
          Not detected
        </span>
      </td>
      <td className="py-3 px-4">
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt"
          className="hidden"
          onChange={handleFileSelected}
        />
        <button
          onClick={handleUploadClick}
          disabled={uploading}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {uploading ? (
            <RefreshCw className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Upload className="h-3.5 w-3.5" />
          )}
          {uploading ? 'Uploading...' : 'Upload'}
        </button>
        {error && (
          <p className="mt-1 text-xs text-red-600">{error}</p>
        )}
      </td>
    </tr>
  );
}

/* ------------------------------------------------------------------ */
/*  Main ReadinessAssessment Component                                */
/* ------------------------------------------------------------------ */

export default function ReadinessAssessment({
  report,
  jobId,
  warnings = [],
  onReadinessUpdated,
}: ReadinessAssessmentProps) {
  const [showLogs, setShowLogs] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const score = report.readiness_score;
  const missingInfo = report.missing_information;
  const missingDocs = report.missing_documents;
  const confidence = report.confidence_summary;
  const risk = report.risk_summary;
  const recommendations = report.recommendations;

  // ── Integrity Enforcement (Task 4) ──────────────────────────────
  // Determine if critical data is missing — if so, force "Manual Review Required"
  const hasPricing = report.dashboard?.has_pricing ?? false;
  const hasBOQ = report.dashboard?.has_boq ?? false;
  const isCriticalDataMissing = !hasPricing || !hasBOQ;

  const overallStatusLabel = isCriticalDataMissing
    ? 'Manual Review Required'
    : score.label === 'high'
    ? 'Ready for Submission'
    : score.label === 'medium'
    ? 'Ready with Minor Actions'
    : 'Manual Review Required';

  const overallStatusColor = isCriticalDataMissing
    ? 'text-red-700 bg-red-50 border-red-200'
    : score.label === 'high'
    ? 'text-emerald-700 bg-emerald-50 border-emerald-200'
    : score.label === 'medium'
    ? 'text-amber-700 bg-amber-50 border-amber-200'
    : 'text-red-700 bg-red-50 border-red-200';

  const handleUploadSuccess = (message: string) => {
    setUploadMessage(message);
    // Auto-dismiss after 5 seconds
    setTimeout(() => setUploadMessage(null), 5000);
    // Re-fetch the readiness report if callback provided
    if (onReadinessUpdated) {
      setRefreshing(true);
      getTenderReadiness(jobId)
        .then((updated) => onReadinessUpdated(updated))
        .catch(() => {
          // Silently fail — the user can manually refresh
        })
        .finally(() => setRefreshing(false));
    }
  };

  return (
    <div className="space-y-6">
      {/* ── Upload success message ──────────────────────────────── */}
      {uploadMessage && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
          <div className="flex items-start gap-3">
            <CheckCircle className="h-5 w-5 text-emerald-500 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-emerald-800">{uploadMessage}</p>
          </div>
        </div>
      )}

      {/* ── Overall Status Header (Task 4: Integrity Enforcement) ── */}
      <div className={`rounded-xl border p-6 ${overallStatusColor}`}>
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold">{overallStatusLabel}</h2>
            <p className="text-sm mt-1 opacity-80">
              {isCriticalDataMissing
                ? 'Critical data gaps detected. Pricing or Bill of Quantities is missing.'
                : score.label_description}
            </p>
          </div>
          <div className="text-right">
            <p className="text-3xl font-black">{Math.round(score.overall_score)}</p>
            <p className="text-xs opacity-70">Readiness Score</p>
          </div>
        </div>
      </div>

      {/* ── Score Breakdown ──────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {Object.entries(score.categories).map(([key, cat]) => (
          <div
            key={key}
            className={`rounded-lg border p-3 ${getScoreBg(cat.score)}`}
          >
            <p className="text-xs font-medium text-gray-500 capitalize mb-1">
              {key.replace(/_/g, ' ')}
            </p>
            <p className={`text-lg font-bold ${getScoreColor(cat.score)}`}>
              {Math.round(cat.score)}
            </p>
            <p className="text-xs text-gray-400 capitalize">{cat.label}</p>
          </div>
        ))}
      </div>

      {/* ── Missing Information ──────────────────────────────────── */}
      {missingInfo.missing_fields.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              <h3 className="text-sm font-semibold text-gray-900">
                Missing Information ({missingInfo.count} of {missingInfo.total_required})
              </h3>
            </div>
          </div>
          <div className="px-6 py-4">
            <div className="space-y-2">
              {missingInfo.missing_fields.map((mf, i) => {
                const sev = getSeverityBadge(mf.severity);
                return (
                  <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-gray-50">
                    <XCircle className="h-4 w-4 text-red-400 flex-shrink-0 mt-0.5" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-900">{mf.label}</span>
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${sev.bg} ${sev.text}`}>
                          {mf.severity}
                        </span>
                      </div>
                      <p className="text-xs text-gray-500 mt-0.5">{mf.reason}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* ── Missing Documents Table with Upload Buttons (Task 2) ── */}
      {missingDocs.missing.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-blue-500" />
              <h3 className="text-sm font-semibold text-gray-900">
                Missing Documents ({missingDocs.missing_count} of {missingDocs.total_required})
              </h3>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="text-left py-3 px-4 font-semibold text-gray-500 text-xs uppercase tracking-wider">
                    Document
                  </th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-500 text-xs uppercase tracking-wider">
                    Severity
                  </th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-500 text-xs uppercase tracking-wider">
                    Status
                  </th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-500 text-xs uppercase tracking-wider">
                    Action
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {missingDocs.missing.map((doc) => (
                  <MissingDocumentRow
                    key={doc.id}
                    doc={doc}
                    jobId={jobId}
                    onUploadSuccess={handleUploadSuccess}
                  />
                ))}
              </tbody>
            </table>
          </div>
          <div className="px-6 py-3 border-t border-gray-100 bg-gray-50 rounded-b-xl">
            <p className="text-xs text-gray-500">{missingDocs.summary}</p>
          </div>
        </div>
      )}

      {/* ── Detected Documents ────────────────────────────────────── */}
      {missingDocs.detected.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-emerald-500" />
              <h3 className="text-sm font-semibold text-gray-900">
                Detected Documents ({missingDocs.detected_count})
              </h3>
            </div>
          </div>
          <div className="px-6 py-4">
            <div className="flex flex-wrap gap-2">
              {missingDocs.detected.map((doc) => (
                <span
                  key={doc.id}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200"
                >
                  <CheckCircle className="h-3 w-3" />
                  {doc.name}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Confidence Summary ────────────────────────────────────── */}
      <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
        <div className="px-6 py-4 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-blue-500" />
            <h3 className="text-sm font-semibold text-gray-900">Confidence Summary</h3>
          </div>
        </div>
        <div className="px-6 py-4">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex-1">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-gray-500">Overall</span>
                <span className={`text-xs font-bold ${getScoreColor(confidence.overall_score * 100)}`}>
                  {Math.round(confidence.overall_score * 100)}%
                </span>
              </div>
              <div className="h-2 rounded-full bg-gray-200 overflow-hidden">
                <div
                  className={`h-full rounded-full ${
                    confidence.overall_score >= 0.7 ? 'bg-emerald-500' :
                    confidence.overall_score >= 0.5 ? 'bg-amber-500' : 'bg-red-500'
                  }`}
                  style={{ width: `${Math.round(confidence.overall_score * 100)}%` }}
                />
              </div>
            </div>
          </div>
          <p className="text-sm text-gray-600 mb-3">{confidence.summary_text}</p>
          <div className="grid grid-cols-3 gap-3">
            {Object.entries(confidence.levels).map(([key, level]) => (
              <div key={key} className="rounded-lg bg-gray-50 p-3 text-center">
                <p className="text-xs text-gray-500 capitalize mb-1">{key}</p>
                <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                  level === 'high' ? 'bg-emerald-100 text-emerald-800' :
                  level === 'medium' ? 'bg-amber-100 text-amber-800' :
                  'bg-red-100 text-red-800'
                }`}>
                  {level}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Risk Summary ──────────────────────────────────────────── */}
      <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
        <div className="px-6 py-4 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-5 w-5 text-red-500" />
            <h3 className="text-sm font-semibold text-gray-900">Risk Assessment</h3>
          </div>
        </div>
        <div className="px-6 py-4">
          <div className="flex items-center gap-3 mb-4">
            <span className={`inline-flex items-center px-3 py-1.5 rounded-lg text-sm font-bold ${getRiskBadge(risk.overall_risk_level).bg} ${getRiskBadge(risk.overall_risk_level).text}`}>
              {getRiskBadge(risk.overall_risk_level).label}
            </span>
            <span className="text-xs text-gray-500">
              {risk.critical_count} critical, {risk.high_count} high, {risk.medium_count} medium, {risk.low_count} low
            </span>
          </div>
          <p className="text-sm text-gray-600 mb-3">{risk.overall_assessment}</p>
          {risk.risks.length > 0 && (
            <div className="space-y-2">
              {risk.risks.map((r, i) => {
                const sev = getSeverityBadge(r.severity);
                return (
                  <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-gray-50">
                    <AlertTriangle className={`h-4 w-4 flex-shrink-0 mt-0.5 ${
                      r.severity === 'critical' ? 'text-red-500' :
                      r.severity === 'high' ? 'text-orange-500' : 'text-amber-500'
                    }`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-900">{r.title}</span>
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${sev.bg} ${sev.text}`}>
                          {r.severity}
                        </span>
                      </div>
                      <p className="text-xs text-gray-500 mt-0.5">{r.description}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* ── Recommendations ────────────────────────────────────────── */}
      {recommendations.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-sm font-semibold text-gray-900">
              Recommendations ({recommendations.length})
            </h3>
          </div>
          <div className="px-6 py-4 space-y-2">
            {recommendations.map((rec, i) => (
              <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-gray-50">
                <div className={`mt-0.5 h-2 w-2 rounded-full flex-shrink-0 ${
                  rec.priority === 'critical' ? 'bg-red-500' :
                  rec.priority === 'high' ? 'bg-orange-500' :
                  rec.priority === 'medium' ? 'bg-amber-500' : 'bg-blue-500'
                }`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-900">{rec.title}</span>
                    <span className={`text-xs font-medium ${getPriorityColor(rec.priority)}`}>
                      {rec.priority}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">{rec.message}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── View Processing Logs Link (Task 3) ────────────────────── */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => setShowLogs(true)}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors shadow-sm"
        >
          <Eye className="h-4 w-4" />
          View Processing Logs
        </button>

        {refreshing && (
          <span className="inline-flex items-center gap-1.5 text-sm text-gray-500">
            <RefreshCw className="h-4 w-4 animate-spin" />
            Refreshing...
          </span>
        )}
      </div>

      {/* ── Processing Logs Modal (Task 3) ──────────────────────────── */}
      {showLogs && (
        <ProcessingLogsModal
          warnings={warnings}
          onClose={() => setShowLogs(false)}
        />
      )}

      {/* ── Footer note ────────────────────────────────────────────── */}
      <p className="text-xs text-gray-400 text-center">
        Generated from verified document extraction. Manual verification required before submission.
      </p>
    </div>
  );
}