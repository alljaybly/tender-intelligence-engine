import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import {
  BadgeCheck,
  BarChart3,
  Building2,
  CalendarDays,
  Check,
  CircleDollarSign,
  FileSearch,
  ListChecks,
  Loader2,
  MapPin,
  ScanText,
  Users,
} from 'lucide-react';
import { demoSimEngine } from '../../demo/demoEngine';
import type { SimulationState } from '../../demo/demoEngine';

interface Props {
  onComplete: () => void;
}

const stageIcons: Record<string, ReactNode> = {
  extract_text: <ScanText className="h-4 w-4" />,
  detect_sector: <Building2 className="h-4 w-4" />,
  detect_duration: <CalendarDays className="h-4 w-4" />,
  detect_locations: <MapPin className="h-4 w-4" />,
  extract_workforce: <Users className="h-4 w-4" />,
  extract_schedule: <BarChart3 className="h-4 w-4" />,
  extract_boq: <ListChecks className="h-4 w-4" />,
  pricing: <CircleDollarSign className="h-4 w-4" />,
};

function statusClasses(status: string): string {
  switch (status) {
    case 'completed':
      return 'border-emerald-200 bg-emerald-50 text-emerald-800';
    case 'in_progress':
      return 'border-blue-300 bg-blue-50 text-blue-800 shadow-sm';
    case 'failed':
      return 'border-red-200 bg-red-50 text-red-800';
    default:
      return 'border-slate-200 bg-white text-slate-500';
  }
}

export default function DemoProcessingAnimation({ onComplete }: Props) {
  const [simState, setSimState] = useState<SimulationState>(demoSimEngine.getState());
  const [completeQueued, setCompleteQueued] = useState(false);

  useEffect(() => {
    demoSimEngine.onStateChange((newState) => {
      setSimState(newState);
      if (newState.phase === 'complete') {
        setCompleteQueued(true);
      }
    });

    return () => {
      demoSimEngine.onStateChange(() => undefined);
    };
  }, []);

  useEffect(() => {
    if (!completeQueued) return undefined;

    const timerId = window.setTimeout(onComplete, 650);
    return () => window.clearTimeout(timerId);
  }, [completeQueued, onComplete]);

  const currentStage = useMemo(
    () => simState.stages.find((stage) => stage.status === 'in_progress') ?? simState.stages.find((stage) => stage.status === 'completed'),
    [simState.stages],
  );

  if (simState.phase === 'idle') return null;

  const isLoading = simState.phase === 'loading';
  const isComplete = simState.phase === 'complete';

  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 bg-slate-950 px-5 py-5 text-white">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="rounded-md bg-white/10 p-2">
              {isComplete ? <BadgeCheck className="h-5 w-5 text-emerald-300" /> : <Loader2 className="h-5 w-5 animate-spin text-blue-200" />}
            </div>
            <div>
              <h2 className="text-lg font-bold">
                {isLoading ? 'Preparing document' : isComplete ? 'Result ready' : 'Processing tender'}
              </h2>
              <p className="mt-1 text-sm leading-6 text-slate-300">
                {simState.fileName ? simState.fileName : 'Tender PDF'} is running through the demo pipeline.
              </p>
            </div>
          </div>
          <div className="rounded-md bg-white/10 px-3 py-2 text-right">
            <div className="text-2xl font-bold tabular-nums">{simState.progressPercent}%</div>
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-300">Complete</div>
          </div>
        </div>

        <div className="mt-5 h-3 overflow-hidden rounded-full bg-white/10">
          <div
            className="h-full rounded-full bg-gradient-to-r from-blue-400 via-emerald-400 to-amber-300 transition-all duration-500"
            style={{ width: `${simState.progressPercent}%` }}
          />
        </div>
      </div>

      <div className="grid gap-0 lg:grid-cols-[1fr_260px]">
        <div className="p-5">
          {isLoading ? (
            <div className="flex min-h-72 flex-col items-center justify-center rounded-md border border-slate-200 bg-slate-50 text-center">
              <FileSearch className="h-10 w-10 text-blue-700" />
              <p className="mt-4 text-sm font-semibold text-slate-700">Opening document and preparing stage plan...</p>
            </div>
          ) : (
            <div className="space-y-2">
              {simState.stages.map((stage, index) => (
                <div
                  key={stage.stageId}
                  className={`flex items-start gap-3 rounded-md border px-4 py-3 transition ${statusClasses(stage.status)}`}
                >
                  <div className="mt-0.5 flex h-7 w-7 flex-none items-center justify-center rounded-md bg-white shadow-sm ring-1 ring-inset ring-current/10">
                    {stage.status === 'completed' ? <Check className="h-4 w-4 text-emerald-700" /> : stageIcons[stage.stageId] ?? <FileSearch className="h-4 w-4" />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-bold">{stage.label}</span>
                      {stage.status === 'in_progress' && (
                        <span className="rounded-md bg-blue-100 px-2 py-0.5 text-xs font-bold text-blue-700">Running</span>
                      )}
                      {stage.status === 'completed' && (
                        <span className="rounded-md bg-emerald-100 px-2 py-0.5 text-xs font-bold text-emerald-700">Done</span>
                      )}
                    </div>
                    <p className="mt-0.5 text-xs leading-5 opacity-80">{stage.description}</p>
                  </div>
                  <span className="text-xs font-bold tabular-nums opacity-60">{String(index + 1).padStart(2, '0')}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <aside className="border-t border-slate-200 bg-slate-50 p-5 lg:border-l lg:border-t-0">
          <h3 className="text-sm font-bold uppercase tracking-wide text-slate-500">Live signals</h3>
          <dl className="mt-4 space-y-4">
            <Signal label="Current stage" value={currentStage?.label ?? 'Queued'} />
            <Signal label="Job id" value={simState.jobId ?? 'pending'} />
            <Signal label="Backend calls" value="0" />
            <Signal label="Mode" value="Demo simulation" />
          </dl>
          <div className="mt-5 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-900">
            This animation is realistic by timing and stage order, but the result payload is loaded from public demo JSON.
          </div>
        </aside>
      </div>
    </div>
  );
}

function Signal({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-bold uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="mt-1 break-words text-sm font-semibold text-slate-800">{value}</dd>
    </div>
  );
}
