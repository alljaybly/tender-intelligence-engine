/**
 * Demo Simulation Engine
 *
 * Loads pre-generated mock JSON result files from public/demo-results/
 * and simulates the tender processing pipeline with realistic timing.
 *
 * No real backend calls - entirely client-side simulation.
 */
/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface DemoProcessingStage {
  id: string;
  label: string;
  description: string;
  durationMs: number; // how long this stage "runs" in the simulation
}

export const PROCESSING_STAGES: DemoProcessingStage[] = [
  { id: 'extract_text', label: 'Document Analysis', description: 'Extracting text and structure from tender document', durationMs: 800 },
  { id: 'detect_sector', label: 'Sector Detection', description: 'Identifying industry sector and project type', durationMs: 600 },
  { id: 'detect_duration', label: 'Duration Estimation', description: 'Analysing project timeline and milestones', durationMs: 500 },
  { id: 'detect_locations', label: 'Location Mapping', description: 'Extracting project locations from document', durationMs: 400 },
  { id: 'extract_workforce', label: 'Workforce Analysis', description: 'Estimating personnel requirements by role', durationMs: 700 },
  { id: 'extract_schedule', label: 'Schedule Extraction', description: 'Building project schedule from milestones', durationMs: 600 },
  { id: 'extract_boq', label: 'BOQ Extraction', description: 'Extracting bill of quantities line items', durationMs: 1200 },
  { id: 'pricing', label: 'Pricing Analysis', description: 'Calculating cost estimates and applying markups', durationMs: 900 },
];

/* ------------------------------------------------------------------ */
/*  Sample Tender Metadata                                             */
/* ------------------------------------------------------------------ */

export interface SampleTender {
  id: string;
  resultFile: string;
  fileName: string;
  title: string;
  description: string;
  sector: string;
  budget: string;
  badge: 'clean' | 'partial' | 'complex';
  badgeLabel: string;
}

export const SAMPLE_TENDERS: SampleTender[] = [
  {
    id: 'infrastructure-roadworks',
    resultFile: '/demo-results/infrastructure-roadworks.json',
    fileName: 'Municipal_Road_Civil_Works.pdf',
    title: 'Municipal Road & Civil Works',
    description: 'Johannesburg road infrastructure upgrade with 10 BOQ items. Clean, well-structured PDF.',
    sector: 'Infrastructure',
    budget: '~ZAR 38M',
    badge: 'clean',
    badgeLabel: 'Clean BOQ',
  },
  {
    id: 'scanned-building',
    resultFile: '/demo-results/scanned-building.json',
    fileName: 'Building_Refurbishment_Scanned.pdf',
    title: 'Building Refurbishment (Scanned)',
    description: 'Cape Town office refurbishment. Scanned PDF with OCR challenges - partial success example.',
    sector: 'Building Construction',
    budget: '~ZAR 7.5M',
    badge: 'partial',
    badgeLabel: 'OCR / Partial',
  },
  {
    id: 'complex-mega-project',
    resultFile: '/demo-results/complex-mega-project.json',
    fileName: 'National_Highway_Bridge_Upgrade.pdf',
    title: 'National Highway & Bridge Upgrade',
    description: 'Large-scale N2 highway upgrade. 14 BOQ items, 36 months, ZAR 442M. Complex multi-year.',
    sector: 'Infrastructure',
    budget: '~ZAR 442M',
    badge: 'complex',
    badgeLabel: 'Mega Project',
  },
  {
    id: 'water-treatment',
    resultFile: '/demo-results/water-treatment.json',
    fileName: 'Water_Treatment_Plant_Upgrade.pdf',
    title: 'Water Treatment Plant Upgrade',
    description: 'Nelspruit WTP expansion from 40ML/day to 65ML/day with 11 BOQ items.',
    sector: 'Water & Sanitation',
    budget: '~ZAR 85M',
    badge: 'clean',
    badgeLabel: 'Clean BOQ',
  },
  {
    id: 'solar-energy',
    resultFile: '/demo-results/solar-energy.json',
    fileName: 'Solar_PV_Plant_Installation.pdf',
    title: 'Solar PV Plant Installation',
    description: '12MW ground-mounted solar plant in Northern Cape. 10 BOQ items, renewable energy.',
    sector: 'Energy',
    budget: '~ZAR 87M',
    badge: 'clean',
    badgeLabel: 'Clean BOQ',
  },
];

