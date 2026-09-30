import { describe, expect, it } from "vitest";

import { resolveStatusTone, statusLabel } from "./status";

describe("statusLabel", () => {
  it("maps known statuses to uppercase display labels", () => {
    expect(statusLabel("running")).toBe("RUNNING");
    expect(statusLabel("not_available")).toBe("NOT AVAILABLE");
  });

  it("falls back to humanized labels for unknown statuses", () => {
    expect(statusLabel("infrastructure_failed")).toBe("INFRASTRUCTURE FAILED");
    expect(statusLabel(null)).toBe("UNKNOWN");
  });
});

describe("resolveStatusTone", () => {
  it("maps metric and execution statuses to semantic tones", () => {
    expect(resolveStatusTone("computed")).toBe("success");
    expect(resolveStatusTone("failed")).toBe("danger");
    expect(resolveStatusTone("not_available")).toBe("muted");
    expect(resolveStatusTone("running")).toBe("info");
  });
});
