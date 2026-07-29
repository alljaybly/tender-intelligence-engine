/**
 * ResultViewer — Professional SaaS intelligence dashboard.
 *
 * Transforms processing results into a polished, scannable executive dashboard
 * with clear transparency: confidence scores, partial-success, failed stages.
 *
 * DOWNLOAD WORKFLOW (redesigned):
 *   PRIMARY:  "Generate Submission Package" — one-click ZIP of everything
 *   SECONDARY: "Advanced Downloads" — collapsible section with individual exports
 *
 * CRITICAL: Warnings, failures, and partial-success are core differentiators.
 * They are never hidden — only presented professionally.
 */
import { useState } from 'react';
import {
  Download,
  FileText,
  AlertTriangle,
  XCircle,
  CheckCircle,
  CheckCircle2,
  HardDrive,
  Clock,
  MapPin,
  Users,
  Calendar,
  BarChart3,
  DollarSign,
  Building2,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  FileSpreadsheet,
  FileCheck,
  ShieldAlert,
  Shield,
  Package,
  Archive,
} from 'lucide-react';
import {
  downloadExcelExport,
  downloadPdfReport,
  downloadCsvExport,
  downloadRoadmap,
  downloadAudit,
  downloadSubmissionLetter,
  downloadReadinessPdf,
  downloadSubmissionPackageZip,
} from '../services/process';
import type { ProcessingResult, ExtractedBOQItem } from '../types/process';
import ProcessingAudit from './ProcessingAudit';

interface ResultViewerProps {
  result: ProcessingResult;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                           */
/* ------------------------------------------------------------------ */

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-ZA', {
    style: 'currency',
    currency: 'ZAR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function getConfidenceColor(value: number | null | undefined): string {
  if (value == null) return 'bg-gray-200 text-gray-600';
  if (value >= 0.9) return 'bg-green-100 text-green-800';
  if (value >= 0.7) return 'bg-amber-100 text-amber-800';
  return 'bg-red-100 text-red-800';
}

function getConfidenceBarColor(value: number | null | undefined): string {
  if (value == null) return 'bg-gray-300';
  if (value >= 0.9) return 'bg-green-500';
  if (value >= 0.7) return 'bg-amber-500';
  return 'bg-red-500';
}

function formatStageName(stage: string): string {
  return stage.replace(/_/g, ' ');
}

/* ------------------------------------------------------------------ */
/*  Status Banner                                                     */
/* ------------------------------------------------------------------ */