/* ------------------------------------------------------------------ */
/*  Simulation Engine                                                  */
/* ------------------------------------------------------------------ */

export type SimulationPhase = 'idle' | 'loading' | 'processing' | 'complete' | 'error';

export interface StageProgress {
  stageId: string;
  label: string;
  description: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'skipped';
}

export interface SimulationState {
  phase: SimulationPhase;
  currentStageIndex: number;
  progressPercent: number;
  stages: StageProgress[];
  fileName: string | null;
  jobId: string | null;
}

type SimulationCallback = (state: SimulationState) => void;

export class DemoSimEngine {
  private state: SimulationState;
  private timerId: ReturnType<typeof setTimeout> | null = null;
  private callback: SimulationCallback | null = null;
  private startTime: number = 0;

  constructor() {
    this.state = this.createInitialState();
  }

  private createInitialState(): SimulationState {
    return {
      phase: 'idle',
      currentStageIndex: -1,
      progressPercent: 0,
      stages: PROCESSING_STAGES.map((s) => ({
        stageId: s.id,
        label: s.label,
        description: s.description,
        status: 'pending' as const,
      })),
      fileName: null,
      jobId: null,
    };
  }

  onStateChange(callback: SimulationCallback): void {
    this.callback = callback;
  }

  getState(): SimulationState {
    return { ...this.state, stages: [...this.state.stages] };
  }

  private emit(): void {
    if (this.callback) {
      this.callback({ ...this.state, stages: [...this.state.stages] });
    }
  }

  startSimulation(fileName: string): void {
    this.stopSimulation();
    this.state = this.createInitialState();
    this.state.phase = 'loading';
    this.state.fileName = fileName;
    this.state.jobId = `demo-${Date.now().toString(36)}`;
    this.startTime = Date.now();
    this.emit();

    // Small delay to show "loading" phase, then start processing
    this.timerId = setTimeout(() => {
      this.state.phase = 'processing';
      this.emit();
      this.runNextStage();
    }, 600);
  }

  private runNextStage(): void {
    const { currentStageIndex, stages } = this.state;
    const nextIndex = currentStageIndex + 1;

    if (nextIndex >= PROCESSING_STAGES.length) {
      // All done
      this.state.phase = 'complete';
      this.state.progressPercent = 100;
      this.emit();
      return;
    }

    const stage = PROCESSING_STAGES[nextIndex];
    const stageState = stages[nextIndex];

    // Mark current as in_progress
    stageState.status = 'in_progress';
    this.state.currentStageIndex = nextIndex;
    this.state.progressPercent = Math.round((nextIndex / PROCESSING_STAGES.length) * 100);
    this.emit();

    // Run the stage for its duration
    this.timerId = setTimeout(() => {
      // Mark as completed
      stageState.status = 'completed';
      this.state.progressPercent = Math.round(((nextIndex + 1) / PROCESSING_STAGES.length) * 100);
      this.emit();

      // Small gap before next stage
      this.timerId = setTimeout(() => {
        this.runNextStage();
      }, 200);
    }, stage.durationMs);
  }

  stopSimulation(): void {
    if (this.timerId !== null) {
      clearTimeout(this.timerId);
      this.timerId = null;
    }
  }

  reset(): void {
    this.stopSimulation();
    this.state = this.createInitialState();
    this.emit();
  }

  /** Load a demo result JSON file */
  async loadDemoResult(resultPath: string): Promise<unknown> {
    const response = await fetch(resultPath);
    if (!response.ok) {
      throw new Error(`Failed to load demo result: ${response.statusText}`);
    }
    return response.json();
  }

  /** Randomly assign a demo result for "uploaded" PDFs */
  getRandomDemoResultPath(): string {
    const randomIndex = Math.floor(Math.random() * SAMPLE_TENDERS.length);
    return SAMPLE_TENDERS[randomIndex].resultFile;
  }

  getElapsedMs(): number {
    return Date.now() - this.startTime;
  }
}

/** Singleton instance for the demo page */
export const demoSimEngine = new DemoSimEngine();

/** Backwards-compatible alias for the interrupted implementation. */
export const demoSimeEngine = demoSimEngine;
