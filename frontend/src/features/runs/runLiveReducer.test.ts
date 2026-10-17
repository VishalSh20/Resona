import { describe, expect, it, vi } from "vitest";
import { QueryClient } from "@tanstack/react-query";

import { callRunKeys, runKeys } from "@/lib/queryKeys";
import type { RunDto } from "@/types/api";

import { applyRunLiveEvent } from "./runLiveReducer";

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
}

const run: RunDto = {
  id: "run_1",
  simulation_id: "sim_1",
  target_revision_id: "rev_1",
  evaluator_count: 3,
  status: "queued",
};

describe("applyRunLiveEvent", () => {
  it("patches run status in place, preserving other fields", () => {
    const queryClient = makeClient();
    queryClient.setQueryData(runKeys.detail("run_1"), run);

    applyRunLiveEvent(queryClient, "run_1", {
      type: "run.status.changed",
      data: { run_id: "run_1", status: "running" },
    });

    const updated = queryClient.getQueryData<RunDto>(runKeys.detail("run_1"));
    expect(updated?.status).toBe("running");
    expect(updated?.simulation_id).toBe("sim_1");
  });

  it("stores run.progress payload", () => {
    const queryClient = makeClient();

    applyRunLiveEvent(queryClient, "run_1", {
      type: "run.progress",
      data: { run_id: "run_1", total: 3, queued: 1, running: 2 },
    });

    expect(queryClient.getQueryData(runKeys.progress("run_1"))).toMatchObject({
      total: 3,
      running: 2,
    });
  });

  it("invalidates the call run's attempts on attempt.status.changed", () => {
    const queryClient = makeClient();
    const spy = vi.spyOn(queryClient, "invalidateQueries");

    applyRunLiveEvent(queryClient, "run_1", {
      type: "attempt.status.changed",
      data: { attempt_id: "att_1", call_run_id: "cr_1", status: "starting" },
    });

    expect(spy).toHaveBeenCalledWith({
      queryKey: callRunKeys.attempts("cr_1"),
    });
  });

  it("invalidates the calls list on call_run.status.changed", () => {
    const queryClient = makeClient();
    const spy = vi.spyOn(queryClient, "invalidateQueries");

    applyRunLiveEvent(queryClient, "run_1", {
      type: "call_run.status.changed",
      data: { call_run_id: "cr_1", status: "completed" },
    });

    expect(spy).toHaveBeenCalledWith({ queryKey: runKeys.callRuns("run_1") });
  });
});
