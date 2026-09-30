import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  benchmarksApi,
  type BenchmarkCreateInput,
  type BenchmarkVersionCreateInput,
} from "@/lib/api/benchmarks";
import type { BenchmarkVersionDto } from "@/types/api";

export const benchmarkKeys = {
  all: ["benchmarks"] as const,
  detail: (benchmarkId: string) => ["benchmarks", benchmarkId] as const,
  versions: (benchmarkId: string) =>
    ["benchmarks", benchmarkId, "versions"] as const,
  version: (versionId: string) => ["benchmark-versions", versionId] as const,
};

export function useBenchmarks() {
  return useQuery({
    queryKey: benchmarkKeys.all,
    queryFn: benchmarksApi.list,
  });
}

export function useBenchmark(benchmarkId: string | undefined) {
  return useQuery({
    queryKey: benchmarkKeys.detail(benchmarkId ?? ""),
    queryFn: () => benchmarksApi.get(benchmarkId as string),
    enabled: Boolean(benchmarkId),
  });
}

export function useBenchmarkVersions(benchmarkId: string | undefined) {
  return useQuery({
    queryKey: benchmarkKeys.versions(benchmarkId ?? ""),
    queryFn: () => benchmarksApi.listVersions(benchmarkId as string),
    enabled: Boolean(benchmarkId),
  });
}

export function useBenchmarkVersion(versionId: string | undefined) {
  return useQuery({
    queryKey: benchmarkKeys.version(versionId ?? ""),
    queryFn: () => benchmarksApi.getVersion(versionId as string),
    enabled: Boolean(versionId),
  });
}

export function latestVersion(
  versions: BenchmarkVersionDto[] | undefined,
): BenchmarkVersionDto | undefined {
  if (!versions || versions.length === 0) return undefined;
  return versions.reduce((latest, version) => {
    const a = Number.parseFloat(version.version);
    const b = Number.parseFloat(latest.version);
    if (Number.isNaN(a) || Number.isNaN(b)) {
      return version.version > latest.version ? version : latest;
    }
    return a > b ? version : latest;
  });
}

export function useCreateBenchmark() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: BenchmarkCreateInput) =>
      benchmarksApi.create(input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: benchmarkKeys.all });
    },
  });
}

export function useCreateBenchmarkVersion(benchmarkId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      input,
      idempotencyKey,
    }: {
      input: BenchmarkVersionCreateInput;
      idempotencyKey: string;
    }) => benchmarksApi.createVersion(benchmarkId, input, idempotencyKey),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: benchmarkKeys.versions(benchmarkId),
      });
    },
  });
}

export function useFreezeBenchmarkVersion(benchmarkId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      versionId,
      idempotencyKey,
    }: {
      versionId: string;
      idempotencyKey: string;
    }) => benchmarksApi.freeze(versionId, idempotencyKey),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: benchmarkKeys.version(variables.versionId),
      });
      void queryClient.invalidateQueries({
        queryKey: benchmarkKeys.versions(benchmarkId),
      });
    },
  });
}
