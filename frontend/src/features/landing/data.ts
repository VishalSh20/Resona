// ─────────────────────────────────────────────────────────────────────────────
// ILLUSTRATIVE LANDING DATA
// Every number/value below is demo content for the marketing page. It is NOT
// real aggregated production data. UI surfaces must label it as illustrative.
// ─────────────────────────────────────────────────────────────────────────────

export interface EvalMetric {
  key: string;
  label: string;
  value: number;
  suffix: string;
  fill: number;
}

export interface EvalCategory {
  id: string;
  label: string;
  metrics: EvalMetric[];
}

export const ILLUSTRATIVE_RUN = {
  name: "Customer Support",
  sample: "100 simulated conversations",
  code: "01",
  categories: [
    {
      id: "conversation",
      label: "Conversation quality",
      metrics: [
        { key: "relevancy", label: "Relevancy", value: 96, suffix: "%", fill: 0.96 },
        { key: "context", label: "Context retention", value: 92, suffix: "%", fill: 0.92 },
        { key: "instruction", label: "Instruction following", value: 95, suffix: "%", fill: 0.95 },
        { key: "empathy", label: "Empathy", value: 88, suffix: "%", fill: 0.88 },
      ],
    },
    {
      id: "voice",
      label: "Voice performance",
      metrics: [
        { key: "ttfa", label: "TTFA", value: 742, suffix: "ms", fill: 0.74 },
        { key: "barge-in", label: "Barge-in success", value: 97, suffix: "%", fill: 0.97 },
      ],
    },
    {
      id: "task",
      label: "Task & knowledge",
      metrics: [
        { key: "task", label: "Task completion", value: 94, suffix: "%", fill: 0.94 },
        { key: "groundedness", label: "Groundedness", value: 97, suffix: "%", fill: 0.97 },
        { key: "hallucination", label: "Hallucination", value: 2, suffix: "%", fill: 0.02 },
      ],
    },
  ] satisfies EvalCategory[],
};

export const PERSONAS = [
  "Frustrated",
  "Impatient",
  "Confused",
  "Skeptical",
  "Talkative",
  "Interrupting",
  "Cooperative",
  "Code-switching",
] as const;

export const PERSONA_TRAITS = [
  "Patience",
  "Assertiveness",
  "Technical knowledge",
  "Verbosity",
  "Emotional intensity",
  "Willingness to cooperate",
] as const;

export const CALL_AMBIENCE = ["Quiet", "Background noise", "People talking"] as const;

export const LANGUAGES = [
  { code: "EN", label: "English" },
  { code: "HI", label: "Hindi" },
  { code: "HINGLISH", label: "Hinglish" },
  { code: "MR", label: "Marathi" },
  { code: "TA", label: "Tamil" },
  { code: "TE", label: "Telugu" },
  { code: "BN", label: "Bengali" },
  { code: "KN", label: "Kannada" },
] as const;

export interface LanguageSample {
  code: string;
  label: string;
  text: string;
  majorLabel: string;
  majorRatio: number;
  minorLabel: string;
  minorRatio: number;
}

export const LANGUAGE_SAMPLES: LanguageSample[] = [
  {
    code: "HINGLISH",
    label: "Hinglish",
    text: "Bhai, mera order cancel karna hai — can you help me?",
    majorLabel: "Hindi / Hinglish",
    majorRatio: 0.55,
    minorLabel: "English",
    minorRatio: 0.45,
  },
  {
    code: "TAMIL",
    label: "Tamil",
    text: "Enna nadakkuthu nu paarunga, I need a refund.",
    majorLabel: "Tamil",
    majorRatio: 0.6,
    minorLabel: "English",
    minorRatio: 0.4,
  },
  {
    code: "TELUGU",
    label: "Telugu",
    text: "Naaku refund kavali, please check my order.",
    majorLabel: "Telugu",
    majorRatio: 0.58,
    minorLabel: "English",
    minorRatio: 0.42,
  },
  {
    code: "MARATHI",
    label: "Marathi",
    text: "Maza order cancel kara, please help me.",
    majorLabel: "Marathi",
    majorRatio: 0.6,
    minorLabel: "English",
    minorRatio: 0.4,
  },
];

export const LANGUAGE_CHECKS = [
  "Language detection",
  "Code-switching",
  "Semantic preservation",
  "Language consistency",
] as const;

export interface ConversationEvent {
  label: string;
  state: "ok" | "warn";
}

export const CONVERSATION_EVENTS: ConversationEvent[] = [
  { label: "Call starts", state: "ok" },
  { label: "Caller asks a question", state: "ok" },
  { label: "Caller interrupts the agent", state: "ok" },
  { label: "Caller switches language", state: "warn" },
  { label: "Caller changes the request", state: "warn" },
  { label: "Background noise", state: "ok" },
  { label: "Task completed", state: "ok" },
];

export interface DiffRow {
  label: string;
  from: number;
  to: number;
  suffix: string;
  lowerIsBetter?: boolean;
}

export const VERSION_DIFF = {
  from: "v1.4",
  to: "v1.5",
  rows: [
    { label: "Task completion", from: 87, to: 94, suffix: "%" },
    { label: "Relevancy", from: 91, to: 96, suffix: "%" },
    { label: "Barge-in", from: 94, to: 98, suffix: "%" },
    { label: "Groundedness", from: 93, to: 97, suffix: "%" },
    { label: "TTFA", from: 620, to: 710, suffix: "ms", lowerIsBetter: true },
  ] satisfies DiffRow[],
  summary: { improved: 4, regressed: 1, overallFrom: 91, overallTo: 95 },
};

export const COVERAGE_DIMENSIONS = [
  "Languages",
  "Personas",
  "Scenarios",
  "Ambience",
  "Metrics",
  "Edge cases",
] as const;

export const OBJECTIVE_SIGNALS = [
  "TTFA",
  "TTFT",
  "Barge-in",
  "Language detection",
  "Task completion signals",
] as const;

export const JUDGMENT_SIGNALS = [
  "Relevancy",
  "Empathy",
  "Instruction following",
  "Semantic preservation",
  "Groundedness",
] as const;

export interface ProvenanceNode {
  key: string;
  label: string;
  detail: string;
}

export const PROVENANCE_NODES: ProvenanceNode[] = [
  { key: "audio", label: "Audio", detail: "Signed call recording" },
  { key: "transcript", label: "Transcript", detail: "“I need to cancel my order…”" },
  { key: "evaluation", label: "Evaluation", detail: "Relevancy · call #382" },
  { key: "metric", label: "Metric", detail: "Relevancy 96%" },
  {
    key: "reasoning",
    label: "Reasoning",
    detail: "“Response directly addressed the request.”",
  },
];

export const PROVIDERS = [
  { slug: "elevenlabs", name: "ElevenLabs" },
  { slug: "vapi", name: "Vapi" },
  { slug: "retell", name: "Retell" },
  { slug: "livekit", name: "LiveKit" },
  { slug: "pipecat", name: "Pipecat" },
] as const;
