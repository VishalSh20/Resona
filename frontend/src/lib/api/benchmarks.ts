import { http } from "./client";
import type { BenchmarkDto, BenchmarkVersionDto } from "@/types/api";

export interface BenchmarkCreateInput {
  benchmark_key: string;
  name: string;
}

export interface BenchmarkVersionCreateInput {
  version: string;
  manifest?: Record<string, unknown> | null;
  manifest_hash?: string | null;
}

export const benchmarksApi = {
  list: () => http.get<BenchmarkDto[]>("/benchmarks"),
  get: (benchmarkId: string) =>
    http.get<BenchmarkDto>(`/benchmarks/${benchmarkId}`),
  create: (input: BenchmarkCreateInput) =>
    http.post<BenchmarkDto>("/benchmarks", input),
  createVersion: (
    benchmarkId: string,
    input: BenchmarkVersionCreateInput,
    idempotencyKey: string,
  ) =>
    http.post<BenchmarkVersionDto>(
      `/benchmarks/${benchmarkId}/versions`,
      input,
      { idempotencyKey },
    ),
  listVersions: (benchmarkId: string) =>
    http.get<BenchmarkVersionDto[]>(`/benchmarks/${benchmarkId}/versions`),
  freeze: (versionId: string, idempotencyKey: string) =>
    http.post<BenchmarkVersionDto>(
      `/benchmark-versions/${versionId}/freeze`,
      undefined,
      { idempotencyKey },
    ),
  getVersion: (versionId: string) =>
    http.get<BenchmarkVersionDto>(`/benchmark-versions/${versionId}`),
};
