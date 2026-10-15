export interface PersonalityOption {
  key: string;
  label: string;
  description: string;
}

// Composable caller-personality traits (mirrors the backend `Personality` enum).
export const PERSONALITY_OPTIONS: PersonalityOption[] = [
  {
    key: "SUPPORTIVE",
    label: "Supportive",
    description: "Warm and cooperative, ready to help the agent succeed.",
  },
  {
    key: "CONCISE",
    label: "Concise",
    description: "Short, to-the-point replies with little small talk.",
  },
  {
    key: "VERBOSE",
    label: "Verbose",
    description: "Long, detailed replies that over-explain.",
  },
  {
    key: "ABUSIVE",
    label: "Abusive",
    description: "Hostile and rude, testing the agent's composure.",
  },
  {
    key: "INTERRUPTOR",
    label: "Interruptor",
    description: "Frequently talks over the agent mid-sentence.",
  },
  {
    key: "IMPATIENT",
    label: "Impatient",
    description: "In a hurry, with low tolerance for delays.",
  },
  {
    key: "CONFUSED",
    label: "Confused",
    description: "Unclear about what they need or how to proceed.",
  },
  {
    key: "SKEPTICAL",
    label: "Skeptical",
    description: "Doubts the agent's answers and asks for proof.",
  },
  {
    key: "COOPERATIVE",
    label: "Cooperative",
    description: "Follows the agent's guidance without friction.",
  },
  {
    key: "UNCOOPERATIVE",
    label: "Uncooperative",
    description: "Resists or ignores the agent's requests.",
  },
  {
    key: "HESITANT",
    label: "Hesitant",
    description: "Unsure and slow to commit to a decision.",
  },
  {
    key: "REPETITIVE",
    label: "Repetitive",
    description: "Restates the same point or question repeatedly.",
  },
  {
    key: "EMOTIONAL",
    label: "Emotional",
    description: "Reacts with strong feelings when frustrated or relieved.",
  },
  {
    key: "DEMANDING",
    label: "Demanding",
    description: "Expects immediate, precise resolution.",
  },
];

const PERSONALITY_LABELS = new Map(
  PERSONALITY_OPTIONS.map((p) => [p.key, p.label]),
);

export function personalityLabel(key: string): string {
  return PERSONALITY_LABELS.get(key) ?? key;
}
