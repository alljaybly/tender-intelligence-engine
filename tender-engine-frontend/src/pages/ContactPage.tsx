import { Phone, Mail, MapPin, Clock } from 'lucide-react';
import AppFooter from '../components/layout/AppFooter';
import PublicHeader from '../components/layout/PublicHeader';

export default function ContactPage() {
  return (
    <div className="min-h-screen bg-slate-50">
      <PublicHeader />
      
      <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="text-center">
          <p className="text-sm font-bold uppercase tracking-wide text-blue-700">Contact Us</p>
          <h1 className="mt-3 text-3xl font-black tracking-tight text-slate-950 sm:text-4xl">
            Get in touch with Tender Engine
          </h1>
          <p className="mt-4 max-w-2xl mx-auto text-lg leading-8 text-slate-600">
            Have questions about our product or want to arrange a pilot? We'd love to hear from you.
          </p>
        </div>

        <div className="mt-16 grid gap-8 lg:grid-cols-3">
          {/* Phone */}
          <div className="rounded-lg border border-slate-200 bg-white p-8 shadow-sm">
            <div className="flex h-14 w-14 items-center justify-center rounded-md bg-blue-50 text-blue-700">
              <Phone className="h-7 w-7" />
            </div>
            <h3 className="mt-6 text-lg font-bold text-slate-950">Phone</h3>
            <p className="mt-2 text-sm text-slate-600">Call us directly for immediate assistance.</p>
            <a
              href="tel:+27834782235"
              className="mt-4 inline-block text-lg font-semibold text-blue-700 hover:text-blue-800 transition"
            >
              +27 83 478 2235
            </a>
          </div>

          {/* Email */}
          <div className="rounded-lg border border-slate-200 bg-white p-8 shadow-sm">
            <div className="flex h-14 w-14 items-center justify-center rounded-md bg-blue-50 text-blue-700">
              <Mail className="h-7 w-7" />
            </div>
            <h3 className="mt-6 text-lg font-bold text-slate-950">Email</h3>
            <p className="mt-2 text-sm text-slate-600">Send us an email anytime, and we'll respond as soon as possible.</p>
            <a
              href="mailto:tenderengine@zohomail.com?subject=Inquiry about Tender Engine"
              className="mt-4 inline-block text-lg font-semibold text-blue-700 hover:text-blue-800 transition"
            >
              tenderengine@zohomail.com
            </a>
          </div>

          {/* Address */}
          <div className="rounded-lg border border-slate-200 bg-white p-8 shadow-sm">
            <div className="flex h-14 w-14 items-center justify-center rounded-md bg-blue-50 text-blue-700">
              <MapPin className="h-7 w-7" />
            </div>
            <h3 className="mt-6 text-lg font-bold text-slate-950">Address</h3>
            <p className="mt-2 text-sm text-slate-600">Visit our office during business hours.</p>
            <div className="mt-4 text-sm text-slate-700 space-y-1">
              <p>12 Claasens Street</p>
              <p>Bishop Lavis</p>
              <p>Cape Town</p>
              <p>Western Cape</p>
              <p>7490</p>
              <p>South Africa</p>
            </div>
          </div>
        </div>

        {/* Business Hours */}
        <div className="mt-12 rounded-lg border border-slate-200 bg-white p-8 shadow-sm">
          <div className="flex items-center gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-md bg-blue-50 text-blue-700">
              <Clock className="h-7 w-7" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-950">Business Hours</h3>
              <p className="mt-1 text-sm text-slate-600">Monday–Friday, 08:00–17:00 (SAST)</p>
            </div>
          </div>
        </div>
      </div>

      <AppFooter />
    </div>
  );
}
