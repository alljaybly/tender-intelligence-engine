import { useCallback, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Menu, X } from 'lucide-react';
import LanguageSelector from './LanguageSelector';

const navLinks = [
  { label: 'Home', href: '/' },
  { label: 'Demo', href: '/demo', prominent: true },
  { label: 'Analytics', href: '/analytics' },
  { label: 'For Contractors', href: '/#contractors', hash: 'contractors' },
  { label: 'For Procurement Offices', href: '/for-procurement' },
  { label: 'Pricing', href: '/#pricing', hash: 'pricing' },
  { label: 'Contact', href: '/contact' },
];

function isActive(pathname: string, href: string): boolean {
  if (href === '/') return pathname === '/';
  if (href.startsWith('/#')) return false;
  return pathname === href;
}

export default function PublicHeader() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { pathname } = useLocation();
  const navigate = useNavigate();

  const handleNavClick = useCallback((e: React.MouseEvent<HTMLAnchorElement>, _href: string, hash?: string) => {
    if (!hash) return; // No interception needed for non-hash links

    e.preventDefault();

    if (pathname === '/') {
      // Already on the landing page — just scroll
      const el = document.getElementById(hash);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth' });
        window.history.replaceState(null, '', `/#${hash}`);
      }
    } else {
      // Navigate to landing page, then scroll after mount
      navigate('/');
      setTimeout(() => {
        const el = document.getElementById(hash);
        if (el) el.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    }
    setMobileOpen(false);
  }, [pathname, navigate]);

  return (
    <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/95 shadow-sm backdrop-blur">
      <nav className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <Link to="/" className="flex min-w-0 items-center gap-3">
          <img src="/images/logo.png" alt="Tender Engine" className="h-10 w-10 rounded-md object-contain" />
          <span className="min-w-0">
            <span className="block truncate text-sm font-bold leading-5 text-slate-950 sm:text-base">Tender Engine</span>
            <span className="hidden text-xs font-medium text-slate-500 sm:block">Professional Tender Processing Platform</span>
          </span>
        </Link>

        <div className="hidden items-center gap-1 lg:flex">
          {navLinks.map((link) => (
            <a
              key={link.label}
              href={link.href}
              onClick={(e) => handleNavClick(e, link.href, link.hash)}
              className={
                link.prominent
                  ? 'rounded-md bg-blue-50 px-3 py-2 text-sm font-bold text-blue-700 ring-1 ring-blue-200 transition hover:bg-blue-100'
                  : `rounded-md px-3 py-2 text-sm font-semibold transition ${
                      isActive(pathname, link.href) ? 'text-blue-700' : 'text-slate-600 hover:bg-slate-50 hover:text-slate-950'
                    }`
              }
            >
              {link.label}
            </a>
          ))}
        </div>

        <div className="hidden items-center gap-2 sm:flex">
          <LanguageSelector />
          <Link to="/login" className="rounded-md px-3 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-50 hover:text-slate-950">
            Login
          </Link>
          <Link to="/register" className="rounded-md bg-slate-950 px-4 py-2 text-sm font-bold text-white shadow-sm transition hover:bg-blue-700">
            Register
          </Link>
        </div>

        <button
          type="button"
          onClick={() => setMobileOpen((open) => !open)}
          className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-slate-200 text-slate-700 lg:hidden"
          aria-label="Toggle navigation"
          aria-expanded={mobileOpen}
        >
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </nav>

      {mobileOpen && (
        <div className="border-t border-slate-200 bg-white px-4 py-3 shadow-sm lg:hidden">
          <div className="mx-auto flex max-w-7xl flex-col gap-1">
          {navLinks.map((link) => (
            <a
              key={link.label}
              href={link.href}
              onClick={(e) => handleNavClick(e, link.href, link.hash)}
              className={
                link.prominent
                  ? 'rounded-md bg-blue-50 px-3 py-2 text-sm font-bold text-blue-700'
                  : 'rounded-md px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50'
              }
            >
              {link.label}
            </a>
          ))}
            <div className="mt-2 grid grid-cols-2 gap-2 border-t border-slate-100 pt-3">
              <LanguageSelector />
              <Link to="/login" onClick={() => setMobileOpen(false)} className="rounded-md border border-slate-200 px-3 py-2 text-center text-sm font-bold text-slate-700">
                Login
              </Link>
              <Link to="/register" onClick={() => setMobileOpen(false)} className="rounded-md bg-slate-950 px-3 py-2 text-center text-sm font-bold text-white">
                Register
              </Link>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
