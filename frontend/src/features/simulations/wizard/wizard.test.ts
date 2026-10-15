import { describe, expect, it } from "vitest";

import { CALL_AMBIENCE_OPTIONS } from "@/lib/constants/ambience";
import { isEvaluatorCountValid } from "./types";

describe("isEvaluatorCountValid", () => {
  it("accepts whole numbers in the 1–100 range", () => {
    expect(isEvaluatorCountValid(1)).toBe(true);
    expect(isEvaluatorCountValid(20)).toBe(true);
    expect(isEvaluatorCountValid(100)).toBe(true);
  });

  it("rejects out-of-range and non-integer values", () => {
    expect(isEvaluatorCountValid(0)).toBe(false);
    expect(isEvaluatorCountValid(101)).toBe(false);
    expect(isEvaluatorCountValid(2.5)).toBe(false);
    expect(isEvaluatorCountValid(undefined)).toBe(false);
  });
});

describe("CALL_AMBIENCE_OPTIONS", () => {
  it("mirrors the backend CallAmbience enum keys", () => {
    expect(CALL_AMBIENCE_OPTIONS.map((option) => option.key)).toEqual([
      "QUIET",
      "NOISY",
      "PEOPLE_TALKING",
      "MUSIC",
      "TRAFFIC",
      "OFFICE",
      "CALL_CENTRE",
      "CAR",
    ]);
  });
});
