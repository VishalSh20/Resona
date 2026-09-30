import { describe, expect, it } from "vitest";

import { casesFromManifest } from "./cases";

describe("casesFromManifest", () => {
  it("reads and sorts cases by sequence number", () => {
    const cases = casesFromManifest({
      cases: [
        {
          case_key: "b",
          case_definition: {
            scenario: "s2",
            personality: ["IMPATIENT"],
          },
          sequence_no: 2,
        },
        {
          case_key: "a",
          case_definition: {
            scenario: "s1",
            personality: ["SKEPTICAL"],
          },
          sequence_no: 1,
        },
      ],
    });
    expect(cases.map((item) => item.caseKey)).toEqual(["a", "b"]);
    expect(cases[0].personality).toEqual(["SKEPTICAL"]);
    expect(cases[0].scenario).toBe("s1");
  });

  it("accepts inline RunEvaluator-compatible fields", () => {
    const cases = casesFromManifest({
      cases: [{ scenario: "s", personality: ["CONCISE"] }],
    });
    expect(cases).toHaveLength(1);
    expect(cases[0].caseKey).toBe("case_1");
    expect(cases[0].personality).toEqual(["CONCISE"]);
  });

  it("returns an empty list when there is no cases array", () => {
    expect(casesFromManifest(null)).toEqual([]);
    expect(casesFromManifest({})).toEqual([]);
  });
});
