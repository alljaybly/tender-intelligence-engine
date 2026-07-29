import { FileUp, ListChecks, Presentation } from 'lucide-react';

const steps = [
  {
    number: '01',
    title: 'Upload a tender pack',
    description: 'Use PDFs from municipalities, SOEs, private developers, and scanned tender packs.',
    icon: FileUp,
  },
  {
    number: '02',
    title: 'Extract and price the structure',
    description: 'Tender Engine identifies BOQs, scope, locations, schedules, workforce requirements, and pricing signals.',
    icon: ListChecks,
  },
  {
    number: '03',
    title: 'Review with confidence',
    description: 'Use summaries, warnings, failed-stage visibility, and confidence scores to decide what needs human review.',
    icon: Presentation,
  },
];

export default function HowItWorks() {
  return (
    <section className="bg-white py-20 sm:py-24">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-sm font-bold uppercase tracking-wide text-blue-700">How It Works</p>
          <h2 className="mt-3 text-3xl font-black tracking-tight text-slate-950 sm:text-4xl">
            From tender document to decision-ready output.
          </h2>
          <p className="mt-4 text-lg leading-8 text-slate-600">
            The workflow is designed for speed, but the output is designed for review.
          </p>
        </div>
        <div className="mx-auto mt-14 grid max-w-5xl grid-cols-1 gap-5 md:grid-cols-3">
          {steps.map((step) => {
            const Icon = step.icon;
            return (
              <div key={step.title} className="rounded-lg border border-slate-200 bg-white p-6 text-left shadow-sm">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex h-12 w-12 items-center justify-center rounded-md bg-blue-50 text-blue-700">
                    <Icon className="h-6 w-6" />
                  </div>
                  <span className="text-sm font-black text-slate-300">{step.number}</span>
                </div>
                <h3 className="mt-5 text-lg font-bold text-slate-950">{step.title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-600">{step.description}</p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
