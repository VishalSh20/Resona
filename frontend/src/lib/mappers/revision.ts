import type { AgentRevisionDto } from "@/types/api";

export type RevisionConfigKey =
  | "llm_config"
  | "stt_config"
  | "tts_config"
  | "turn_config"
  | "conversation_config"
  | "tools_config"
  | "variables_config"
  | "knowledge_config"
  | "workflow_config"
  | "handoffs_config"
  | "guardrails_config";

export interface RevisionConfigSection {
  key: RevisionConfigKey;
  label: string;
  description: string;
}

// Ordered the way a reader reasons about an agent: what it thinks with, how it
// hears and speaks, how it takes turns, then the capabilities around it.
export const REVISION_CONFIG_SECTIONS: RevisionConfigSection[] = [
  {
    key: "llm_config",
    label: "Language model",
    description: "Model, instructions, and generation settings.",
  },
  {
    key: "stt_config",
    label: "Speech recognition",
    description: "Speech-to-text and transcription setup.",
  },
  {
    key: "tts_config",
    label: "Voice",
    description: "Text-to-speech and voice selection.",
  },
  {
    key: "turn_config",
    label: "Turn taking",
    description: "Turn detection, responsiveness, and interruptions.",
  },
  {
    key: "conversation_config",
    label: "Conversation",
    description: "Call-level conversation behavior.",
  },
  {
    key: "tools_config",
    label: "Tools",
    description: "Tools the agent can invoke.",
  },
  {
    key: "variables_config",
    label: "Variables",
    description: "Dynamic variables available to the agent.",
  },
  {
    key: "knowledge_config",
    label: "Knowledge",
    description: "Knowledge bases the agent can draw on.",
  },
  {
    key: "workflow_config",
    label: "Workflow",
    description: "Conversation graph: states, nodes, and transitions.",
  },
  {
    key: "handoffs_config",
    label: "Handoffs",
    description: "Transfer to other agents or humans.",
  },
  {
    key: "guardrails_config",
    label: "Guardrails",
    description: "Safety and policy constraints.",
  },
];

function isNonEmptyConfig(value: unknown): boolean {
  if (Array.isArray(value)) return value.length > 0;
  if (value && typeof value === "object") return Object.keys(value).length > 0;
  if (typeof value === "string") return value.trim().length > 0;
  return value != null;
}

export interface ResolvedRevisionConfigSection {
  section: RevisionConfigSection;
  value: unknown;
}

export function revisionConfigSections(
  revision: AgentRevisionDto,
): ResolvedRevisionConfigSection[] {
  return REVISION_CONFIG_SECTIONS.map((section) => ({
    section,
    value: revision[section.key] as unknown,
  })).filter((entry) => isNonEmptyConfig(entry.value));
}

export interface RevisionHeadline {
  model?: string;
  voice?: string;
  language?: string;
  toolCount?: number;
  knowledgeCount?: number;
  variableCount?: number;
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

function pick(
  record: Record<string, unknown> | undefined,
  keys: string[],
): unknown {
  if (!record) return undefined;
  for (const key of keys) {
    const value = record[key];
    if (value != null && value !== "") return value;
  }
  return undefined;
}

function firstString(...values: unknown[]): string | undefined {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) return value;
    if (typeof value === "number") return String(value);
  }
  return undefined;
}

function countItems(value: unknown): number | undefined {
  if (Array.isArray(value)) return value.length || undefined;
  const record = asRecord(value);
  if (!record) return undefined;
  for (const key of ["tools", "procedures", "items", "entries"]) {
    const nested = record[key];
    if (Array.isArray(nested)) return nested.length || undefined;
  }
  const keys = Object.keys(record);
  return keys.length || undefined;
}

// Best-effort, provider-tolerant extraction of the few fields worth surfacing
// as a summary. Anything a provider doesn't expose simply stays undefined.
export function revisionHeadline(revision: AgentRevisionDto): RevisionHeadline {
  const llm = asRecord(revision.llm_config);
  const stt = asRecord(revision.stt_config);
  const tts = asRecord(revision.tts_config);
  const nestedVoice = asRecord(pick(tts, ["voice"]));
  const knowledge = asRecord(revision.knowledge_config);

  const language = firstString(
    pick(stt, ["language", "language_code", "languageCode", "lang"]),
    pick(llm, ["language", "language_code", "languageCode"]),
    pick(tts, ["language", "language_code", "languageCode"]),
  );

  return {
    model: firstString(
      pick(llm, ["model", "model_name", "modelName", "model_id"]),
    ),
    voice: firstString(
      pick(tts, ["voice_id", "voiceId", "voice", "voice_model", "voiceModel", "voice_name"]),
      pick(nestedVoice, ["voice_id", "voiceId", "name"]),
    ),
    language,
    toolCount: countItems(revision.tools_config),
    knowledgeCount: countItems(
      pick(knowledge, ["knowledge_base_ids", "knowledgeBases", "ids", "collections"]) ??
        revision.knowledge_config,
    ),
    variableCount: countItems(revision.variables_config),
  };
}

const REVISION_TYPE_LABELS: Record<string, string> = {
  AGENT_CONFIGURATION: "Configuration",
  DEPLOYMENT: "Deployment",
};

const SOURCE_KIND_LABELS: Record<string, string> = {
  IMPORTED: "Imported",
  MANUAL: "Manual",
};

export function revisionTypeLabel(
  type: string | null | undefined,
): string | undefined {
  if (!type) return undefined;
  return REVISION_TYPE_LABELS[type] ?? type;
}

export function sourceKindLabel(kind: string | null | undefined): string {
  if (!kind) return "—";
  return SOURCE_KIND_LABELS[kind] ?? kind;
}
