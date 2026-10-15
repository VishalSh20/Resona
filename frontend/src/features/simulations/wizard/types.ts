export interface SimulationDraft {
  name: string;
  agentTargetId: string;
  targetRevisionId: string;
  description: string;
  evaluatorCount: number | undefined;
  languages: string[];
  callAmbience: string[];
  personalities: string[];
  metrics: string[];
}

export const SIMULATION_STEPS = [
  "Target",
  "Configuration",
  "Personas",
  "Metrics",
  "Review",
] as const;

export const TARGET_STEP = 0;
export const CONFIGURATION_STEP = 1;
export const PERSONA_STEP = 2;
export const METRIC_STEP = 3;
export const REVIEW_STEP = 4;

export const EMPTY_DRAFT: SimulationDraft = {
  name: "",
  agentTargetId: "",
  targetRevisionId: "",
  description: "",
  evaluatorCount: 20,
  languages: [],
  callAmbience: [],
  personalities: [],
  metrics: [],
};

export function isEvaluatorCountValid(value: number | undefined): boolean {
  return (
    typeof value === "number" &&
    Number.isInteger(value) &&
    value >= 1 &&
    value <= 100
  );
}