function StatusBanner({ result }: { result: ProcessingResult }) {
  const config = {
    completed: {
      bg: 'bg-emerald-50 border-emerald-200',
      icon: CheckCircle,
      iconColor: 'text-emerald-500',
      title: 'Processing completed successfully — all stages finished.',
      textColor: 'text-emerald-800',
    },
    partial_success: {
      bg: 'bg-amber-50 border-amber-200',
      icon: AlertTriangle,
      iconColor: 'text-amber-500',
      title: 'Partial Success — some stages completed, others failed.',
      textColor: 'text-amber-800',
    },
    failed: {
      bg: 'bg-red-50 border-red-200',
      icon: XCircle,
      iconColor: 'text-red-500',
      title: 'Processing Failed',
      textColor: 'text-red-800',
    },
  };

  const c = config[result.status];
  const Icon = c.icon;

  return (
    <div className={`rounded-xl border ${c.bg} p-4`}>
      <div className="flex items-start gap-3">
        <Icon className={`h-5 w-5 ${c.iconColor} flex-shrink-0 mt-0.5`} />
        <div>
          <p className={`text-sm font-semibold ${c.textColor}`}>{c.title}</p>
          {result.status === 'partial_success' && (
            <p className="text-sm text-amber-600 mt-1">
              Successfully extracted data is shown below. Unavailable sections
              are marked with failure reasons.
            </p>
          )}
          {result.status === 'failed' && result.warnings.length > 0 && (
            <p className="text-sm text-red-600 mt-1">{result.warnings[0]}</p>
          )}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Warning Panel                                                     */
/* ------------------------------------------------------------------ */

function WarningPanel({ warnings }: { warnings: string[] }) {
  const [expanded, setExpanded] = useState(false);
  if (warnings.length === 0) return null;

  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 hover:bg-amber-100/50 transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-amber-500 flex-shrink-0" />
          <span className="text-sm font-semibold text-amber-800">
            {warnings.length} Warning{warnings.length !== 1 ? 's' : ''}
          </span>
        </div>
        {expanded ? (
          <ChevronUp className="h-4 w-4 text-amber-500" />
        ) : (
          <ChevronDown className="h-4 w-4 text-amber-500" />
        )}
      </button>
      {expanded && (
        <div className="px-4 pb-4">
          <ul className="space-y-1.5">
            {warnings.map((w, i) => (
              <li key={i} className="text-sm text-amber-700 flex items-start gap-2">
                <span className="mt-1.5 block h-1.5 w-1.5 rounded-full bg-amber-400 flex-shrink-0" />
                {w}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Failed Stages Panel                                               */
/* ------------------------------------------------------------------ */

function FailedStagesPanel({ failedStages }: { failedStages: string[] }) {
  const [expanded, setExpanded] = useState(true);
  if (failedStages.length === 0) return null;

  return (
    <div className="rounded-xl border border-red-200 bg-red-50 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 hover:bg-red-100/50 transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          <XCircle className="h-5 w-5 text-red-500 flex-shrink-0" />
          <span className="text-sm font-semibold text-red-800">
            {failedStages.length} Failed Stage{failedStages.length !== 1 ? 's' : ''}
          </span>
        </div>
        {expanded ? (
          <ChevronUp className="h-4 w-4 text-red-500" />
        ) : (
          <ChevronDown className="h-4 w-4 text-red-500" />
        )}
      </button>
      {expanded && (
        <div className="px-4 pb-4">
          <p className="text-sm text-red-600 mb-2">
            The following processing stages failed and their results are unavailable:
          </p>
          <ul className="space-y-1.5">
            {failedStages.map((stage, i) => (
              <li key={i} className="text-sm text-red-700 flex items-start gap-2">
                <span className="mt-1.5 block h-1.5 w-1.5 rounded-full bg-red-400 flex-shrink-0" />
                {formatStageName(stage)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Metric Card                                                       */
/* ------------------------------------------------------------------ */

function MetricCard({
  icon: Icon,
  label,
  value,
  subtext,
  color = 'text-gray-900',
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  subtext?: string;
  color?: string;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div className="h-9 w-9 rounded-lg bg-blue-50 flex items-center justify-center">
          <Icon className="h-4.5 w-4.5 text-blue-600" />
        </div>
      </div>
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
        {label}
      </p>
      <p className={`text-xl font-bold ${color} truncate`}>{value}</p>
      {subtext && (
        <p className="mt-0.5 text-xs text-gray-400">{subtext}</p>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Stage Badges                                                      */
/* ------------------------------------------------------------------ */

function StageBadges({
  completed,
  failed,
}: {
  completed: string[];
  failed: string[];
}) {
  if (completed.length === 0 && failed.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2">
      {completed.map((stage) => (
        <span
          key={stage}
          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200"
        >
          <CheckCircle className="h-3 w-3" />
          {formatStageName(stage)}
        </span>
      ))}
      {failed.map((stage) => (
        <span
          key={stage}
          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-red-50 text-red-700 border border-red-200"
        >
          <XCircle className="h-3 w-3" />
          {formatStageName(stage)}
        </span>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  BOQ Table                                                        */
/* ------------------------------------------------------------------ */

function BOQTable({ items }: { items: ExtractedBOQItem[] }) {
  if (items.length === 0) return null;

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="bg-gray-50 border-b border-gray-200">
            <th className="text-left py-3 px-4 font-semibold text-gray-500 text-xs uppercase tracking-wider">Item</th>
            <th className="text-left py-3 px-4 font-semibold text-gray-500 text-xs uppercase tracking-wider">Description</th>
            <th className="text-right py-3 px-4 font-semibold text-gray-500 text-xs uppercase tracking-wider">Qty</th>
            <th className="text-left py-3 px-4 font-semibold text-gray-500 text-xs uppercase tracking-wider">Unit</th>
            <th className="text-right py-3 px-4 font-semibold text-gray-500 text-xs uppercase tracking-wider">Rate</th>
            <th className="text-right py-3 px-4 font-semibold text-gray-500 text-xs uppercase tracking-wider">Amount</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {items.map((item, i) => (
            <tr key={i} className={`${i % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'} hover:bg-blue-50/30 transition-colors`}>
              <td className="py-2.5 px-4 text-gray-500 font-mono text-xs">{item.item_no || '-'}</td>
              <td className="py-2.5 px-4 text-gray-900 max-w-xs truncate" title={item.description}>{item.description}</td>
              <td className="py-2.5 px-4 text-right text-gray-700 tabular-nums">{item.quantity != null ? item.quantity.toLocaleString() : '-'}</td>
              <td className="py-2.5 px-4 text-gray-600">{item.unit || '-'}</td>
              <td className="py-2.5 px-4 text-right text-gray-700 tabular-nums">{item.rate != null ? formatCurrency(item.rate) : '-'}</td>
              <td className="py-2.5 px-4 text-right font-semibold text-gray-900 tabular-nums">{item.amount != null ? formatCurrency(item.amount) : '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Pricing Section                                                   */
/* ------------------------------------------------------------------ */

function PricingSection({ result }: { result: ProcessingResult }) {
  const pricingUnavailable = result.pricing_status === 'failed' || !result.pricing_result;

  if (pricingUnavailable) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-5">
        <div className="flex items-start gap-3">
          <DollarSign className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-red-800">Pricing Unavailable</p>
            {result.pricing_unavailable_reason && <p className="text-sm text-red-600 mt-1">{result.pricing_unavailable_reason}</p>}
            {result.failed_stages.includes('pricing_calculation') && (
              <p className="text-sm text-red-600 mt-1">The pricing calculation stage failed during processing.</p>
            )}
          </div>
        </div>
      </div>
    );
  }

  const pr = result.pricing_result as Record<string, number | string>;
  const rows = Object.entries(pr);
  const totalKey = rows.length > 0 ? rows[rows.length - 1][0] : null;

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <div className="flex items-center gap-2 mb-5">
        <div className="h-8 w-8 rounded-lg bg-emerald-50 flex items-center justify-center">
          <DollarSign className="h-4 w-4 text-emerald-600" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-gray-900">Pricing Breakdown</h3>
          {result.pricing_status === 'completed' && (
            <span className="inline-flex items-center gap-1 text-xs text-emerald-600">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />Completed
            </span>
          )}
        </div>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {rows.map(([key, value]) => {
          const isTotal = key === totalKey;
          return (
            <div key={key} className={`rounded-lg border ${isTotal ? 'border-emerald-200 bg-emerald-50 col-span-full' : 'border-gray-100 bg-gray-50'} p-3`}>
              <p className="text-xs font-medium text-gray-500 capitalize mb-0.5">{key.replace(/_/g, ' ')}</p>
              <p className={`${isTotal ? 'text-lg font-bold text-emerald-800' : 'text-sm font-semibold text-gray-900'} tabular-nums`}>
                {typeof value === 'number' ? formatCurrency(value) : String(value)}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Submission Package Section — PRIMARY ACTION                       */
/* ------------------------------------------------------------------ */

function SubmissionPackageSection({
  jobId,
  filename,
  canExport,
}: {
  jobId: string;
  filename: string | null;
  canExport: boolean;
}) {
  const [generating, setGenerating] = useState(false);
  const [generated, setGenerated] = useState(false);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);
  const [packageSize, setPackageSize] = useState<string | null>(null);
  const [packageError, setPackageError] = useState<string | null>(null);
  const [errorDetails, setErrorDetails] = useState<string[]>([]);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const handleGenerate = async () => {
    if (!canExport) return;
    setGenerating(true);
    setPackageError(null);
    setErrorDetails([]);
    try {
      const blob = await downloadSubmissionPackageZip(jobId, `Submission_Package_${jobId}.zip`);
      setGenerated(true);
      setGeneratedAt(new Date().toLocaleString());
      setPackageSize(formatFileSize(blob.size));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to generate package';
      setPackageError(msg);
      // Check for specific report failures
      if (msg.includes('failed') || msg.includes('Failed')) {
        setErrorDetails(['One or more reports failed to generate. Please try again or download individual reports below.']);
      }
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="rounded-xl border-2 border-blue-200 bg-gradient-to-br from-blue-50 to-white shadow-lg">
      {/* Package Header */}
      <div className="px-6 py-5 border-b border-blue-100">
        <div className="flex items-start gap-4">
          <div className="h-14 w-14 rounded-2xl bg-blue-600 flex items-center justify-center shadow-lg flex-shrink-0">
            <Package className="h-7 w-7 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 mb-2">
              <CheckCircle className="h-3 w-3" />
              Recommended for most users
            </span>
            <h3 className="text-lg font-bold text-gray-900">Generate Submission Package</h3>
            <p className="text-sm text-gray-600 mt-1">
              Download everything required for this tender in one professionally organised ZIP package.
            </p>
          </div>
        </div>
      </div>

      {/* Package Contents */}
      <div className="px-6 py-4 border-b border-blue-100">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Package includes</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
          {[
            'Executive Summary.pdf',
            'Tender Completion Guide.pdf',
            'Tender Readiness Assessment.pdf',
            'Submission Letter.pdf',
            'Bid Response Roadmap.pdf',
            'Processing Audit.pdf',
            'Evidence Report.pdf',
            'BOQ.xlsx',
            'BOQ.csv',
            'Metadata.json',
          ].map((item) => (
            <div key={item} className="flex items-center gap-2 text-xs text-gray-600">
              <CheckCircle2 className="h-3 w-3 text-emerald-500 flex-shrink-0" />
              <span>{item}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Action */}
      <div className="px-6 py-5 space-y-3">
        <button
          onClick={handleGenerate}
          disabled={generating || !canExport}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-4 px-6 rounded-xl shadow-lg flex items-center justify-center gap-3 disabled:opacity-50 disabled:cursor-not-allowed transition-all hover:shadow-xl active:scale-[0.99]"
        >
          {generating ? (
            <><RefreshCw className="h-5 w-5 animate-spin" /> Generating Submission Package...</>
          ) : generated ? (
            <><Archive className="h-5 w-5" /> Download Submission Package</>
          ) : (
            <><Package className="h-5 w-5" /> Generate Submission Package</>
          )}
        </button>

        <p className="text-xs text-gray-500 text-center">
          This download contains everything required to review, complete and prepare your tender submission.
        </p>

        {/* Package Status */}
        {generated && generatedAt && (
          <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-3">
            <div className="flex items-center gap-2 mb-1">
              <CheckCircle className="h-4 w-4 text-emerald-600" />
              <span className="text-sm font-semibold text-emerald-800">Package ready</span>
            </div>
            <div className="text-xs text-emerald-700 space-y-0.5">
              <p>Generated: {generatedAt}</p>
              {packageSize && <p>Size: {packageSize}</p>}
              <p>Package Version: 2.0.0</p>
            </div>
          </div>
        )}

        {/* Error State */}
        {packageError && (
          <div className="rounded-lg bg-red-50 border border-red-200 p-3">
            <div className="flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 text-red-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-semibold text-red-800">Package generation failed</p>
                <p className="text-xs text-red-600 mt-1">{packageError}</p>
                {errorDetails.map((d, i) => (
                  <p key={i} className="text-xs text-red-600 mt-0.5">{d}</p>
                ))}
                <button
                  onClick={handleGenerate}
                  className="mt-2 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-red-300 bg-white text-red-700 hover:bg-red-50 transition-colors"
                >
                  <RefreshCw className="h-3 w-3" /> Retry
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Advanced Downloads */}
        <div className="border-t border-gray-200 pt-4">
          <button
            onClick={() => setAdvancedOpen(!advancedOpen)}
            className="w-full flex items-center justify-between text-sm text-gray-500 hover:text-gray-700 transition-colors"
          >
            <span className="flex items-center gap-2">
              <Download className="h-4 w-4" />
              Advanced Downloads
            </span>
            <span className="text-xs text-gray-400">
              For experienced users who only require specific reports
            </span>
            {advancedOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>

          {advancedOpen && (
            <div className="mt-3 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
              <AdvancedDownloadButton icon={FileText} label="Executive Summary" />
              <AdvancedDownloadButton icon={FileText} label="Tender Completion Guide" />
              <AdvancedDownloadButton icon={BarChart3} label="Readiness Assessment" onClick={async () => {
                try { await downloadReadinessPdf(jobId, `Readiness_${jobId}.pdf`); } catch {}
              }} />
              <AdvancedDownloadButton icon={FileText} label="Submission Letter" onClick={async () => {
                try { await downloadSubmissionLetter(jobId, `Letter_${jobId}.pdf`); } catch {}
              }} />
              <AdvancedDownloadButton icon={FileCheck} label="Bid Response Roadmap" onClick={async () => {
                try { await downloadRoadmap(jobId, `Roadmap_${jobId}.pdf`); } catch {}
              }} />
              <AdvancedDownloadButton icon={ShieldAlert} label="Processing Audit" onClick={async () => {
                try { await downloadAudit(jobId, `Audit_${jobId}.pdf`); } catch {}
              }} />
              <AdvancedDownloadButton icon={FileSpreadsheet} label="BOQ Excel" onClick={async () => {
                try { await downloadExcelExport(jobId, `${filename ?? 'tender'}_export.xlsx`); } catch {}
              }} />
              <AdvancedDownloadButton icon={Download} label="BOQ CSV" onClick={async () => {
                try { await downloadCsvExport(jobId, `${filename ?? 'tender'}_export.csv`); } catch {}
              }} />
              <AdvancedDownloadButton icon={FileText} label="PDF Report" onClick={async () => {
                try { await downloadPdfReport(jobId, `${filename ?? 'tender'}_report.pdf`); } catch {}
              }} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Advanced Download Button                                          */
/* ------------------------------------------------------------------ */

function AdvancedDownloadButton({
  icon: Icon,
  label,
  onClick,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  onClick?: () => void;
}) {
  const [loading, setLoading] = useState(false);

  const handleClick = async () => {
    if (!onClick) return;
    setLoading(true);
    try {
      await onClick();
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={handleClick}
      disabled={loading || !onClick}
      className="inline-flex items-center gap-2 px-3 py-2.5 text-xs font-medium rounded-lg border border-gray-200 bg-white text-gray-700 hover:bg-gray-50 hover:border-gray-300 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm"
    >
      {loading ? (
        <RefreshCw className="h-3.5 w-3.5 animate-spin text-gray-400" />
      ) : (
        <Icon className="h-3.5 w-3.5 text-gray-500" />
      )}
      {loading ? 'Downloading...' : label}
    </button>
  );
}

/* ------------------------------------------------------------------ */
/*  Main ResultViewer                                                 */
/* ------------------------------------------------------------------ */

export default function ResultViewer({ result }: ResultViewerProps) {
  const [activeTab, setActiveTab] = useState<'result' | 'audit'>('result');

  /* ── Derived values ────────────────────────────────────────────── */
  const canExport = result.status === 'completed' || result.status === 'partial_success';
  const hasBOQ = result.boq_items && result.boq_items.length > 0;
  const hasWorkforce = result.detected_workforce && Object.keys(result.detected_workforce).length > 0;
  const hasSchedule = result.detected_schedule && Object.keys(result.detected_schedule).length > 0;

  const overallConfidence = result.boq_confidence != null
    ? parseFloat(result.boq_confidence.replace('%', '')) / 100
    : null;

  const totalBOQ = hasBOQ
    ? result.boq_items.reduce((sum, item) => sum + (item.amount ?? 0), 0)
    : 0;

  /* ── Risk assessment ──────────────────────────────────────────── */
  const getRiskAssessment = () => {
    const scorePercent = overallConfidence != null ? overallConfidence * 100 : 0;
    let riskLevel, bgClass, borderClass, textClass, summary;
    if (scorePercent < 40) {
      riskLevel = 'HIGH RISK';
      bgClass = 'bg-red-50';
      borderClass = 'border-red-200';
      textClass = 'text-red-800';
      summary = 'High risk detected: Significant manual verification of pricing required.';
    } else if (scorePercent < 70) {
      riskLevel = 'MEDIUM RISK';
      bgClass = 'bg-amber-50';
      borderClass = 'border-amber-200';
      textClass = 'text-amber-800';
      summary = 'Medium risk detected: Some manual verification recommended.';
    } else {
      riskLevel = 'LOW RISK';
      bgClass = 'bg-green-50';
      borderClass = 'border-green-200';
      textClass = 'text-green-800';
      summary = 'Low risk detected: Extraction completed with high confidence.';
    }
    return { riskLevel, bgClass, borderClass, textClass, summary, scorePercent };
  };

  /* ── Failed state ───────────────────────────────────────────────── */
  if (result.status === 'failed') {
    return (
      <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
        <div className="px-6 py-5 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-gray-400" />
            <h2 className="text-lg font-semibold text-gray-900">Result</h2>
          </div>
        </div>
        <div className="px-6 py-5 space-y-4">
          <StatusBanner result={result} />
          {result.warnings.length > 0 && <WarningPanel warnings={result.warnings} />}
          {result.filename && (
            <p className="text-sm text-gray-500">File: <span className="font-medium text-gray-700">{result.filename}</span></p>
          )}
        </div>
      </div>
    );
  }

  /* ── Main return ────────────────────────────────────────────────── */
  return (
    <div className="space-y-6">
      {/* ── Tab Navigation ──────────────────────────────────────── */}
      <div className="flex border-b border-gray-200">
        <button
          onClick={() => setActiveTab('result')}
          className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'result' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
          }`}
        >
          <BarChart3 className="h-4 w-4 inline mr-1.5" />
          Processing Result
        </button>
        <button
          onClick={() => setActiveTab('audit')}
          className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'audit' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
          }`}
        >
          <Shield className="h-4 w-4 inline mr-1.5" />
          Processing Audit
        </button>
      </div>

      {/* ── Audit Tab ───────────────────────────────────────────── */}
      {activeTab === 'audit' && <ProcessingAudit jobId={result.job_id} />}

      {/* ── Result Tab ──────────────────────────────────────────── */}
      {activeTab === 'result' && (
        <>
          {/* ── PRIMARY: Submission Package ──────────────────────── */}
          {canExport && (
            <SubmissionPackageSection
              jobId={result.job_id}
              filename={result.filename}
              canExport={canExport}
            />
          )}

          {/* ── Instant Risk Assessment ─────────────────────────── */}
          {canExport && (
            <div className={`rounded-xl border p-6 shadow-lg ${getRiskAssessment().bgClass} ${getRiskAssessment().borderClass}`}>
              <div className="flex flex-col md:flex-row items-center justify-between gap-6">
                <div className="flex-1">
                  <h2 className={`text-2xl font-black uppercase tracking-wider ${getRiskAssessment().textClass}`}>
                    {getRiskAssessment().riskLevel}
                  </h2>
                  <p className={`text-lg font-semibold mt-2 ${getRiskAssessment().textClass}`}>
                    Overall Confidence Score: {Math.round(getRiskAssessment().scorePercent)}%
                  </p>
                  <p className="text-sm mt-1 text-gray-700">{getRiskAssessment().summary}</p>
                  {result?.win_probability_index != null && (
                    <div className="mt-4 pt-4 border-t border-gray-200">
                      <p className="text-lg font-bold text-gray-800">Win Probability Index: {Math.round(result.win_probability_index)}%</p>
                      <p className="text-sm text-gray-600 mt-1">{result.win_probability_explanation}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* ── Compliance Summary ─────────────────────────────── */}
          {result?.critical_traps && result.critical_traps.length > 0 && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-6">
              <h3 className="text-xl font-bold text-red-800 mb-4 flex items-center gap-2">
                <AlertTriangle className="h-6 w-6" />
                Critical Disqualification Traps
              </h3>
              <ul className="space-y-2">
                {result.critical_traps.map((trap, index) => (
                  <li key={index} className="flex items-start gap-3">
                    <div className="mt-1 h-2 w-2 rounded-full bg-red-600 flex-shrink-0" />
                    <p className="text-red-600 font-bold">{trap}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {result?.compliance_gaps && result.compliance_gaps.length > 0 && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-6">
              <h3 className="text-xl font-bold text-amber-800 mb-4 flex items-center gap-2">
                <CheckCircle2 className="h-6 w-6" />
                Compliance Gaps (Standard SME Profile)
              </h3>
              <ul className="space-y-2">
                {result.compliance_gaps.map((gap, index) => (
                  <li key={index} className="flex items-start gap-3">
                    <div className="mt-1 h-2 w-2 rounded-full bg-amber-600 flex-shrink-0" />
                    <p className="text-amber-700">{gap}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* ── Processing Result Card ──────────────────────────── */}
          <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
            <div className="px-6 py-5 border-b border-gray-200 flex items-center gap-3">
              <div className="h-10 w-10 rounded-xl bg-blue-600 flex items-center justify-center">
                <BarChart3 className="h-5 w-5 text-white" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-gray-900">Processing Result</h2>
                {result.filename && <p className="text-sm text-gray-500">{result.filename}</p>}
              </div>
            </div>

            <div className="px-6 py-5 space-y-5">
              <StatusBanner result={result} />
              {result.warnings.length > 0 && <WarningPanel warnings={result.warnings} />}
              {result.failed_stages.length > 0 && <FailedStagesPanel failedStages={result.failed_stages} />}
              {(result.completed_stages.length > 0 || result.failed_stages.length > 0) && (
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Processing Stages</h3>
                  <StageBadges completed={result.completed_stages} failed={result.failed_stages} />
                </div>
              )}
            </div>
          </div>

          {/* ── Executive Summary Cards ─────────────────────────── */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <MetricCard icon={Building2} label="Sector" value={result.detected_sector ?? 'Not detected'} />
            <MetricCard icon={BarChart3} label="Confidence"
              value={overallConfidence != null ? `${Math.round(overallConfidence * 100)}%` : result.boq_confidence ?? 'Required field missing: please update project details'}
              color={overallConfidence != null && overallConfidence >= 0.7 ? 'text-emerald-700' : overallConfidence != null && overallConfidence >= 0.5 ? 'text-amber-700' : 'text-gray-700'} />
            <MetricCard icon={DollarSign} label="BOQ Total" value={hasBOQ ? formatCurrency(totalBOQ) : 'Required field missing: please update project details'} />
            <MetricCard icon={Clock} label="Duration" value={result.detected_duration_months != null ? `${result.detected_duration_months} mo` : 'Required field missing: please update project details'} />
            <MetricCard icon={Users} label="Workforce" value={hasWorkforce ? String(
              (result.detected_workforce as Record<string, { count?: number }>).total_personnel ?? Object.keys(result.detected_workforce).length) : 'Required field missing: please update project details'} />
            <MetricCard icon={MapPin} label="Locations" value={result.detected_locations.length > 0 ? String(result.detected_locations.length) : 'None'}
              subtext={result.detected_locations.length > 0 ? result.detected_locations.slice(0, 2).join(', ') + (result.detected_locations.length > 2 ? '...' : '') : undefined} />
          </div>

          {/* ── Confidence Breakdown ────────────────────────────── */}
          {overallConfidence != null && (
            <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
              <div className="flex items-center gap-2 mb-3">
                <div className="h-7 w-7 rounded-lg bg-blue-50 flex items-center justify-center">
                  <BarChart3 className="h-3.5 w-3.5 text-blue-600" />
                </div>
                <h3 className="text-sm font-semibold text-gray-900">Confidence Score</h3>
              </div>
              <div className="flex items-center gap-3 mb-3">
                <div className="flex-1 h-2.5 rounded-full bg-gray-200 overflow-hidden">
                  <div className={`h-full rounded-full ${getConfidenceBarColor(overallConfidence)}`}
                    style={{ width: `${Math.round(overallConfidence * 100)}%` }} />
                </div>
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-md text-sm font-bold ${getConfidenceColor(overallConfidence)}`}>
                  {Math.round(overallConfidence * 100)}%
                </span>
              </div>
              <p className="text-xs text-gray-400">
                Confidence scores reflect processing reliability, not factual correctness. Always review outputs before use.
              </p>
            </div>
          )}

          {/* ── Two Column: Workforce + Schedule ────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className={`rounded-xl border border-gray-200 bg-white p-5 shadow-sm ${!hasWorkforce ? 'opacity-60' : ''}`}>
              <div className="flex items-center gap-2 mb-4">
                <div className="h-8 w-8 rounded-lg bg-violet-50 flex items-center justify-center">
                  <Users className="h-4 w-4 text-violet-600" />
                </div>
                <h3 className="text-sm font-semibold text-gray-900">Workforce Requirements</h3>
              </div>
              {hasWorkforce ? (
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(result.detected_workforce).filter(([key]) => key !== 'total_personnel').map(([category, info]) => {
                    const data = info as { count?: number; source?: string };
                    return (
                      <div key={category} className="rounded-lg border border-gray-100 bg-gray-50 p-3">
                        <p className="text-xs font-medium text-gray-500 capitalize mb-1">{category.replace(/_/g, ' ')}</p>
                        <p className="text-lg font-bold text-gray-900">{data.count ?? '-'}</p>
                        {data.source && <p className="text-xs text-gray-400 mt-0.5">Source: {data.source}</p>}
                      </div>
                    );
                  })}
                </div>
              ) : <p className="text-sm text-gray-400 italic">Not available</p>}
            </div>
            <div className={`rounded-xl border border-gray-200 bg-white p-5 shadow-sm ${!hasSchedule ? 'opacity-60' : ''}`}>
              <div className="flex items-center gap-2 mb-4">
                <div className="h-8 w-8 rounded-lg bg-amber-50 flex items-center justify-center">
                  <Calendar className="h-4 w-4 text-amber-600" />
                </div>
                <h3 className="text-sm font-semibold text-gray-900">Project Schedule</h3>
              </div>
              {hasSchedule ? (
                <dl className="space-y-2">
                  {Object.entries(result.detected_schedule).map(([key, value]) => (
                    <div key={key} className="flex justify-between py-1.5 border-b border-gray-100 last:border-0">
                      <dt className="text-sm text-gray-500 capitalize">{key.replace(/_/g, ' ')}</dt>
                      <dd className="text-sm font-medium text-gray-900">{String(value)}</dd>
                    </div>
                  ))}
                </dl>
              ) : <p className="text-sm text-gray-400 italic">Not available</p>}
            </div>
          </div>

          {/* ── BOQ Table ───────────────────────────────────────── */}
          <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
            <div className="px-6 py-4 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="h-8 w-8 rounded-lg bg-gray-100 flex items-center justify-center">
                    <FileText className="h-4 w-4 text-gray-600" />
                  </div>
                  <h3 className="text-sm font-semibold text-gray-900">Bill of Quantities</h3>
                </div>
                {hasBOQ && <span className="text-xs text-gray-400">{result.boq_items.length} item{result.boq_items.length !== 1 ? 's' : ''}</span>}
              </div>
            </div>
            <div className="px-6 py-4">
              {hasBOQ ? <BOQTable items={result.boq_items} /> : <p className="text-sm text-gray-400 italic">No BOQ items extracted</p>}
            </div>
          </div>

          {/* ── Pricing ─────────────────────────────────────────── */}
          {result.pricing_status !== 'failed' && result.pricing_result ? <PricingSection result={result} /> : null}
          {result.status === 'partial_success' && (result.pricing_status === 'failed' || !result.pricing_result) && <PricingSection result={result} />}

          {/* ── Extraction info ─────────────────────────────────── */}
          {(result.extraction_method || result.pipeline_version) && (
            <div className="text-xs text-gray-400 flex flex-wrap gap-x-4 gap-y-1 px-1">
              {result.extraction_method && <span className="inline-flex items-center gap-1"><HardDrive className="h-3 w-3" /> Method: {result.extraction_method}</span>}
              {result.pipeline_version && <span className="inline-flex items-center gap-1"><RefreshCw className="h-3 w-3" /> Pipeline: {result.pipeline_version}</span>}
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Helper: format file size                                          */
/* ------------------------------------------------------------------ */

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}