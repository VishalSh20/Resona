export interface BenchmarkCaseView {
  caseKey: string;
  sequenceNo: number;
  personality: string[];
  scenario: string;
}

// A benchmark case now carries an immutable RunEvaluator-compatible
// `case_definition` (scenario, expected_output_prompt, metrics, languages,
// personality). The manifest is client-supplied JSONB.
function definitionFromItem(
  item: Record<string, unknown>,
): Record<string, unknown> {
  const raw = item.case_definition ?? item.caseDefinition;
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    return raw as Record<string, unknown>;
  }
  const definition: Record<string, unknown> = {};
  for (const key of [
    "scenario",
    "expected_output_prompt",
    "metrics",
    "languages",
    "personality",
  ]) {
    if (item[key] !== undefined) definition[key] = item[key];
  }
  return definition;
}

export function casesFromManifest(
  manifest: Record<string, unknown> | null | undefined,
): BenchmarkCaseView[] {
  const raw = manifest?.cases;
  if (!Array.isArray(raw)) return [];
  return raw
    .filter(
      (item): item is Record<string, unknown> =>
        Boolean(item) && typeof item === "object",
    )
    .map((item, index) => {
      const definition = definitionFromItem(item);
      return {
        caseKey: String(item.case_key ?? item.caseKey ?? `case_${index + 1}`),
        sequenceNo:
          typeof item.sequence_no === "number" ? item.sequence_no : index + 1,
        personality: Array.isArray(definition.personality)
          ? definition.personality.map(String)
          : [],
        scenario: typeof definition.scenario === "string" ? definition.scenario : "",
      };
    })
    .sort((a, b) => a.sequenceNo - b.sequenceNo);
}
