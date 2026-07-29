import { useCallback, useRef, useState } from 'react';
import type { ReactNode, RefObject } from 'react';
import type { NavigateFunction } from 'react-router-dom';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  BarChart3,
  Building2,
  CalendarDays,
  CheckCircle2,
  CircleDollarSign,
  ClipboardCheck,
  Download,
  Eye,
  FileSearch,
  FileSpreadsheet,
  FileText,
  Info,
  ListChecks,
  Lock,
  MapPin,
  RefreshCw,
  ShieldCheck,
  Timer,
  Upload,
  Users,
} from 'lucide-react';
import { demoResult, DEMO_LABEL } from '../demo/demoResult';
import { SAMPLE_TENDERS, demoSimEngine } from '../demo/demoEngine';
import type { SampleTender } from '../demo/demoEngine';
import DemoProcessingAnimation from '../components/demo/DemoProcessingAnimation';
import AppFooter from '../components/layout/AppFooter';
import PublicHeader from '../components/layout/PublicHeader';

type ViewMode = 'executive' | 'technical';
type DemoPhase = 'welcome' | 'processing' | 'result';
type ResultSource =
  | { kind: 'sample'; tender: SampleTender }
  | { kind: 'upload'; fileName: string; representativeTender?: SampleTender };

interface BoqItem {
  item_no: string | null;
  description: string;
  quantity: number | null;
  unit: string | null;
  rate: number | null;
  amount: number | null;
}

interface PricingResult {
  total_boq_amount?: number;
  contingency_10_percent?: number;
  escalation_8_percent?: number;
  professional_fees?: number;
  total_estimated_amount?: number;
  currency?: string;
  pricing_mode?: string;
  markups_applied?: boolean;
  item_count?: number;
}

interface WorkforceItem {
  count?: number;
  source?: string;
}

interface SchedulePhase {
  phase: string;
  duration: string;
}

interface DemoResultData {
  job_id: string;
  status: string;
  filename: string;
  completed_stages: string[];
  failed_stages: string[];
  metadata: Record<string, unknown>;
  detected_sector: string | null;
  detected_duration_months: number | null;
  detected_locations: string[];
  detected_workforce: Record<string, WorkforceItem | number | undefined>;
  detected_schedule: {
    start_date?: string;
    phases?: SchedulePhase[];
  };
  boq_items: BoqItem[];
  boq_confidence: string | null;
  pricing_result: PricingResult | null;
  pricing_status: string | null;
  pricing_unavailable_reason: string | null;
  extraction_method: string | null;
  pipeline_version: string | null;
  warnings: string[];
  confidence_scores: {
    overall: number;
    boq_extraction: number;
    workforce: number;
    sector: number;
    pricing: number;
  };
  executive_summary: string;
}

const HONESTY_POINTS = [
  'Demo results are pre-generated for speed.',
  'Uploaded PDFs are not sent to the backend on this page.',
  'Warnings, failed stages, and confidence scores stay visible.',
];

