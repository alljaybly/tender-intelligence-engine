import { ArrowRight, CheckCircle2, Play, ShieldCheck } from 'lucide-react';

interface HeroSectionProps {
  onTryDemo: () => void;
  onGetStarted: () => void;
}

const proofPoints = [
  'Extract BOQs, quantities, rates, and totals',
  'Surface warnings instead of hiding uncertainty',
  'Create executive-ready summaries in minutes',
];

export default function HeroSection({ onTryDemo, onGetStarted }: HeroSectionProps) {
  return (
    <section className="relative overflow-hidden bg-white">
      <div className="absolute inset-0 -z-10 bg-[linear-gradient(to_right,#e5e7eb_1px,transparent_1px),linear-gradient(to_bottom,#e5e7eb_1px,transparent_1px)] bg-[size:4rem_4rem] opacity-40" />
      <div className="mx-auto grid max-w-7xl gap-12 px-4 py-16 sm:px-6 sm:py-20 lg:grid-cols-[minmax(0,1.05fr)_minmax(360px,0.95fr)] lg:items-center lg:px-8 lg:py-24">
        <div>
          <div className="inline-flex items-center gap-2 rounded-md border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-bold uppercase tracking-wide text-blue-700">
            <ShieldCheck className="h-4 w-4" />
            Built for South African tenders
          </div>
          <h1 className="mt-6 max-w-4xl text-4xl font-black tracking-tight text-slate-950 sm:text-5xl lg:text-6xl leading-[1.1]">
            Turn tender PDFs into priced BOQs you can trust, not guess from.
          </h1>
          <p className="mt-5 max-w-2xl text-lg leading-8 text-slate-600">
            Upload a tender document and get a confidence-scored extraction of BOQ lines, pricing, sector, and review signals — all in one view, ready for your team.
          </p>

          <div className="mt-10 flex flex-col gap-4 sm:flex-row">
            <button
              onClick={onTryDemo}
              className="inline-flex items-center justify-center gap-2.5 rounded-xl bg-gradient-to-r from-blue-700 to-blue-600 px-8 py-4 text-base font-bold text-white shadow-lg ring-1 ring-blue-400/30 transition hover:-translate-y-0.5 hover:from-blue-800 hover:to-blue-700 hover:shadow-xl active:scale-[0.98]"
            >
              <Play className="h-5 w-5" />
              Try Live Demo — No Signup
            </button>
            <button
              onClick={onGetStarted}
              className="inline-flex items-center justify-center gap-2 rounded-xl border-2 border-slate-300 bg-white px-7 py-4 text-base font-bold text-slate-800 shadow-sm transition hover:-translate-y-0.5 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-800 active:scale-[0.98]"
            >
              Create Free Account
              <ArrowRight className="h-5 w-5" />
            </button>
          </div>

          <div className="mt-10 grid gap-3 sm:grid-cols-3">
            {proofPoints.map((point) => (
              <div key={point} className="flex items-start gap-2 rounded-md border border-slate-200 bg-white p-3 shadow-sm">
                <CheckCircle2 className="mt-0.5 h-4 w-4 flex-none text-emerald-600" />
                <p className="text-sm font-semibold leading-5 text-slate-700">{point}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 bg-slate-950 p-4 shadow-xl">
          <div className="rounded-md bg-white p-5">
            <div className="flex items-center justify-between gap-4 border-b border-slate-200 pb-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Demo result preview</p>
                <h2 className="mt-1 text-lg font-bold text-slate-950">Municipal Road & Civil Works</h2>
              </div>
              <span className="rounded-md bg-emerald-50 px-2.5 py-1 text-xs font-bold text-emerald-700 ring-1 ring-emerald-200">89% confidence</span>
            </div>

            <div className="mt-5 grid grid-cols-2 gap-3">
              <PreviewMetric label="BOQ value" value="R30.8M" />
              <PreviewMetric label="Estimated total" value="R37.9M" />
              <PreviewMetric label="BOQ lines" value="10" />
              <PreviewMetric label="Review flags" value="2" />
            </div>

            <div className="mt-5 rounded-md border border-amber-200 bg-amber-50 p-3">
              <p className="text-xs font-bold uppercase tracking-wide text-amber-700">Honesty Architecture</p>
              <p className="mt-1 text-sm leading-6 text-amber-900">
                The demo shows confidence scores, warnings, and partial-success states instead of pretending automation is always perfect.
              </p>
            </div>

            <button
              onClick={onTryDemo}
              className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-md bg-slate-950 px-4 py-3 text-sm font-bold text-white transition hover:bg-blue-700"
            >
              Open the interactive demo
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

function PreviewMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
      <div className="text-xl font-black tabular-nums text-slate-950">{value}</div>
      <div className="mt-1 text-xs font-bold uppercase tracking-wide text-slate-500">{label}</div>
    </div>
  );
}
