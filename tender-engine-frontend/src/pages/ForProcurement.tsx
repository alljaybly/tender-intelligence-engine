import { useNavigate } from 'react-router-dom';
import AppFooter from '../components/layout/AppFooter';
import PublicHeader from '../components/layout/PublicHeader';

const BENEFITS = [
  {
    title: 'Reduce Bidder Confusion',
    description:
      'Flag ambiguous BOQ items, unclear specifications, and contradictory clauses before they reach suppliers. Clearer tenders attract better, more competitive bids.',
    icon: (
      <svg className="h-6 w-6 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  {
    title: 'Improve Bid Quality & Competition',
    description:
      'When tender documents are clear and well-structured, more qualified bidders can respond confidently — increasing competition and driving better value for money.',
    icon: (
      <svg className="h-6 w-6 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
      </svg>
    ),
  },
  {
    title: 'Lower Risk of Disputes & Variations',
    description:
      'Catch pricing gaps, missing quantities, and risky clauses before publication. Fewer ambiguities mean fewer contractor claims and cost overruns during project execution.',
    icon: (
      <svg className="h-6 w-6 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
      </svg>
    ),
  },
  {
    title: 'Save Time & Money',
    description:
      'Reduce the back-and-forth of tender clarification questions, cut evaluation cycles, and lower the administrative burden on your procurement team.',
    icon: (
      <svg className="h-6 w-6 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  {
    title: 'Promote Transparency & Good Governance',
    description:
      'Every tender health report includes clear confidence scores. You can demonstrate due diligence, show exactly where improvements were made, and build trust with bidders and oversight bodies.',
    icon: (
      <svg className="h-6 w-6 text-sky-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
];

const HOW_IT_WORKS = [
  {
    step: '1',
    title: 'Upload Your Draft Tender',
    description: 'Submit your tender document (PDF, DOCX, or TXT) through our secure portal.',
  },
  {
    step: '2',
    title: 'Analysis & Health Check',
    description: 'Our engine extracts and analyzes every section — BOQ items, specifications, pricing, schedules, and workforce requirements.',
  },
  {
    step: '3',
    title: 'Receive Your Tender Health Report',
    description: 'Get a clear report showing confidence scores, flagging ambiguous or missing items, and highlighting potential risks — before you publish.',
  },
];

export default function ForProcurement() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-white flex flex-col">
      {/* ── Navigation Bar ─────────────────────────────────────────── */}
      <PublicHeader />

      {/* ── Hero / Headline ────────────────────────────────────────── */}
      <section className="relative overflow-hidden bg-gradient-to-b from-blue-50/80 to-white">
        <div className="absolute inset-0 -z-10">
          <div className="absolute inset-0 bg-[linear-gradient(to_right,#e8f0fe_1px,transparent_1px),linear-gradient(to_bottom,#e8f0fe_1px,transparent_1px)] bg-[size:4rem_4rem] opacity-40" />
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[900px] h-[500px] bg-gradient-to-b from-blue-100/60 to-transparent rounded-full blur-3xl" />
        </div>
        <div className="mx-auto max-w-7xl px-6 py-20 sm:py-28 lg:px-8">
          <div className="mx-auto max-w-3xl text-center">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-100 border border-blue-200 text-xs font-semibold text-blue-700 mb-6">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500" />
              </span>
              For Government & Public Procurement
            </div>
            <h1 className="text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl lg:text-6xl leading-tight">
              Help Us Create{' '}
              <span className="text-blue-600">Clearer, Better Tenders</span>
            </h1>
            <p className="mt-6 text-lg leading-8 text-gray-600 max-w-2xl mx-auto">
              Upload your draft tender. Our processing engine analyzes it and flags ambiguous BOQ items,
              unclear specifications, missing information, and risky clauses — with clear
              confidence scores. Receive a professional{' '}
              <span className="font-semibold text-gray-900">Tender Health Report</span>{' '}
              before publishing.
            </p>
            <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
              <button
                onClick={() => navigate('/register')}
                className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-8 py-4 text-base font-semibold text-white shadow-sm hover:bg-blue-500 transition-all hover:shadow-lg hover:-translate-y-0.5 active:scale-[0.98]"
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" />
                </svg>
                Start Free Pilot — Submit 3 Tenders
              </button>
              <button
                onClick={() => navigate('/demo')}
                className="inline-flex items-center gap-2 rounded-xl border-2 border-blue-200 bg-white px-8 py-4 text-base font-semibold text-blue-700 shadow-sm hover:bg-blue-50 transition-all hover:shadow-lg hover:-translate-y-0.5 active:scale-[0.98]"
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                See a Demo Report
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* ── How It Works ───────────────────────────────────────────── */}
      <section className="bg-white py-20 sm:py-24">
        <div className="mx-auto max-w-7xl px-6 lg:px-8">
          <h2 className="text-center text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
            How It Works
          </h2>
          <p className="mt-4 text-center text-lg text-gray-600 max-w-2xl mx-auto">
            From draft to published — add a quality check before your tender goes to market.
          </p>
          <div className="mt-16 grid grid-cols-1 gap-8 sm:grid-cols-3">
            {HOW_IT_WORKS.map((item) => (
              <div key={item.step} className="relative text-center">
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-blue-100 text-xl font-bold text-blue-700">
                  {item.step}
                </div>
                <h3 className="mt-6 text-lg font-semibold text-gray-900">{item.title}</h3>
                <p className="mt-2 text-sm leading-6 text-gray-600">{item.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Benefits ───────────────────────────────────────────────── */}
      <section className="bg-gray-50 py-20 sm:py-24">
        <div className="mx-auto max-w-7xl px-6 lg:px-8">
          <h2 className="text-center text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
            Why Use Automated Quality Assurance?
          </h2>
          <p className="mt-4 text-center text-lg text-gray-600 max-w-2xl mx-auto">
            Better tender documents lead to better procurement outcomes for everyone.
          </p>
          <div className="mt-16 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {BENEFITS.map((benefit) => (
              <div
                key={benefit.title}
                className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm hover:shadow-md transition-shadow"
              >
                <div className="h-12 w-12 rounded-lg bg-blue-50 flex items-center justify-center mb-4">
                  {benefit.icon}
                </div>
                <h3 className="text-base font-semibold text-gray-900">{benefit.title}</h3>
                <p className="mt-2 text-sm leading-6 text-gray-600">{benefit.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Target Audience Section ────────────────────────────────── */}
      <section className="bg-white py-20 sm:py-24">
        <div className="mx-auto max-w-7xl px-6 lg:px-8">
          <h2 className="text-center text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
            Built for Public Procurement
          </h2>
          <p className="mt-4 text-center text-lg text-gray-600 max-w-2xl mx-auto">
            Our tender analysis is designed to support procurement professionals across the public sector.
          </p>
          <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-3">
            {[
              {
                title: 'National & Provincial Treasury',
                description: 'Support SCM directives by ensuring tender documents are clear, complete, and compliant before publication.',
                icon: (
                  <svg className="h-8 w-8 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21M3 3h12m-.75 4.5H21m-3.75 3.75h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008z" />
                  </svg>
                ),
              },
              {
                title: 'Provincial SCM Departments',
                description: 'Streamline tender review processes, reduce clarification cycles, and publish higher-quality bid documents faster.',
                icon: (
                  <svg className="h-8 w-8 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25zM6.75 12h.008v.008H6.75V12zm0 3h.008v.008H6.75V15zm0 3h.008v.008H6.75V18z" />
                  </svg>
                ),
              },
              {
                title: 'Major SOEs',
                description: 'Eskom, Transnet, PRASA, and others — reduce contract disputes by catching risks early, before tenders go to market.',
                icon: (
                  <svg className="h-8 w-8 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25H12" />
                  </svg>
                ),
              },
            ].map((item) => (
              <div
                key={item.title}
                className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm hover:shadow-md transition-shadow"
              >
                <div className="h-14 w-14 rounded-xl bg-gray-50 flex items-center justify-center mb-4">
                  {item.icon}
                </div>
                <h3 className="text-lg font-semibold text-gray-900">{item.title}</h3>
                <p className="mt-2 text-sm leading-6 text-gray-600">{item.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Pilot Program CTA ──────────────────────────────────────── */}
      <section className="bg-gradient-to-br from-blue-600 to-blue-700 py-16 sm:py-20">
        <div className="mx-auto max-w-7xl px-6 lg:px-8 text-center">
          <div className="mx-auto max-w-2xl">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-500/30 border border-blue-400/40 text-xs font-semibold text-blue-100 mb-6">
              Free Pilot Program
            </div>
            <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
              Try It Free — No Commitment
            </h2>
            <p className="mt-4 text-lg leading-8 text-blue-100">
              We are currently offering free pilot programs to selected government departments
              and SOEs. Get a <span className="font-semibold text-white">Tender Health Report</span>{' '}
              for up to <span className="font-semibold text-white">3 draft tenders</span> at no cost.
            </p>
            <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4">
              <button
                onClick={() => navigate('/register')}
                className="inline-flex items-center gap-2 rounded-xl bg-white px-8 py-4 text-base font-bold text-blue-700 shadow-lg hover:bg-blue-50 transition-all hover:shadow-xl hover:-translate-y-0.5 active:scale-[0.98]"
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 8.688c0-.747.468-1.416 1.157-1.664l13.5-4.875A1.875 1.875 0 0120.25 4.5v13.388c0 .747-.468 1.416-1.157 1.664l-13.5 4.875A1.875 1.875 0 013.75 22.5V8.688z" />
                </svg>
                Start Free Pilot
              </button>
              <a
                href="mailto:tenderengine@zohomail.com"
                className="inline-flex items-center gap-2 rounded-xl border border-blue-400 px-8 py-4 text-base font-semibold text-white hover:bg-blue-500 transition-all hover:shadow-lg active:scale-[0.98]"
              >
                Contact Our Team
              </a>
            </div>
            <p className="mt-4 text-xs text-blue-200">
              No credit card required. Strict confidentiality guaranteed.
            </p>
          </div>
        </div>
      </section>

      {/* ── Footer ─────────────────────────────────────────────────── */}
      <AppFooter />
    </div>
  );
}
