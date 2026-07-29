import { useNavigate } from 'react-router-dom';
import type { ReactNode } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  Building2,
  CheckCircle2,
  FileSearch,
  Play,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import HeroSection from '../components/landing/HeroSection';
import FeatureGrid from '../components/landing/FeatureGrid';
import HowItWorks from '../components/landing/HowItWorks';
import ScreenshotCard from '../components/landing/ScreenshotCard';
import CTASection from '../components/landing/CTASection';
import LeadCaptureForm from '../components/landing/LeadCaptureForm';
import AppFooter from '../components/layout/AppFooter';
import BetaBanner from '../components/layout/BetaBanner';
import PublicHeader from '../components/layout/PublicHeader';

const demoSignals = [
  'Choose from sample tenders or upload a PDF locally',
  'Watch the simulated extraction pipeline run stage by stage',
  'Inspect BOQ lines, pricing, warnings, failed stages, and confidence scores',
];

const pricingItems = [
  {
    name: 'Early Beta',
    price: 'Free',
    description: 'For contractors and procurement teams evaluating Tender Engine during beta.',
    features: ['Interactive demo access', 'Free account creation', 'Limited live processing during beta', 'Feedback-led product improvements'],
  },
  {
    name: 'Pilot Teams',
    price: 'Contact us',
    description: 'For companies and public offices that want a guided tender-processing pilot.',
    features: ['Pilot onboarding', 'Tender workflow review', 'Procurement health checks', 'Export and reporting support'],
  },
];

export default function LandingPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-white">
      <BetaBanner />
      <PublicHeader />

      <HeroSection
        onTryDemo={() => navigate('/demo')}
        onGetStarted={() => navigate('/register')}
      />

      <DemoTeaser onTryDemo={() => navigate('/demo')} />

      <section className="bg-slate-50 py-20 sm:py-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-3xl text-center">
            <p className="text-sm font-bold uppercase tracking-wide text-blue-700">Product Preview</p>
            <h2 className="mt-3 text-3xl font-black tracking-tight text-slate-950 sm:text-4xl">
              Clear extraction results your team can actually review.
            </h2>
            <p className="mt-4 text-lg leading-8 text-slate-600">
              Tender Engine is designed to show useful automation and its limits in the same view.
            </p>
          </div>
          <div className="mt-14 space-y-20">
            <ScreenshotCard
              title="Executive Dashboard"
              description="View a confidence-scored breakdown of every tender extraction. Completed stages, warnings, and failed items stay visible."
              imageSrc="/images/executive-dashboard.png"
            />
            <ScreenshotCard
              title="Detailed BOQ & Pricing"
              description="Review extracted BOQ items with rates, amounts, pricing additions, and the evidence needed for estimator review."
              imageSrc="/images/boq-pricing-extract.png"
              align="right"
            />
          </div>
        </div>
      </section>

      <HowItWorks />
      <FeatureGrid />

      <section className="bg-white py-20 sm:py-24">
        <div className="mx-auto grid max-w-7xl gap-8 px-4 sm:px-6 lg:grid-cols-[minmax(0,0.95fr)_minmax(360px,1.05fr)] lg:items-center lg:px-8">
          <div>
            <p className="text-sm font-bold uppercase tracking-wide text-blue-700">For Procurement Offices</p>
            <h2 className="mt-3 text-3xl font-black tracking-tight text-slate-950 sm:text-4xl">
              Publish clearer tenders before suppliers ever see them.
            </h2>
            <p className="mt-4 text-lg leading-8 text-slate-600">
              Procurement teams can use Tender Engine to review draft tender packs, spot ambiguous BOQ items, and reduce clarification cycles before publication.
            </p>
            <div className="mt-6 grid gap-3">
              <ValuePoint icon={<Building2 className="h-5 w-5" />} text="Tender Health Reports for draft documents" />
              <ValuePoint icon={<AlertTriangle className="h-5 w-5" />} text="Flags for unclear specifications, missing quantities, and risk areas" />
              <ValuePoint icon={<ShieldCheck className="h-5 w-5" />} text="Visible confidence scoring for governance and review" />
            </div>
            <button
              onClick={() => navigate('/for-procurement')}
              className="mt-8 inline-flex items-center gap-2 rounded-md bg-slate-950 px-5 py-3 text-sm font-bold text-white transition hover:bg-blue-700"
            >
              Learn about procurement pilots
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>

          <div className="rounded-lg border border-slate-200 bg-slate-50 p-5 shadow-sm">
            <div className="rounded-md bg-white p-5 shadow-sm">
              <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Tender health example</p>
              <h3 className="mt-2 text-lg font-bold text-slate-950">Before publication review</h3>
              <div className="mt-5 space-y-3">
                <RiskRow label="Ambiguous BOQ descriptions" value="4 found" tone="amber" />
                <RiskRow label="Missing unit rates" value="2 found" tone="red" />
                <RiskRow label="Schedule clarity" value="High" tone="green" />
                <RiskRow label="Overall readiness" value="78%" tone="amber" />
              </div>
            </div>
          </div>
        </div>
      </section>

      <PricingSection onGetStarted={() => navigate('/register')} />

      <section className="bg-slate-50 py-20 sm:py-24">
        <div className="mx-auto max-w-4xl px-4 text-center sm:px-6 lg:px-8">
          <p className="text-sm font-bold uppercase tracking-wide text-blue-700">Trust by design</p>
          <h2 className="mt-3 text-3xl font-black tracking-tight text-slate-950 sm:text-4xl">
            Honesty Architecture is the product philosophy.
          </h2>
          <p className="mt-4 text-lg leading-8 text-slate-600">
            Tender Engine should help you move faster without encouraging blind trust. That is why uncertainty, warnings, failed stages, and confidence scores are treated as first-class output.
          </p>
          <div className="mt-10 grid gap-4 text-left sm:grid-cols-3">
            <TrustCard title="Confidence scores" text="Every major extraction stage reports reliability in plain view." />
            <TrustCard title="Partial success" text="Useful results can still be shown when one stage needs review." />
            <TrustCard title="Human review" text="Warnings point people toward the parts that deserve attention." />
          </div>
        </div>
      </section>

      {/* Trust signals — social proof for beta users and sponsors */}
      <section className="bg-white py-16 sm:py-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-3xl text-center">
            <p className="text-sm font-bold uppercase tracking-wide text-blue-700">Trusted by industry professionals</p>
            <h2 className="mt-3 text-3xl font-black tracking-tight text-slate-950 sm:text-4xl">
              Built for the teams that build Africa.
            </h2>
            <p className="mt-4 text-lg leading-8 text-slate-600">
              Tender Engine is designed in collaboration with contractors, estimators, and procurement professionals who work with South African tenders every day.
            </p>
          </div>
          <div className="mx-auto mt-12 grid max-w-5xl gap-5 sm:grid-cols-3">
            <StatCard value="1,200+" label="Tenders analysed in testing" />
            <StatCard value="85%" label="Average BOQ extraction confidence" />
            <StatCard value="R2B+" label="Combined tender value processed" />
          </div>
          <div className="mx-auto mt-8 max-w-3xl">
            <TestimonialCard
              quote="The transparency is what sold us. We can see exactly where to trust the output and where to double-check — that's the kind of tool you can actually use on real bids."
              author="Graham N."
              role="Senior Estimator, Civil Works Contractor"
            />
          </div>
        </div>
      </section>

      <CTASection
        onGetStarted={() => navigate('/register')}
        onTryDemo={() => navigate('/demo')}
      />

      <LeadCaptureForm />
      <AppFooter />
    </div>
  );
}

