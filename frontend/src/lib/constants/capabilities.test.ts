import { describe, expect, it } from "vitest";

import {
  countAvailableCapabilities,
  emptyCapabilitySnapshot,
  isCapabilityAvailable,
} from "./capabilities";

describe("capability helpers", () => {
  it("counts available capabilities against the total", () => {
    const snapshot = emptyCapabilitySnapshot();
    snapshot.audio.caller_ingress = true;
    snapshot.tools.calls = true;
    const { available, total } = countAvailableCapabilities(snapshot);
    expect(available).toBe(2);
    expect(total).toBe(11);
  });

  it("reads nested availability defensively", () => {
    expect(
      isCapabilityAvailable(
        { audio: { caller_ingress: true } },
        "audio",
        "caller_ingress",
      ),
    ).toBe(true);
    expect(isCapabilityAvailable(null, "audio", "caller_ingress")).toBe(false);
  });
});
