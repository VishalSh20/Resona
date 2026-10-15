export interface MetricOption {
  key: string;
  label: string;
  family: string;
  description: string;
}

// v0.4 metric catalogue (single source of truth, mirroring the backend
// `MetricKey` enum). The LLM generation workflows select from these keys.
export const METRIC_OPTIONS: MetricOption[] = [
  {
    key: "ttfa",
    label: "TTFA",
    family: "Latency & turn-taking",
    description: "Time until the agent starts speaking after the caller finishes.",
  },
  {
    key: "ttft",
    label: "TTFT",
    family: "Latency & turn-taking",
    description: "Time to first token from the underlying model.",
  },
  {
    key: "barge_in_latency",
    label: "Barge-in latency",
    family: "Latency & turn-taking",
    description: "How quickly the agent yields when the caller interrupts.",
  },
  {
    key: "barge_in_success_rate",
    label: "Barge-in success rate",
    family: "Latency & turn-taking",
    description: "How often the agent correctly handles an interruption.",
  },
  {
    key: "relevancy",
    label: "Relevancy",
    family: "Conversation quality",
    description: "Whether the response addresses the caller's actual request.",
  },
  {
    key: "context_retention",
    label: "Context retention",
    family: "Conversation quality",
    description:
      "Whether the agent correctly uses information established earlier in the call.",
  },
  {
    key: "repetition",
    label: "Repetition",
    family: "Conversation quality",
    description: "Whether the agent repeats itself or the caller unnecessarily.",
  },
  {
    key: "instruction_following",
    label: "Instruction following",
    family: "Conversation quality",
    description: "Whether the agent obeys its configured instructions.",
  },
  {
    key: "empathy",
    label: "Empathy",
    family: "Conversation quality",
    description: "Whether the agent acknowledges the caller's situation and tone.",
  },
  {
    key: "task_completion",
    label: "Task completion",
    family: "Task & knowledge",
    description: "Whether the caller's goal is actually achieved.",
  },
  {
    key: "hallucination",
    label: "Hallucination",
    family: "Task & knowledge",
    description: "Whether the agent invents facts it cannot support.",
  },
  {
    key: "kb_groundedness",
    label: "Knowledge-base groundedness",
    family: "Task & knowledge",
    description: "Whether answers stay grounded in the knowledge base.",
  },
  {
    key: "language_detection_accuracy",
    label: "Language detection accuracy",
    family: "Language quality",
    description: "Whether the agent correctly identifies the caller's language.",
  },
  {
    key: "code_switching_accuracy",
    label: "Code-switching accuracy",
    family: "Language quality",
    description: "Whether the agent handles mid-sentence language switching.",
  },
  {
    key: "semantic_preservation",
    label: "Semantic preservation",
    family: "Language quality",
    description: "Whether meaning is preserved across languages.",
  },
  {
    key: "language_consistency",
    label: "Language consistency",
    family: "Language quality",
    description: "Whether the agent stays in the agreed language.",
  },
];

const METRIC_LABELS = new Map(METRIC_OPTIONS.map((m) => [m.key, m.label]));

export function metricLabel(key: string): string {
  return METRIC_LABELS.get(key) ?? key;
}
