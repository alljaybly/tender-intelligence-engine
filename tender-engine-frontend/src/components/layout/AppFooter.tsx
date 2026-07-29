import { Link } from 'react-router-dom';
import { Mail, MapPin, Home, Phone } from 'lucide-react';

export default function AppFooter() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="border-t border-slate-800 bg-slate-950">
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="grid gap-8 md:grid-cols-[1.5fr_1fr_1fr] md:items-start">
          <div>
            <div className="flex items-center gap-3">
              <img src="/images/logo.png" alt="Tender Engine" className="h-10 w-10 rounded-md object-contain" />
              <div>
                <p className="text-lg font-bold text-white">Tender Engine</p>
                <p className="text-sm font-medium text-slate-400">Professional Tender Processing Software</p>
              </div>
            </div>
            <p className="mt-4 max-w-md text-sm leading-6 text-slate-400">
              Evidence-based tender processing with fully auditable outputs.
            </p>
            
            <div className="mt-6 space-y-4 text-sm text-slate-400">
              <div className="flex items-start gap-3">
                <Phone className="mt-0.5 h-4 w-4 flex-none text-slate-500" />
                <div>
                  <p className="font-semibold text-slate-300">Phone</p>
                  <a href="tel:+27834782235" className="text-slate-400 hover:text-white transition">
                    +27 83 478 2235
                  </a>
                </div>
              </div>
              
              <div className="flex items-start gap-3">
                <Mail className="mt-0.5 h-4 w-4 flex-none text-slate-500" />
                <div>
                  <p className="font-semibold text-slate-300">Email</p>
                  <a 
                    href="mailto:tenderengine@zohomail.com?subject=Inquiry about Tender Engine" 
                    className="text-slate-400 hover:text-white transition"
                  >
                    tenderengine@zohomail.com
                  </a>
                </div>
              </div>
              
              <div className="flex items-start gap-3">
                <MapPin className="mt-0.5 h-4 w-4 flex-none text-slate-500" />
                <div>
                  <p className="font-semibold text-slate-300">Address</p>
                  <p>12 Claasens Street</p>
                  <p>Bishop Lavis</p>
                  <p>Cape Town</p>
                  <p>Western Cape</p>
                  <p>7490</p>
                  <p>South Africa</p>
                </div>
              </div>
            </div>
          </div>

          <div>
            <h2 className="text-sm font-bold uppercase tracking-wide text-slate-300">Product</h2>
            <div className="mt-4 grid gap-3 text-sm">
              <Link to="/" className="inline-flex items-center gap-2 text-slate-400 transition hover:text-white">
                <Home className="h-4 w-4" />
                Home
              </Link>
              <Link to="/demo" className="text-slate-400 transition hover:text-white">Live Demo</Link>
              <a href="/#contractors" className="text-slate-400 transition hover:text-white">For Contractors</a>
              <Link to="/for-procurement" className="text-slate-400 transition hover:text-white">For Procurement Offices</Link>
              <a href="/#pricing" className="text-slate-400 transition hover:text-white">Pricing</a>
            </div>
          </div>

          <div>
            <h2 className="text-sm font-bold uppercase tracking-wide text-slate-300">Company</h2>
            <div className="mt-4 grid gap-3 text-sm">
              <Link to="/" className="text-slate-400 transition hover:text-white">Home</Link>
              <Link to="/terms" className="text-slate-400 transition hover:text-white">Terms</Link>
              <Link to="/privacy" className="text-slate-400 transition hover:text-white">Privacy</Link>
            </div>
          </div>
        </div>

        <div className="mt-8 flex flex-col gap-3 border-t border-slate-800 pt-6 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between">
          <p>&copy; {currentYear >= 2026 ? currentYear : 2026} Tender Engine. All rights reserved.</p>
          <p>Designed for South African contractors and procurement professionals.</p>
        </div>
      </div>
    </footer>
  );
}
