export interface AmbienceOption {
  key: string;
  label: string;
}

// Environmental conditions mixed into the caller's line during a call. Mirrors
// the backend `CallAmbience` enum (the recommended starting values).
export const CALL_AMBIENCE_OPTIONS: AmbienceOption[] = [
  { key: "QUIET", label: "Quiet" },
  { key: "NOISY", label: "Noisy" },
  { key: "PEOPLE_TALKING", label: "People talking" },
  { key: "MUSIC", label: "Music" },
  { key: "TRAFFIC", label: "Traffic" },
  { key: "OFFICE", label: "Office" },
  { key: "CALL_CENTRE", label: "Call centre" },
  { key: "CAR", label: "Car" },
];

const CALL_AMBIENCE_LABELS = new Map(
  CALL_AMBIENCE_OPTIONS.map((a) => [a.key, a.label]),
);

export function callAmbienceLabel(key: string): string {
  return CALL_AMBIENCE_LABELS.get(key) ?? key;
}