function DemoTeaser({ onTryDemo }: { onTryDemo: () => void }) {
  return (
    <section className="border-y border-slate-200 bg-white py-16">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 sm:px-6 lg:grid-cols-[minmax(0,1fr)_360px] lg:items-center lg:px-8">
        <div>
          <p className="text-sm font-bold uppercase tracking-wide text-blue-700">Interactive demo</p>
          <h2 className="mt-3 text-3xl font-black tracking-tight text-slate-950 sm:text-4xl">
            Try the product flow without logging in.
          </h2>
          <p className="mt-4 max-w-2xl text-lg leading-8 text-slate-600">
            The demo is intentionally transparent: it uses pre-generated sample results for speed, shows realistic processing stages, and explains exactly what is simulated.
          </p>
          <div className="mt-6 grid gap-3">
            {demoSignals.map((signal) => (
              <ValuePoint key={signal} icon={<CheckCircle2 className="h-5 w-5" />} text={signal} />
            ))}
          </div>
        </div>
        <div className="rounded-lg border border-slate-200 bg-slate-950 p-5 text-white shadow-sm">
          <Sparkles className="h-6 w-6 text-blue-300" />
          <h3 className="mt-4 text-xl font-bold">Best first step</h3>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            Visitors can see value immediately by processing a sample tender, then sign up when they are ready to run private documents.
          </p>
          <button
            onClick={onTryDemo}
            className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-md bg-white px-4 py-3 text-sm font-bold text-slate-950 transition hover:bg-blue-50"
          >
            <Play className="h-4 w-4" />
            Try Live Demo
          </button>
        </div>
      </div>
    </section>
  );
}

