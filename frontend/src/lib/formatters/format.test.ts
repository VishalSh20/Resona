import { describe, expect, it } from "vitest";

import { formatDurationMs, formatPercent, truncateId } from "./format";

describe("formatDurationMs", () => {
  it("formats sub-second durations in milliseconds", () => {
    expect(formatDurationMs(720)).toBe("720 ms");
  });

  it("formats second-scale durations", () => {
    expect(formatDurationMs(34800)).toBe("34.8 s");
  });

  it("returns an em dash for missing values", () => {
    expect(formatDurationMs(null)).toBe("—");
  });
});

describe("formatPercent", () => {
  it("formats ratios as percentages", () => {
    expect(formatPercent(0.907)).toBe("90.7%");
  });
});

describe("truncateId", () => {
  it("truncates prefixed ULIDs", () => {
    expect(truncateId("run_01J9FAX7Y2")).toBe("run_01J9…X7Y2");
  });
});
