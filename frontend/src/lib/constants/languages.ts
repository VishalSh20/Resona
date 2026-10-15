export interface LanguageOption {
  key: string;
  label: string;
}

// Common caller languages. The backend `languages` field is extensible JSONB;
// these are the recommended starting values.
export const LANGUAGE_OPTIONS: LanguageOption[] = [
  { key: "en", label: "English" },
  { key: "hi", label: "Hindi" },
  { key: "hinglish", label: "Hinglish" },
  { key: "mr", label: "Marathi" },
  { key: "ta", label: "Tamil" },
  { key: "te", label: "Telugu" },
  { key: "bn", label: "Bengali" },
  { key: "kn", label: "Kannada" },
];

const LANGUAGE_LABELS = new Map(LANGUAGE_OPTIONS.map((l) => [l.key, l.label]));

export function languageLabel(key: string): string {
  return LANGUAGE_LABELS.get(key) ?? key;
}
