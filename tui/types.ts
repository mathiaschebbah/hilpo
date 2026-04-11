export interface ScopeAccuracy {
  n: number;
  category: number;
  visualFormat: number;
  strategy: number;
}

export interface TelemetryState {
  mode?: "protegi";
  runId: number;
  flags: string[];
  cursor: number;
  total: number;
  nProcessed: number;
  rate: number;
  elapsedSec: number;
  etaSec: number | null;

  accuracy: { category: number; visualFormat: number; strategy: number };
  loss: { category: number; visualFormat: number; strategy: number };
  rolling50: { cat: number; vf: number; str: number } | null;
  byScope: {
    FEED: ScopeAccuracy;
    REELS: ScopeAccuracy;
  };

  costUsd: number;
  inputTokens: number;
  outputTokens: number;

  maxPromptVersion: number;
  errorBufferSize: number;
  batchSize: number;
  skipped: number;

  phase: "classification" | "rewrite" | "done" | "failed";
  rewriteSubPhase: string | null;
  rewritesPromoted: number;
  rewritesRollback: number;

  lastActivitySec: number;
  lastActivityLabel: string;

  events: Array<{ ts: string; msg: string; type?: "event" | "api" | "error" }>;
}

export interface StructuredSlot {
  key: string;
  agent: string;
  scope: string | null;
  stepsTaken: number;
  stepsAccepted: number;
  jInitial: number;
  jCurrent: number;
  tabuHits: number;
  done: boolean;
}

export interface JComponents {
  macroF1_vf?: number;
  macroF1_cat?: number;
  acc_strat?: number;
}

export interface StructuredTelemetryState {
  mode: "structured";
  runId: number;
  flags: string[];
  phase:
    | "bootstrap"
    | "eval_initial"
    | "coord_ascent"
    | "eval_holdout"
    | "done"
    | "failed";
  phaseElapsedSec: number;
  phaseDone: number;
  phaseTotal: number;
  phaseUnit: string | null;
  elapsedSec: number;
  rate: number;
  etaSec: number | null;
  lastActivitySec: number;
  lastActivityLabel: string;

  passNum: number;
  passMax: number;
  currentSlot: string | null;
  currentStep: number;
  currentStepMax: number;
  currentSubPhase: string | null;

  jInitial: number | null;
  jCurrent: number | null;
  jComponents: JComponents;
  jHoldout: number | null;
  jHoldoutComponents: JComponents;

  slots: StructuredSlot[];

  nStepsGlobal: number;
  nStepsAcceptedGlobal: number;
  nPassesCompleted: number;
  nSlotsDone: number;

  costUsd: number;
  inputTokens: number;
  outputTokens: number;
  apiCallsCount: number;

  events: Array<{ ts: string; msg: string; type?: string }>;
}

export type AnyTelemetryState = TelemetryState | StructuredTelemetryState;

export function isStructured(
  state: AnyTelemetryState,
): state is StructuredTelemetryState {
  return state.mode === "structured";
}
