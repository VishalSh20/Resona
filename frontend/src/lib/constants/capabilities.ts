export interface CapabilityField {
  key: string;
  label: string;
}

export interface CapabilityGroup {
  key: string;
  label: string;
  fields: CapabilityField[];
}

// Mirrors the nested capability snapshot the backend's extract_capabilities
// flattens. Keys are the wire contract; labels are display-only.
export const CAPABILITY_GROUPS: CapabilityGroup[] = [
  {
    key: "audio",
    label: "Audio",
    fields: [
      { key: "caller_ingress", label: "Caller ingress" },
      { key: "agent_egress", label: "Agent egress" },
    ],
  },
  {
    key: "transcript",
    label: "Transcript",
    fields: [
      { key: "target_input", label: "Target input" },
      { key: "target_output", label: "Target output" },
      { key: "independent_asr_possible", label: "Independent ASR" },
    ],
  },
  {
    key: "events",
    label: "Events",
    fields: [
      { key: "turn_boundaries", label: "Turn boundaries" },
      { key: "text_stream", label: "Text stream" },
      { key: "interruptions", label: "Interruptions" },
      { key: "connection_events", label: "Connection events" },
    ],
  },
  {
    key: "tools",
    label: "Tools",
    fields: [
      { key: "calls", label: "Calls" },
      { key: "results", label: "Results" },
    ],
  },
];

// Inverse of the backend CAPABILITY_MATRIX: which metrics each capability
// affects. Useful because capability negotiation is a plan-time concern.
export const AFFECTED_METRICS: Record<string, string[]> = {
  caller_ingress: ["ttfa"],
  agent_egress: ["ttfa", "voice_quality", "language_adaptation"],
  target_input: ["agent_input_wer"],
  target_output: [],
  independent_asr_possible: ["independent_asr_wer"],
  turn_boundaries: [],
  text_stream: ["ttft"],
  interruptions: ["interruption_latency"],
  connection_events: [],
  calls: ["tool_selection", "tool_argument_correctness"],
  results: ["tool_result_handling"],
};

export type CapabilitySnapshot = Record<string, Record<string, boolean>>;

export function emptyCapabilitySnapshot(): CapabilitySnapshot {
  const snapshot: CapabilitySnapshot = {};
  for (const group of CAPABILITY_GROUPS) {
    snapshot[group.key] = {};
    for (const field of group.fields) {
      snapshot[group.key][field.key] = false;
    }
  }
  return snapshot;
}

export function isCapabilityAvailable(
  snapshot: Record<string, unknown> | null | undefined,
  group: string,
  field: string,
): boolean {
  const section = snapshot?.[group];
  if (!section || typeof section !== "object") return false;
  return Boolean((section as Record<string, unknown>)[field]);
}

export function countAvailableCapabilities(
  snapshot: Record<string, unknown> | null | undefined,
): { available: number; total: number } {
  let available = 0;
  let total = 0;
  for (const group of CAPABILITY_GROUPS) {
    for (const field of group.fields) {
      total += 1;
      if (isCapabilityAvailable(snapshot, group.key, field.key)) available += 1;
    }
  }
  return { available, total };
}
