import { useState, type FormEvent } from 'react';
import { CheckCircle2 } from 'lucide-react';

interface LeadFormData {
  name: string;
  email: string;
  company: string;
  role: string;
}

export default function LeadCaptureForm() {
  const [formData, setFormData] = useState<LeadFormData>({
    name: '',
    email: '',
    company: '',
    role: '',
  });
  const [status, setStatus] = useState<'idle' | 'submitting' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState('');

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!formData.name || !formData.email) return;

    setStatus('submitting');
    try {
      const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
      const res = await fetch(`${apiBase}/api/leads`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });

      if (res.ok) {
        setStatus('success');
        setMessage('Thank you - we\'ll contact you soon.');
        setFormData({ name: '', email: '', company: '', role: '' });
      } else {
        const data = await res.json();
        setStatus('error');
        setMessage(data.detail || 'Something went wrong. Please try again.');
      }
    } catch {
      setStatus('error');
      setMessage('Unable to connect. Please try again later.');
    }
  };

  if (status === 'success') {
    return (
      <section className="bg-blue-700 py-24">
        <div className="mx-auto max-w-2xl text-center px-6">
          <div className="rounded-xl bg-white/10 p-8 backdrop-blur-sm">
            <CheckCircle2 className="mx-auto mb-4 h-12 w-12 text-emerald-300" />
            <h2 className="text-2xl font-bold text-white">{message}</h2>
            <p className="mt-2 text-blue-100">We'll be in touch with early access information.</p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="bg-slate-950 py-24">
      <div className="mx-auto max-w-2xl px-6 text-center">
        <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
          Request Early Access
        </h2>
        <p className="mt-4 text-lg leading-8 text-slate-300">
          Be among the first to try Tender Engine. We're launching soon.
        </p>
        <form onSubmit={handleSubmit} className="mt-10 mx-auto max-w-md space-y-4">
          <div>
            <input
              type="text"
              name="name"
              placeholder="Your name *"
              required
              value={formData.name}
              onChange={handleChange}
              className="block w-full rounded-md border-0 bg-white/10 px-4 py-2.5 text-white shadow-sm ring-1 ring-inset ring-white/20 placeholder:text-slate-400 focus:ring-2 focus:ring-inset focus:ring-blue-500 text-sm"
            />
          </div>
          <div>
            <input
              type="email"
              name="email"
              placeholder="Email address *"
              required
              value={formData.email}
              onChange={handleChange}
              className="block w-full rounded-md border-0 bg-white/10 px-4 py-2.5 text-white shadow-sm ring-1 ring-inset ring-white/20 placeholder:text-slate-400 focus:ring-2 focus:ring-inset focus:ring-blue-500 text-sm"
            />
          </div>
          <div>
            <input
              type="text"
              name="company"
              placeholder="Company"
              value={formData.company}
              onChange={handleChange}
              className="block w-full rounded-md border-0 bg-white/10 px-4 py-2.5 text-white shadow-sm ring-1 ring-inset ring-white/20 placeholder:text-slate-400 focus:ring-2 focus:ring-inset focus:ring-blue-500 text-sm"
            />
          </div>
          <div>
            <input
              type="text"
              name="role"
              placeholder="Role / Title"
              value={formData.role}
              onChange={handleChange}
              className="block w-full rounded-md border-0 bg-white/10 px-4 py-2.5 text-white shadow-sm ring-1 ring-inset ring-white/20 placeholder:text-slate-400 focus:ring-2 focus:ring-inset focus:ring-blue-500 text-sm"
            />
          </div>
          {status === 'error' && (
            <p className="text-sm text-red-400">{message}</p>
          )}
          <button
            type="submit"
            disabled={status === 'submitting'}
            className="w-full rounded-md bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-600 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-700 disabled:opacity-50 transition-colors"
          >
            {status === 'submitting' ? 'Submitting...' : 'Request Access'}
          </button>
        </form>
      </div>
    </section>
  );
}
