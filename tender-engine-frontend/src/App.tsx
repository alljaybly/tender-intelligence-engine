import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { LanguageProvider } from './context/LanguageContext';
import BackToTop from './components/layout/BackToTop';
import ProtectedRoute from './components/auth/ProtectedRoute';
import NotFound from './pages/NotFound';

const Login = lazy(() => import('./pages/Login'));
const Register = lazy(() => import('./pages/Register'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const DemoPage = lazy(() => import('./pages/DemoPage'));
const ForProcurement = lazy(() => import('./pages/ForProcurement'));
const TermsPage = lazy(() => import('./pages/legal/TermsPage'));
const PrivacyPage = lazy(() => import('./pages/legal/PrivacyPage'));
const ContactPage = lazy(() => import('./pages/ContactPage'));
const AnalyticsDashboard = lazy(() => import('./pages/AnalyticsDashboard'));

/**
 * Minimal loading fallback shown while a lazy-loaded page chunk is
 * being fetched and executed. Keeps the UI responsive during navigation.
 */
function PageFallback() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="flex flex-col items-center gap-3">
        <svg
          className="h-8 w-8 animate-spin text-blue-500"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
        <p className="text-sm font-medium text-gray-500">Loading…</p>
      </div>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <LanguageProvider>
        <Suspense fallback={<PageFallback />}>
          <Routes>
            {/* Public entry redirects to login while protected app lives under explicit routes */}
            <Route path="/" element={<Login />} />

            {/* Demo experience — no auth required */}
            <Route path="/demo" element={<DemoPage />} />

            {/* Procurement page */}
            <Route path="/for-procurement" element={<ForProcurement />} />

            {/* Contact page */}
            <Route path="/contact" element={<ContactPage />} />

            {/* Legal pages */}
            <Route path="/terms" element={<TermsPage />} />
            <Route path="/privacy" element={<PrivacyPage />} />

            {/* Authentication routes */}
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
            <Route path="/analytics" element={<ProtectedRoute><AnalyticsDashboard /></ProtectedRoute>} />

            <Route path="*" element={<NotFound />} />
          </Routes>
          {/* Floating back-to-top button — visible on all pages */}
          <BackToTop />
        </Suspense>
        </LanguageProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;