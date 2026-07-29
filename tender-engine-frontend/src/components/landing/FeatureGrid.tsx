import {
  BarChart3,
  ClipboardList,
  FileSpreadsheet,
  FileText,
  RefreshCw,
  ScanSearch,
  Target,
  Users,
} from 'lucide-react';

const features = [
  {
    title: 'BOQ Extraction',
    description: 'Extract item numbers, descriptions, quantities, units, rates, and amounts from tender documents.',
    icon: ClipboardList,
  },
  {
    title: 'OCR Support',
    description: 'Handle scanned PDFs and image-based tables when tender packs are not machine-readable.',
    icon: ScanSearch,
  },
  {
    title: 'Workforce Estimation',
    description: 'Identify skill categories, personnel counts, and inferred roles that affect delivery planning.',
    icon: Users,
  },
  {
    title: 'Pricing Intelligence',
    description: 'Turn extracted BOQ data into fast pricing estimates with contingency and escalation visibility.',
    icon: BarChart3,
  },
  {
    title: 'Executive Reports',
    description: 'Summarise tender scope, cost, timeline, warnings, and review priorities for decision makers.',
    icon: FileText,
  },
  {
    title: 'Excel Exports',
    description: 'Move structured BOQ and pricing data into spreadsheets for estimating and internal review.',
    icon: FileSpreadsheet,
  },
  {
    title: 'Retry Failed Stages',
    description: 'Recover from partial processing by retrying only the stage that needs attention.',
    icon: RefreshCw,
  },
  {
    title: 'Confidence Scoring',
    description: 'See how reliable each extraction stage is before you rely on the result.',
    icon: Target,
  },
];

export default function FeatureGrid() {
  return (
    <section id="contractors" className="bg-slate-50 py-20 sm:py-24">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-sm font-bold uppercase tracking-wide text-blue-700">For Contractors</p>
          <h2 className="mt-3 text-3xl font-black tracking-tight text-slate-950 sm:text-4xl">
            Spend less time decoding tender packs and more time pricing the work.
          </h2>
          <p className="mt-4 text-lg leading-8 text-slate-600">
            A practical toolkit for estimators, bid managers, and delivery teams who need speed without losing review control.
          </p>
        </div>
        <div className="mx-auto mt-14 grid max-w-6xl grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {features.map((feature) => {
            const Icon = feature.icon;
            return (
              <div key={feature.title} className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-blue-200 hover:shadow-md">
                <div className="flex h-10 w-10 items-center justify-center rounded-md bg-blue-50 text-blue-700">
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="mt-4 text-base font-bold text-slate-950">{feature.title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-600">{feature.description}</p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
