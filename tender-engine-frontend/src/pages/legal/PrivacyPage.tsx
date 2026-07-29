/**
 * PrivacyPage — Renders the Privacy Policy markdown file.
 *
 * Fetches /privacy.md at runtime and renders it as styled HTML.
 * Falls back to an error message if the file cannot be loaded.
 */
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import AppFooter from '../../components/layout/AppFooter';

export default function PrivacyPage() {
  const navigate = useNavigate();
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadPrivacy() {
      try {
        const res = await fetch('/privacy.md');
        if (!res.ok) throw new Error(`Failed to load privacy policy (${res.status})`);
        const text = await res.text();
        if (!cancelled) setContent(text);
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load Privacy Policy');
        }
      }
    }

    loadPrivacy();
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="min-h-screen bg-white flex flex-col">
      {/* Header with back navigation */}
      <header className="sticky top-0 z-50 border-b border-gray-100 bg-white/80 backdrop-blur-sm">
        <nav className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4 lg:px-8">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-blue-600 flex items-center justify-center">
              <span className="text-sm font-bold text-white">TE</span>
            </div>
            <span className="text-lg font-semibold text-gray-900">Tender Engine</span>
          </div>
          <button
            onClick={() => navigate('/')}
            className="text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors"
          >
            Back to Home
          </button>
        </nav>
      </header>

      {/* Main content area — flex-1 pushes footer to bottom */}
      <main className="flex-1 mx-auto w-full max-w-4xl px-6 py-12 lg:px-8">
        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-6">
            <h2 className="text-lg font-semibold text-red-800 mb-2">Error Loading Privacy Policy</h2>
            <p className="text-sm text-red-600">{error}</p>
            <button
              onClick={() => window.location.reload()}
              className="mt-4 px-4 py-2 text-sm font-medium text-red-700 bg-red-100 rounded-md hover:bg-red-200 transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {!content && !error && (
          <div className="flex items-center justify-center py-24">
            <div className="animate-pulse text-gray-400 text-lg">Loading Privacy Policy...</div>
          </div>
        )}

        {content && (
          <div className="text-gray-800 text-base leading-7">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                // Style blockquotes — used for the legal disclaimer
                blockquote: ({ children }) => (
                  <blockquote className="border-l-4 border-blue-500 bg-blue-50 rounded-r-lg py-3 px-5 my-6 text-sm text-blue-800">
                    {children}
                  </blockquote>
                ),
                // Style headings
                h1: ({ children }) => (
                  <h1 className="text-3xl font-bold text-gray-900 mt-10 mb-4">{children}</h1>
                ),
                h2: ({ children }) => (
                  <h2 className="text-xl font-bold text-gray-900 mt-8 mb-3">{children}</h2>
                ),
                h3: ({ children }) => (
                  <h3 className="text-lg font-bold text-gray-900 mt-6 mb-2">{children}</h3>
                ),
                // Style links
                a: ({ href, children }) => (
                  <a href={href} className="text-blue-600 underline hover:text-blue-800 transition-colors">
                    {children}
                  </a>
                ),
                // Style lists
                ul: ({ children }) => (
                  <ul className="list-disc pl-6 space-y-1.5 my-3">{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol className="list-decimal pl-6 space-y-1.5 my-3">{children}</ol>
                ),
                li: ({ children }) => (
                  <li className="text-gray-700 leading-relaxed">{children}</li>
                ),
                // Style paragraphs
                p: ({ children }) => (
                  <p className="text-gray-700 leading-7 my-3">{children}</p>
                ),
                // Style horizontal rules
                hr: () => <hr className="border-t border-gray-200 my-8" />,
                // Style strong text
                strong: ({ children }) => (
                  <strong className="font-bold text-gray-900">{children}</strong>
                ),
                // Style tables (for data retention sections etc.)
                table: ({ children }) => (
                  <div className="overflow-x-auto my-4">
                    <table className="min-w-full border-collapse border border-gray-200 text-sm">
                      {children}
                    </table>
                  </div>
                ),
                th: ({ children }) => (
                  <th className="border border-gray-200 bg-gray-50 px-4 py-2 text-left font-medium text-gray-700">
                    {children}
                  </th>
                ),
                td: ({ children }) => (
                  <td className="border border-gray-200 px-4 py-2 text-gray-700">
                    {children}
                  </td>
                ),
              }}
            >
              {content}
            </ReactMarkdown>
          </div>
        )}
      </main>

      {/* Footer */}
      <AppFooter />
    </div>
  );
}