function formatCurrency(amount: number, currency = 'ZAR'): string {
  return new Intl.NumberFormat('en-ZA', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function normalizeText(value: string | null | undefined): string {
  if (!value) return '';

  let repaired = value;
  try {
    const bytes = Uint8Array.from(value, (char) => char.charCodeAt(0) & 0xff);
    const decoded = new TextDecoder('utf-8', { fatal: false }).decode(bytes);
    if (!decoded.includes('\uFFFD') && /[\u2013\u2014\u2022\u00B2\u00B3]/.test(decoded)) {
      repaired = decoded;
    }
  } catch {
    repaired = value;
  }

  return repaired
    .replace(/\u2014|\u2013/g, '-')
    .replace(/\u2022/g, '-')
    .replace(/\u2019/g, "'")
    .replace(/\u201C|\u201D/g, '"')
    .replace(/\u2026/g, '...')
    .replace(/\u26A0\uFE0F/g, 'Warning:')
    .replace(/\u00B2/g, '2')
    .replace(/\u00B3/g, '3')
    .replace(/\u00B7/g, '.')
    .replace(/\uFE0F/g, '')
    .replace(/\s+-\s+/g, ' - ')
    .trim();
}

function titleCase(value: string | null | undefined): string {
  return normalizeText(value)
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function getPricing(result: DemoResultData): PricingResult {
  return result.pricing_result ?? {};
}

function getTotalPersonnel(result: DemoResultData): number {
  const total = result.detected_workforce.total_personnel;
  return typeof total === 'number' ? total : 0;
}

function getCurrency(result: DemoResultData): string {
  return getPricing(result).currency ?? 'ZAR';
}

function findTenderByResultPath(resultPath: string): SampleTender | undefined {
  return SAMPLE_TENDERS.find((tender) => tender.resultFile === resultPath);
}

function mergeDisplayFilename(data: DemoResultData, source: ResultSource): DemoResultData {
  if (source.kind !== 'upload') return data;
  return {
    ...data,
    filename: source.fileName,
  };
}

export default function DemoPage() {
  const navigate = useNavigate();
  const [phase, setPhase] = useState<DemoPhase>('welcome');
  const [viewMode, setViewMode] = useState<ViewMode>('executive');
  const [result, setResult] = useState<DemoResultData | null>(null);
  const [resultSource, setResultSource] = useState<ResultSource | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSelectSample = useCallback((tender: SampleTender) => {
    setResult(null);
    setUploadError(null);
    setResultSource({ kind: 'sample', tender });
    setViewMode('executive');
    setPhase('processing');
    demoSimEngine.startSimulation(tender.fileName);
  }, []);

  const handleUpload = useCallback(() => {
    const file = fileInputRef.current?.files?.[0];

    if (!file) {
      setUploadError('Please select a PDF file first.');
      return;
    }

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setUploadError('Only PDF files are supported in demo mode.');
      return;
    }

    if (file.size > 50 * 1024 * 1024) {
      setUploadError('File too large. Demo uploads accept PDFs up to 50 MB.');
      return;
    }

    setResult(null);
    setUploadError(null);
    setResultSource({ kind: 'upload', fileName: file.name });
    setViewMode('executive');
    setPhase('processing');
    demoSimEngine.startSimulation(file.name);

    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, []);

  const handleProcessingComplete = useCallback(async () => {
    const source = resultSource;
    let resultPath: string;
    let finalSource = source;

    if (source?.kind === 'sample') {
      resultPath = source.tender.resultFile;
    } else {
      resultPath = demoSimEngine.getRandomDemoResultPath();
      finalSource = {
        kind: 'upload',
        fileName: source?.kind === 'upload' ? source.fileName : 'Uploaded tender.pdf',
        representativeTender: findTenderByResultPath(resultPath),
      };
      setResultSource(finalSource);
    }

    try {
      const data = (await demoSimEngine.loadDemoResult(resultPath)) as DemoResultData;
      setResult(mergeDisplayFilename(data, finalSource ?? { kind: 'upload', fileName: data.filename }));
    } catch {
      setResult(mergeDisplayFilename(demoResult as unknown as DemoResultData, finalSource ?? { kind: 'upload', fileName: demoResult.filename }));
    } finally {
      setPhase('result');
    }
  }, [resultSource]);

  const handleReset = useCallback(() => {
    demoSimEngine.reset();
    setPhase('welcome');
    setResult(null);
    setResultSource(null);
    setUploadError(null);
    setViewMode('executive');
  }, []);

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <PublicHeader />

      <div className="border-b border-amber-200 bg-amber-50">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm text-amber-900 sm:px-6 lg:px-8">
          <div className="flex items-start gap-2">
            <Info className="mt-0.5 h-4 w-4 flex-none" />
            <p>
              <span className="font-bold">{DEMO_LABEL}:</span> this page uses representative mock results so you can evaluate the workflow immediately.
            </p>
          </div>
          <span className="text-xs font-semibold uppercase tracking-wide text-amber-700">Honesty Architecture</span>
        </div>
      </div>

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 lg:px-8">
        {phase === 'welcome' && (
          <WelcomeView
            fileInputRef={fileInputRef}
            onSelectSample={handleSelectSample}
            onUpload={handleUpload}
            uploadError={uploadError}
          />
        )}

        {phase === 'processing' && <ProcessingView resultSource={resultSource} onComplete={handleProcessingComplete} />}

        {phase === 'result' && result && (
          <ResultView
            result={result}
            resultSource={resultSource}
            viewMode={viewMode}
            setViewMode={setViewMode}
            onReset={handleReset}
          />
        )}
      </main>

      {phase === 'result' && <ResultCta navigate={navigate} />}
      <AppFooter />
    </div>
  );
}

function WelcomeView({
  fileInputRef,
  onSelectSample,
  onUpload,
  uploadError,
}: {
  fileInputRef: RefObject<HTMLInputElement | null>;
  onSelectSample: (tender: SampleTender) => void;
  onUpload: () => void;
  uploadError: string | null;
}) {
  return (
    <div className="space-y-8">
      <section className="grid gap-8 lg:grid-cols-[minmax(0,1.05fr)_minmax(360px,0.95fr)] lg:items-end">
        <div className="space-y-6">
          <div className="inline-flex items-center gap-2 rounded-md border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-bold uppercase tracking-wide text-blue-700">
            <BadgeCheck className="h-4 w-4" />
            Live-feeling demo, mock-only processing
          </div>
          <div className="max-w-3xl">
            <h1 className="text-4xl font-bold tracking-tight text-slate-950 sm:text-5xl">
              See exactly what Tender Engine would extract from a tender PDF.
            </h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600 sm:text-lg">
              Choose a representative sample or upload a PDF name into demo mode. The page simulates the pipeline, then reveals BOQ lines, pricing, warnings, confidence scores, and review signals without requiring an account.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            {HONESTY_POINTS.map((point) => (
              <div key={point} className="rounded-md border border-slate-200 bg-white p-4 shadow-sm">
                <ShieldCheck className="h-5 w-5 text-emerald-600" />
                <p className="mt-2 text-sm font-medium leading-5 text-slate-700">{point}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-start gap-3">
            <div className="rounded-md bg-slate-900 p-2 text-white">
              <FileSearch className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-950">What this demo proves</h2>
              <p className="mt-1 text-sm leading-6 text-slate-600">
                The useful part is not pretending every PDF is perfect. It is showing where extraction is strong, where the model is cautious, and what a reviewer should check next.
              </p>
            </div>
          </div>
          <div className="mt-5 grid grid-cols-2 gap-3">
            <ProofTile label="Sample tenders" value={SAMPLE_TENDERS.length.toString()} />
            <ProofTile label="Pipeline stages" value="8" />
            <ProofTile label="Mock latency" value="~6 sec" />
            <ProofTile label="Backend calls" value="0" />
          </div>
        </div>
      </section>

      <section>
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold text-slate-950">Choose a sample PDF</h2>
            <p className="mt-1 text-sm text-slate-500">Each sample is mapped to a pre-generated result profile.</p>
          </div>
          <span className="rounded-md bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">No signup. No waitlist.</span>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
          {SAMPLE_TENDERS.map((tender) => (
            <SampleTenderCard key={tender.id} tender={tender} onSelect={onSelectSample} />
          ))}
        </div>
      </section>

      <section className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="rounded-lg border-2 border-dashed border-slate-300 bg-white p-6 shadow-sm">
          <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
            <div className="max-w-2xl">
              <div className="flex items-center gap-2">
                <Upload className="h-5 w-5 text-blue-700" />
                <h2 className="text-lg font-bold text-slate-950">Upload your own PDF</h2>
              </div>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                Demo upload accepts a local PDF, then runs the same simulated pipeline using a representative mock result. Your file is not sent to the backend from this public page.
              </p>
            </div>

            <div className="w-full max-w-md space-y-3">
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,application/pdf"
                className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-blue-50 file:px-4 file:py-2.5 file:text-sm file:font-bold file:text-blue-700 hover:file:bg-blue-100"
              />
              <button
                onClick={onUpload}
                className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-blue-700 px-4 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-blue-800"
              >
                <FileSearch className="h-4 w-4" />
                Run demo processing
              </button>
              {uploadError && (
                <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm font-semibold text-red-700">{uploadError}</p>
              )}
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 bg-slate-900 p-5 text-white shadow-sm">
          <h3 className="text-sm font-bold uppercase tracking-wide text-slate-300">Demo limits</h3>
          <ul className="mt-4 space-y-3 text-sm leading-6 text-slate-200">
            <li className="flex gap-2"><CheckCircle2 className="mt-1 h-4 w-4 flex-none text-emerald-400" /> Shows the real product flow and review surfaces.</li>
            <li className="flex gap-2"><CheckCircle2 className="mt-1 h-4 w-4 flex-none text-emerald-400" /> Uses pre-generated BOQ, pricing, and confidence data.</li>
            <li className="flex gap-2"><AlertTriangle className="mt-1 h-4 w-4 flex-none text-amber-300" /> Does not process private tender contents until a user signs in.</li>
          </ul>
        </div>
      </section>
    </div>
  );
}

function SampleTenderCard({ tender, onSelect }: { tender: SampleTender; onSelect: (tender: SampleTender) => void }) {
  const badgeClass =
    tender.badge === 'clean'
      ? 'bg-emerald-50 text-emerald-700 ring-emerald-200'
      : tender.badge === 'partial'
        ? 'bg-amber-50 text-amber-700 ring-amber-200'
        : 'bg-violet-50 text-violet-700 ring-violet-200';

  return (
    <button
      onClick={() => onSelect(tender)}
      className="group flex h-full flex-col rounded-lg border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-blue-300 hover:shadow-md"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="rounded-md bg-blue-50 p-2 text-blue-700 transition group-hover:bg-blue-100">
          <FileText className="h-5 w-5" />
        </div>
        <span className={`rounded-md px-2 py-1 text-xs font-bold ring-1 ${badgeClass}`}>{tender.badgeLabel}</span>
      </div>
      <h3 className="mt-4 text-sm font-bold leading-5 text-slate-950 group-hover:text-blue-700">{tender.title}</h3>
      <p className="mt-1 truncate font-mono text-xs text-slate-400">{tender.fileName}</p>
      <p className="mt-2 line-clamp-3 text-xs leading-5 text-slate-500">{normalizeText(tender.description)}</p>
      <div className="mt-auto pt-4">
        <div className="flex flex-wrap gap-2 text-xs font-semibold text-slate-500">
          <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-1">
            <Building2 className="h-3.5 w-3.5" />
            {tender.sector}
          </span>
          <span className="rounded-md bg-slate-100 px-2 py-1">{tender.budget}</span>
        </div>
        <span className="mt-4 inline-flex items-center gap-1 text-xs font-bold text-blue-700">
          Process sample <ArrowRight className="h-3.5 w-3.5" />
        </span>
      </div>
    </button>
  );
}

function ProcessingView({ resultSource, onComplete }: { resultSource: ResultSource | null; onComplete: () => void }) {
  const label = resultSource?.kind === 'sample' ? resultSource.tender.title : resultSource?.kind === 'upload' ? resultSource.fileName : 'Tender PDF';

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-start gap-3">
          <div className="rounded-md bg-blue-50 p-2 text-blue-700">
            <Timer className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-950">Simulating Tender Engine processing</h1>
            <p className="mt-1 text-sm leading-6 text-slate-600">
              Processing <span className="font-semibold text-slate-900">{label}</span>. This is a client-side demo animation connected to pre-generated results.
            </p>
          </div>
        </div>
      </div>
      <DemoProcessingAnimation onComplete={onComplete} />
    </div>
  );
}

function ResultView({
  result,
  resultSource,
  viewMode,
  setViewMode,
  onReset,
}: {
  result: DemoResultData;
  resultSource: ResultSource | null;
  viewMode: ViewMode;
  setViewMode: (mode: ViewMode) => void;
  onReset: () => void;
}) {
  const pricing = getPricing(result);
  const currency = getCurrency(result);
  const statusLabel = result.failed_stages.length > 0 ? 'Needs review' : result.status === 'partial_success' ? 'Partial success' : 'Complete';
  const statusClass = result.failed_stages.length > 0 || result.status === 'partial_success'
    ? 'bg-amber-50 text-amber-700 ring-amber-200'
    : 'bg-emerald-50 text-emerald-700 ring-emerald-200';

  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <div className="flex flex-wrap items-center gap-2">
              <span className={`rounded-md px-2.5 py-1 text-xs font-bold ring-1 ${statusClass}`}>{statusLabel}</span>
              <span className="rounded-md bg-blue-50 px-2.5 py-1 text-xs font-bold text-blue-700 ring-1 ring-blue-200">{DEMO_LABEL}</span>
            </div>
            <h1 className="mt-3 text-2xl font-bold text-slate-950 sm:text-3xl">{normalizeText(result.filename)}</h1>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              {resultSource?.kind === 'upload'
                ? `Uploaded-file demo: the filename is yours, while the displayed extraction is representative sample data${resultSource.representativeTender ? ` based on ${resultSource.representativeTender.title}` : ''}.`
                : `Sample result profile: ${resultSource?.kind === 'sample' ? resultSource.tender.title : 'Tender Engine sample'}.`}
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              onClick={onReset}
              className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-blue-300 hover:bg-blue-50"
            >
              <RefreshCw className="h-4 w-4" />
              Try another
            </button>
            <button
              disabled
              title="Available in the signed-in product"
              className="inline-flex cursor-not-allowed items-center gap-2 rounded-md border border-slate-200 bg-slate-100 px-3 py-2 text-sm font-semibold text-slate-400"
            >
              <Download className="h-4 w-4" />
              Export PDF
            </button>
            <button
              disabled
              title="Available in the signed-in product"
              className="inline-flex cursor-not-allowed items-center gap-2 rounded-md border border-slate-200 bg-slate-100 px-3 py-2 text-sm font-semibold text-slate-400"
            >
              <FileSpreadsheet className="h-4 w-4" />
              Export XLSX
            </button>
          </div>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            label="Estimated total"
            value={formatCurrency(pricing.total_estimated_amount ?? 0, currency)}
            subtext="Incl. contingency, escalation, fees"
            icon={<CircleDollarSign className="h-5 w-5" />}
            accent="emerald"
          />
          <MetricCard
            label="BOQ extracted"
            value={`${result.boq_items.length} items`}
            subtext={`${titleCase(result.boq_confidence)} confidence`}
            icon={<ListChecks className="h-5 w-5" />}
            accent="violet"
          />
          <MetricCard
            label="Workforce"
            value={`${getTotalPersonnel(result)} people`}
            subtext="Extracted plus inferred roles"
            icon={<Users className="h-5 w-5" />}
            accent="amber"
          />
          <MetricCard
            label="Overall confidence"
            value={formatPercent(result.confidence_scores.overall)}
            subtext={`${result.warnings.length} warning${result.warnings.length === 1 ? '' : 's'} surfaced`}
            icon={<ShieldCheck className="h-5 w-5" />}
            accent="blue"
          />
        </div>
      </section>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="inline-flex w-full rounded-md border border-slate-200 bg-white p-1 shadow-sm sm:w-auto">
          <TabButton active={viewMode === 'executive'} onClick={() => setViewMode('executive')} icon={<BarChart3 className="h-4 w-4" />} label="Executive" />
          <TabButton active={viewMode === 'technical'} onClick={() => setViewMode('technical')} icon={<ClipboardCheck className="h-4 w-4" />} label="Technical" />
        </div>
        <div className="flex items-center gap-2 text-xs font-medium text-slate-500">
          <Lock className="h-4 w-4" />
          Signed-in accounts can export and process private PDFs.
        </div>
      </div>

      {viewMode === 'executive' ? <ExecutiveView result={result} /> : <TechnicalView result={result} />}
    </div>
  );
}

function ExecutiveView({ result }: { result: DemoResultData }) {
  const pricing = getPricing(result);
  const currency = getCurrency(result);

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
      <div className="space-y-6">
        <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-start gap-3">
            <div className="rounded-md bg-blue-50 p-2 text-blue-700">
              <Eye className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-950">Executive Summary</h2>
              <p className="mt-1 text-sm text-slate-500">A concise, review-ready interpretation of the extracted tender.</p>
            </div>
          </div>
          <div className="mt-5 whitespace-pre-line text-sm leading-7 text-slate-700">
            {normalizeText(result.executive_summary)}
          </div>
        </section>

        <ReviewSignals result={result} />
      </div>

      <aside className="space-y-6">
        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="flex items-center gap-2 text-base font-bold text-slate-950">
            <ShieldCheck className="h-5 w-5 text-emerald-600" />
            Confidence Scores
          </h2>
          <p className="mt-1 text-sm leading-6 text-slate-500">Every stage carries its own confidence. Low scores are visible by design.</p>
          <div className="mt-5 space-y-4">
            <ConfidenceRow label="Overall" value={result.confidence_scores.overall} />
            <ConfidenceRow label="BOQ extraction" value={result.confidence_scores.boq_extraction} />
            <ConfidenceRow label="Workforce" value={result.confidence_scores.workforce} />
            <ConfidenceRow label="Sector detection" value={result.confidence_scores.sector} />
            <ConfidenceRow label="Pricing" value={result.confidence_scores.pricing} />
          </div>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="flex items-center gap-2 text-base font-bold text-slate-950">
            <MapPin className="h-5 w-5 text-blue-700" />
            Project Profile
          </h2>
          <dl className="mt-4 space-y-3 text-sm">
            <ProfileRow label="Sector" value={normalizeText(result.detected_sector) || 'Not detected'} />
            <ProfileRow label="Duration" value={result.detected_duration_months ? `${result.detected_duration_months} months` : 'Not detected'} />
            <ProfileRow label="Locations" value={result.detected_locations.map(normalizeText).join(', ') || 'Not detected'} />
            <ProfileRow label="Method" value={titleCase(result.extraction_method)} />
            <ProfileRow label="Pipeline" value={result.pipeline_version ?? 'Unknown'} />
          </dl>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="flex items-center gap-2 text-base font-bold text-slate-950">
            <CircleDollarSign className="h-5 w-5 text-emerald-600" />
            Pricing Snapshot
          </h2>
          <div className="mt-4 space-y-3 text-sm">
            <PriceRow label="BOQ subtotal" value={pricing.total_boq_amount ?? 0} currency={currency} />
            <PriceRow label="Contingency" value={pricing.contingency_10_percent ?? 0} currency={currency} />
            <PriceRow label="Escalation" value={pricing.escalation_8_percent ?? 0} currency={currency} />
            <PriceRow label="Professional fees" value={pricing.professional_fees ?? 0} currency={currency} />
            <div className="border-t border-slate-200 pt-3">
              <PriceRow label="Estimated total" value={pricing.total_estimated_amount ?? 0} currency={currency} strong />
            </div>
          </div>
        </section>
      </aside>
    </div>
  );
}

function TechnicalView({ result }: { result: DemoResultData }) {
  const pricing = getPricing(result);
  const currency = getCurrency(result);
  const workforce = Object.entries(result.detected_workforce).filter(([key]) => key !== 'total_personnel') as Array<[string, WorkforceItem]>;

  return (
    <div className="space-y-6">
      <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-slate-50 px-5 py-4">
          <div>
            <h2 className="flex items-center gap-2 text-lg font-bold text-slate-950">
              <ListChecks className="h-5 w-5 text-violet-700" />
              Bill of Quantities
            </h2>
            <p className="mt-1 text-sm text-slate-500">{result.boq_items.length} extracted line items with quantities, rates, and amounts.</p>
          </div>
          <span className="rounded-md bg-white px-2.5 py-1 text-xs font-bold text-slate-600 ring-1 ring-slate-200">
            {titleCase(result.boq_confidence)} confidence
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-white">
              <tr>
                <TableHead>Item</TableHead>
                <TableHead>Description</TableHead>
                <TableHead align="right">Qty</TableHead>
                <TableHead align="right">Unit</TableHead>
                <TableHead align="right">Rate</TableHead>
                <TableHead align="right">Amount</TableHead>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {result.boq_items.map((item, index) => (
                <tr key={`${item.item_no}-${index}`} className="transition hover:bg-blue-50/50">
                  <TableCell muted mono>{item.item_no ?? '-'}</TableCell>
                  <TableCell>{normalizeText(item.description)}</TableCell>
                  <TableCell align="right">{item.quantity?.toLocaleString('en-ZA') ?? '-'}</TableCell>
                  <TableCell align="right" muted>{normalizeText(item.unit) || '-'}</TableCell>
                  <TableCell align="right">{formatCurrency(item.rate ?? 0, currency)}</TableCell>
                  <TableCell align="right" strong>{formatCurrency(item.amount ?? 0, currency)}</TableCell>
                </tr>
              ))}
            </tbody>
            <tfoot className="bg-slate-50">
              <tr>
                <td colSpan={5} className="px-4 py-4 text-right text-sm font-bold text-slate-700">Total BOQ Amount</td>
                <td className="px-4 py-4 text-right text-sm font-bold tabular-nums text-slate-950">
                  {formatCurrency(pricing.total_boq_amount ?? 0, currency)}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="flex items-center gap-2 text-lg font-bold text-slate-950">
            <Users className="h-5 w-5 text-amber-600" />
            Workforce Requirements
          </h2>
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            {workforce.map(([role, data]) => (
              <div key={role} className="rounded-md border border-slate-200 bg-slate-50 p-4">
                <div className="text-sm font-bold text-slate-900">{normalizeText(role)}</div>
                <div className="mt-2 flex items-end justify-between gap-3">
                  <span className="text-2xl font-bold tabular-nums text-slate-950">{data.count ?? 0}</span>
                  <span className={`rounded-md px-2 py-1 text-xs font-bold ${data.source === 'extracted' ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
                    {data.source ?? 'unknown'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="flex items-center gap-2 text-lg font-bold text-slate-950">
            <CalendarDays className="h-5 w-5 text-blue-700" />
            Project Schedule
          </h2>
          <p className="mt-1 text-sm text-slate-500">Start: {normalizeText(result.detected_schedule.start_date) || 'Not detected'}</p>
          <div className="mt-5 space-y-3">
            {(result.detected_schedule.phases ?? []).map((phase, index) => (
              <div key={`${phase.phase}-${index}`} className="flex items-center gap-3 rounded-md border border-slate-200 bg-slate-50 px-4 py-3">
                <span className="flex h-7 w-7 flex-none items-center justify-center rounded-md bg-blue-700 text-xs font-bold text-white">{index + 1}</span>
                <span className="flex-1 text-sm font-semibold text-slate-800">{normalizeText(phase.phase)}</span>
                <span className="text-sm font-medium text-slate-500">{normalizeText(phase.duration)}</span>
              </div>
            ))}
            {(result.detected_schedule.phases ?? []).length === 0 && (
              <p className="rounded-md bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-700">Schedule phases were not extracted for this sample.</p>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

function ReviewSignals({ result }: { result: DemoResultData }) {
  const hasWarnings = result.warnings.length > 0;
  const hasFailures = result.failed_stages.length > 0;

  if (!hasWarnings && !hasFailures) {
    return (
      <section className="rounded-lg border border-emerald-200 bg-emerald-50 p-5">
        <div className="flex items-start gap-3">
          <CheckCircle2 className="mt-0.5 h-5 w-5 flex-none text-emerald-700" />
          <div>
            <h2 className="text-base font-bold text-emerald-950">No warnings surfaced</h2>
            <p className="mt-1 text-sm leading-6 text-emerald-800">All simulated stages completed and passed the confidence thresholds for this sample.</p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-amber-200 bg-amber-50 p-5">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 flex-none text-amber-700" />
        <div className="min-w-0 flex-1">
          <h2 className="text-base font-bold text-amber-950">Review signals</h2>
          <p className="mt-1 text-sm leading-6 text-amber-800">Tender Engine should be useful even when it is cautious. These flags stay visible for human review.</p>
          <div className="mt-4 space-y-2">
            {result.warnings.map((warning, index) => (
              <ReviewItem key={`warning-${index}`} tone="amber" text={normalizeText(warning)} />
            ))}
            {result.failed_stages.map((stage, index) => (
              <ReviewItem key={`stage-${index}`} tone="red" text={`Failed stage: ${titleCase(stage)}`} />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function ResultCta({ navigate }: { navigate: NavigateFunction }) {
  return (
    <section className="border-t border-slate-200 bg-white">
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="rounded-lg bg-slate-950 p-6 text-white shadow-sm sm:p-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-2xl">
              <h2 className="text-2xl font-bold">Process private tenders with the full product.</h2>
              <p className="mt-2 text-sm leading-6 text-slate-300">
                Sign in to upload real tender PDFs, persist results, export BOQ workbooks, and compare tenders over time.
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row">
              <button
                onClick={() => navigate('/register')}
                className="inline-flex items-center justify-center gap-2 rounded-md bg-white px-5 py-3 text-sm font-bold text-slate-950 transition hover:bg-blue-50"
              >
                Create free account
                <ArrowRight className="h-4 w-4" />
              </button>
              <button
                onClick={() => navigate('/')}
                className="inline-flex items-center justify-center rounded-md border border-slate-600 px-5 py-3 text-sm font-bold text-white transition hover:bg-slate-800"
              >
                Learn more
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function MetricCard({
  label,
  value,
  subtext,
  icon,
  accent,
}: {
  label: string;
  value: string;
  subtext: string;
  icon: ReactNode;
  accent: 'emerald' | 'blue' | 'violet' | 'amber';
}) {
  const classes = {
    emerald: 'border-l-emerald-500 text-emerald-700',
    blue: 'border-l-blue-500 text-blue-700',
    violet: 'border-l-violet-500 text-violet-700',
    amber: 'border-l-amber-500 text-amber-700',
  };

  return (
    <div className={`rounded-md border border-slate-200 border-l-4 bg-white p-4 shadow-sm ${classes[accent]}`}>
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-bold uppercase tracking-wide text-slate-500">{label}</p>
        {icon}
      </div>
      <p className="mt-3 truncate text-xl font-bold tabular-nums text-slate-950">{value}</p>
      <p className="mt-1 text-xs font-medium leading-5 text-slate-500">{subtext}</p>
    </div>
  );
}

function ConfidenceRow({ label, value }: { label: string; value: number }) {
  const tone = value >= 0.88 ? 'bg-emerald-600 text-emerald-700' : value >= 0.72 ? 'bg-amber-500 text-amber-700' : 'bg-red-500 text-red-700';

  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between gap-3">
        <span className="text-sm font-semibold text-slate-700">{label}</span>
        <span className={`text-sm font-bold ${tone.split(' ')[1]}`}>{formatPercent(value)}</span>
      </div>
      <div className="h-2.5 overflow-hidden rounded-full bg-slate-100">
        <div className={`h-full rounded-full ${tone.split(' ')[0]}`} style={{ width: formatPercent(value) }} />
      </div>
    </div>
  );
}

function TabButton({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: ReactNode; label: string }) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex flex-1 items-center justify-center gap-2 rounded px-4 py-2.5 text-sm font-bold transition sm:flex-none ${
        active ? 'bg-blue-700 text-white shadow-sm' : 'text-slate-600 hover:bg-slate-50'
      }`}
    >
      {icon}
      {label}
    </button>
  );
}

function ProfileRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 border-b border-slate-100 pb-3 last:border-0 last:pb-0">
      <dt className="font-medium text-slate-500">{label}</dt>
      <dd className="text-right font-semibold text-slate-900">{value}</dd>
    </div>
  );
}

function PriceRow({ label, value, currency, strong = false }: { label: string; value: number; currency: string; strong?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className={strong ? 'font-bold text-slate-950' : 'text-slate-600'}>{label}</span>
      <span className={`tabular-nums ${strong ? 'text-base font-bold text-emerald-700' : 'font-semibold text-slate-900'}`}>
        {formatCurrency(value, currency)}
      </span>
    </div>
  );
}

function ReviewItem({ tone, text }: { tone: 'amber' | 'red'; text: string }) {
  const classes = tone === 'red' ? 'border-red-200 bg-red-50 text-red-800' : 'border-amber-200 bg-white/70 text-amber-900';

  return (
    <div className={`rounded-md border px-3 py-2 text-sm font-medium leading-6 ${classes}`}>
      {text}
    </div>
  );
}

function ProofTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
      <div className="text-2xl font-bold tabular-nums text-slate-950">{value}</div>
      <div className="mt-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
    </div>
  );
}

function TableHead({ children, align = 'left' }: { children: ReactNode; align?: 'left' | 'right' }) {
  const alignClass = align === 'right' ? 'text-right' : 'text-left';

  return (
    <th className={`px-4 py-3 ${alignClass} text-xs font-bold uppercase tracking-wide text-slate-500`}>
      {children}
    </th>
  );
}

function TableCell({
  children,
  align = 'left',
  strong = false,
  muted = false,
  mono = false,
}: {
  children: ReactNode;
  align?: 'left' | 'right';
  strong?: boolean;
  muted?: boolean;
  mono?: boolean;
}) {
  const alignClass = align === 'right' ? 'text-right' : 'text-left';
  const colorClass = strong ? 'font-bold text-slate-950' : muted ? 'text-slate-500' : 'text-slate-800';
  const monoClass = mono ? 'font-mono text-xs' : '';

  return (
    <td
      className={`px-4 py-3 ${alignClass} ${colorClass} ${monoClass} tabular-nums`}
    >
      {children}
    </td>
  );
}
