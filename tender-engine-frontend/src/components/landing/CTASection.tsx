import { ArrowRight, Play } from 'lucide-react';

interface CTASectionProps {
  onGetStarted: () => void;
  onTryDemo: () => void;
}

export default function CTASection({ onGetStarted, onTryDemo }: CTASectionProps) {
  return (
    <section className="bg-white py-20 sm:py-24">
      <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
        <div className="rounded-lg bg-slate-950 p-6 text-center shadow-sm sm:p-10">
          <p className="text-sm font-bold uppercase tracking-wide text-blue-300">Ready to see it work?</p>
          <h2 className="mt-3 text-3xl font-black tracking-tight text-white sm:text-4xl">
            Try the live demo before creating an account.
          </h2>
          <p className="mx-auto mt-4 max-w-2xl text-base leading-7 text-slate-300">
            Choose a sample tender, watch the simulated pipeline, and inspect BOQ, pricing, warnings, and confidence scores.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <button
              onClick={onTryDemo}
              className="inline-flex items-center justify-center gap-2 rounded-md bg-white px-6 py-3.5 text-sm font-bold text-slate-950 transition hover:bg-blue-50"
            >
              <Play className="h-4 w-4" />
              Try Live Demo
            </button>
            <button
              onClick={onGetStarted}
              className="inline-flex items-center justify-center gap-2 rounded-md border border-slate-600 px-6 py-3.5 text-sm font-bold text-white transition hover:bg-slate-800"
            >
              Create Free Account
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