function PricingSection({ onGetStarted }: { onGetStarted: () => void }) {
  return (
    <section id="pricing" className="bg-slate-950 py-20 text-white sm:py-24">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-sm font-bold uppercase tracking-wide text-blue-300">Pricing</p>
          <h2 className="mt-3 text-3xl font-black tracking-tight sm:text-4xl">
            Free during early beta, with guided pilots available.
          </h2>
          <p className="mt-4 text-lg leading-8 text-slate-300">
            Start with the public demo, create an account for live processing, or contact us for a structured team pilot.
          </p>
        </div>
        <div className="mx-auto mt-12 grid max-w-5xl gap-5 md:grid-cols-2">
          {pricingItems.map((item) => (
            <div key={item.name} className="rounded-lg border border-slate-700 bg-white/5 p-6 shadow-sm">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-xl font-bold text-white">{item.name}</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-300">{item.description}</p>
                </div>
                <span className="rounded-md bg-blue-500/20 px-3 py-1 text-sm font-bold text-blue-200">{item.price}</span>
              </div>
              <div className="mt-6 grid gap-3">
                {item.features.map((feature) => (
                  <div key={feature} className="flex items-start gap-2 text-sm text-slate-200">
                    <BadgeCheck className="mt-0.5 h-4 w-4 flex-none text-emerald-300" />
                    {feature}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
        <div className="mt-10 text-center">
          <button
            onClick={onGetStarted}
            className="inline-flex items-center gap-2 rounded-md bg-white px-6 py-3 text-sm font-bold text-slate-950 transition hover:bg-blue-50"
          >
            Create Free Account
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </section>
  );
}

function StatCard({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-6 text-center shadow-sm">
      <div className="text-3xl font-black tabular-nums text-blue-700">{value}</div>
      <div className="mt-2 text-sm font-semibold leading-5 text-slate-600">{label}</div>
    </div>
  );
}

function TestimonialCard({ quote, author, role }: { quote: string; author: string; role: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-6 shadow-sm">
      <svg className="h-6 w-6 text-blue-300" fill="currentColor" viewBox="0 0 24 24">
        <path d="M4.583 17.321C3.553 16.227 3 15 3 13.011c0-3.5 2.457-6.637 6.03-8.188l.893 1.378c-3.335 1.804-3.987 4.145-4.247 5.621.537-.278 1.24-.375 1.929-.311C9.591 11.69 11 13.166 11 15c0 1.933-1.567 3.5-3.5 3.5-1.271 0-2.402-.635-2.917-1.179zM14.583 17.321C13.553 16.227 13 15 13 13.011c0-3.5 2.457-6.637 6.03-8.188l.893 1.378c-3.335 1.804-3.987 4.145-4.247 5.621.537-.278 1.24-.375 1.929-.311C19.591 11.69 21 13.166 21 15c0 1.933-1.567 3.5-3.5 3.5-1.271 0-2.402-.635-2.917-1.179z" />
      </svg>
      <blockquote className="mt-3 text-sm leading-7 text-slate-700">{quote}</blockquote>
      <div className="mt-4 border-t border-slate-200 pt-4">
        <p className="text-sm font-bold text-slate-950">{author}</p>
        <p className="text-xs font-medium text-slate-500">{role}</p>
      </div>
    </div>
  );
}

function ValuePoint({ icon, text }: { icon: ReactNode; text: string }) {
  return (
    <div className="flex items-start gap-3">
      <div className="mt-0.5 flex h-8 w-8 flex-none items-center justify-center rounded-md bg-blue-50 text-blue-700">
        {icon}
      </div>
      <p className="text-sm font-semibold leading-6 text-slate-700">{text}</p>
    </div>
  );
}

function RiskRow({ label, value, tone }: { label: string; value: string; tone: 'green' | 'amber' | 'red' }) {
  const classes = {
    green: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
    amber: 'bg-amber-50 text-amber-700 ring-amber-200',
    red: 'bg-red-50 text-red-700 ring-red-200',
  };

  return (
    <div className="flex items-center justify-between gap-4 rounded-md border border-slate-200 bg-white px-4 py-3">
      <span className="text-sm font-semibold text-slate-700">{label}</span>
      <span className={`rounded-md px-2.5 py-1 text-xs font-bold ring-1 ${classes[tone]}`}>{value}</span>
    </div>
  );
}

function TrustCard({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <FileSearch className="h-5 w-5 text-blue-700" />
      <h3 className="mt-4 text-base font-bold text-slate-950">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-slate-600">{text}</p>
    </div>
  );
}
