import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  downloadAnalyticsCsv,
  getAnalyticsDashboard,
  getExtractionScorecard,
  getPerformance,
  getTrends,
  type AnalyticsDashboardResponse,
  type ExtractionScorecardResponse,
  type PerformanceResponse,
  type TrendsResponse,
} from '../services/analytics';

function MetricCard({ title, value }: { title: string; value: string | number | null | undefined }) {
  const displayValue = value == null ? 'No data' : value;
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-sm text-slate-500">{title}</div>
      <div className="mt-2 text-2xl font-semibold text-slate-900">{displayValue}</div>
    </div>
  );
}

function KeyValueTable({ title, rows }: { title: string; rows: Array<[string, number]> }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="mb-3 text-lg font-semibold text-slate-900">{title}</h3>
      <div className="space-y-2">
        {rows.length === 0 ? <div className="text-sm text-slate-500">No data</div> : rows.map(([label, count]) => (
          <div key={`${title}-${label}`} className="flex items-center justify-between text-sm">
            <span className="text-slate-700">{label}</span>
            <span className="font-medium text-slate-900">{count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function AnalyticsDashboard() {
  const navigate = useNavigate();
  const [days, setDays] = useState(30);
  const [dashboard, setDashboard] = useState<AnalyticsDashboardResponse | null>(null);
  const [scorecard, setScorecard] = useState<ExtractionScorecardResponse | null>(null);
  const [performance, setPerformance] = useState<PerformanceResponse | null>(null);
  const [trends, setTrends] = useState<TrendsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        setLoading(true);
        setError(null);
        const [dashboardData, scorecardData, performanceData, trendsData] = await Promise.all([
          getAnalyticsDashboard(days),
          getExtractionScorecard(days),
          getPerformance(days),
          getTrends(days === 365 ? 365 : 30),
        ]);
        if (cancelled) return;
        setDashboard(dashboardData);
        setScorecard(scorecardData);
        setPerformance(performanceData);
        setTrends(trendsData);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Failed to load analytics from the backend.');
        setDashboard(null);
        setScorecard(null);
        setPerformance(null);
        setTrends(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [days]);

  const hasAnalyticsData = useMemo(() => {
    if (!dashboard) return false;
    return dashboard.summary.total_tenders_processed > 0;
  }, [dashboard]);

  return (
    <div className="min-h-screen bg-slate-50 px-6 py-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex flex-col gap-4 rounded-2xl bg-slate-900 p-6 text-white shadow-lg md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-3xl font-bold">Platform Intelligence Dashboard</h1>
            <p className="mt-2 text-sm text-slate-300">Deterministic operational analytics from live tender processing events.</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <select value={days} onChange={(e) => setDays(Number(e.target.value))} className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white">
              <option value={30}>Last 30 days</option>
              <option value={365}>Last 12 months</option>
            </select>
            <button onClick={() => navigate('/dashboard')} className="rounded-lg border border-slate-600 bg-slate-800 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700">
              Back to Dashboard
            </button>
            <button onClick={() => window.location.reload()} className="rounded-lg border border-slate-600 bg-slate-800 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700">
              Refresh
            </button>
            <button onClick={() => downloadAnalyticsCsv(days)} className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-medium text-white hover:bg-blue-600">
              Export CSV
            </button>
            <button onClick={() => window.print()} className="rounded-lg bg-white px-4 py-2 text-sm font-medium text-slate-900 hover:bg-slate-100">
              Export PDF
            </button>
          </div>
        </div>

        {loading ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 8 }).map((_, index) => (
              <div key={index} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm animate-pulse">
                <div className="h-4 w-28 rounded bg-slate-200" />
                <div className="mt-3 h-8 w-20 rounded bg-slate-200" />
              </div>
            ))}
          </div>
        ) : null}
        {error ? (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Failed to load platform analytics from the backend. {error}
          </div>
        ) : null}

        {!loading && !error && !hasAnalyticsData ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center shadow-sm">
            <h2 className="text-xl font-semibold text-slate-900">No processed tenders yet.</h2>
            <p className="mt-2 text-sm text-slate-500">Platform analytics will appear here after real tenders have been processed by the backend.</p>
            <div className="mt-5 flex justify-center gap-3">
              <button onClick={() => navigate('/dashboard')} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700">
                Go to Dashboard
              </button>
              <button onClick={() => window.location.reload()} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">
                Refresh
              </button>
            </div>
          </div>
        ) : null}

        {dashboard && hasAnalyticsData ? (
          <>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <MetricCard title="Total tenders processed" value={dashboard.summary.total_tenders_processed} />
              <MetricCard title="Successful jobs" value={dashboard.summary.successful_jobs} />
              <MetricCard title="Failed jobs" value={dashboard.summary.failed_jobs} />
              <MetricCard title="Average readiness score" value={dashboard.summary.average_readiness_score} />
              <MetricCard title="Average processing time (ms)" value={dashboard.summary.average_processing_time_ms} />
              <MetricCard title="OCR usage %" value={dashboard.summary.ocr_usage_percent} />
              <MetricCard title="Digital PDF %" value={dashboard.summary.digital_pdf_percent} />
              <MetricCard title="Average BOQ items" value={dashboard.summary.average_boq_items} />
            </div>

            <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
              <KeyValueTable title="Most common currencies" rows={dashboard.most_common_currencies} />
              <KeyValueTable title="Most common jurisdictions" rows={dashboard.most_common_jurisdictions} />
              <KeyValueTable title="Most common procurement methods" rows={dashboard.most_common_procurement_methods} />
              <KeyValueTable title="Most common missing documents" rows={dashboard.most_common_missing_documents} />
              <KeyValueTable title="Most common warnings" rows={dashboard.most_common_warnings} />
              <KeyValueTable title="Most common failures" rows={dashboard.most_common_failures} />
            </div>
          </>
        ) : null}

        {hasAnalyticsData ? (
          <>
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <h3 className="mb-3 text-lg font-semibold text-slate-900">Extraction Scorecard</h3>
                <div className="space-y-2 text-sm">
                  {scorecard ? Object.entries(scorecard.metrics).map(([key, value]) => (
                    <div key={key} className="flex items-center justify-between">
                      <span className="text-slate-700">{key}</span>
                      <span className="font-medium text-slate-900">{value}%</span>
                    </div>
                  )) : <div className="text-slate-500">No scorecard data</div>}
                </div>
              </div>

              <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <h3 className="mb-3 text-lg font-semibold text-slate-900">Performance Metrics</h3>
                <div className="space-y-2 text-sm">
                  {performance ? Object.entries(performance).map(([key, value]) => (
                    <div key={key} className="flex items-center justify-between">
                      <span className="text-slate-700">{key}</span>
                      <span className="font-medium text-slate-900">{value ?? 'No data'}</span>
                    </div>
                  )) : <div className="text-slate-500">No performance data</div>}
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h3 className="mb-3 text-lg font-semibold text-slate-900">Trend Data</h3>
              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-slate-500">
                      <th className="py-2 pr-4">Date</th>
                      <th className="py-2 pr-4">Processed</th>
                      <th className="py-2 pr-4">Completed</th>
                      <th className="py-2 pr-4">Failed</th>
                      <th className="py-2 pr-4">Avg readiness</th>
                      <th className="py-2 pr-4">Avg processing ms</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(trends?.daily || []).slice(0, 40).map((row) => (
                      <tr key={row.date} className="border-b border-slate-100">
                        <td className="py-2 pr-4">{row.date}</td>
                        <td className="py-2 pr-4">{row.processed}</td>
                        <td className="py-2 pr-4">{row.completed}</td>
                        <td className="py-2 pr-4">{row.failed}</td>
                        <td className="py-2 pr-4">{row.avg_readiness_score ?? 'No data'}</td>
                        <td className="py-2 pr-4">{row.avg_processing_time_ms ?? 'No data'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
