import { Link, useNavigate } from "react-router-dom";
import { useQueries } from "@tanstack/react-query";
import { Plus } from "lucide-react";

import { DataTable, type DataTableColumn } from "@/components/data/DataTable";
import { PageHeader } from "@/components/domain/PageHeader";
import { ErrorState, LoadingState } from "@/components/domain/States";
import { StatusBadge } from "@/components/status/StatusBadge";
import { Button } from "@/components/ui/button";
import { casesFromManifest } from "@/features/benchmarks/cases";
import { latestVersion, useBenchmarks } from "@/features/benchmarks/queries";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { benchmarksApi } from "@/lib/api/benchmarks";
import { formatTimestamp } from "@/lib/formatters/format";
import type { BenchmarkDto, BenchmarkVersionDto } from "@/types/api";

interface BenchmarkRow {
  benchmark: BenchmarkDto;
  latest?: BenchmarkVersionDto;
}

const columns: DataTableColumn<BenchmarkRow>[] = [
  {
    key: "name",
    header: "Benchmark",
    render: (row) => <span className="font-medium">{row.benchmark.name}</span>,
  },
  {
    key: "key",
    header: "Key",
    render: (row) => (
      <span className="font-mono text-micro">
        {row.benchmark.benchmark_key}
      </span>
    ),
  },
  {
    key: "version",
    header: "Latest version",
    align: "right",
    render: (row) => (row.latest ? row.latest.version : "—"),
  },
  {
    key: "cases",
    header: "Cases",
    align: "right",
    render: (row) => {
      if (!row.latest) return "—";
      const cases = casesFromManifest(row.latest.manifest);
      return cases.length > 0 ? cases.length.toString() : "—";
    },
  },
  {
    key: "status",
    header: "Status",
    render: (row) =>
      row.latest ? <StatusBadge status={row.latest.status} /> : "—",
  },
  {
    key: "frozen",
    header: "Last frozen",
    render: (row) => formatTimestamp(row.latest?.frozen_at),
  },
];

export function BenchmarkListPage() {
  useDocumentTitle("Benchmarks");
  const navigate = useNavigate();
  const benchmarksQuery = useBenchmarks();
  const benchmarks = benchmarksQuery.data ?? [];

  const versionQueries = useQueries({
    queries: benchmarks.map((benchmark) => ({
      queryKey: ["benchmarks", benchmark.id, "versions"],
      queryFn: () => benchmarksApi.listVersions(benchmark.id),
    })),
  });

  const rows: BenchmarkRow[] = benchmarks.map((benchmark, index) => ({
    benchmark,
    latest: latestVersion(versionQueries[index]?.data),
  }));

  if (benchmarksQuery.isLoading) {
    return <LoadingState label="Loading benchmarks…" />;
  }
  if (benchmarksQuery.isError) {
    return (
      <ErrorState
        error={benchmarksQuery.error}
        title="Could not load benchmarks."
        onRetry={() => void benchmarksQuery.refetch()}
      />
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Benchmarks"
        description="Reproducible evaluation suites over evaluator revisions."
        actions={
          <Button asChild>
            <Link to="/app/benchmarks/new">
              <Plus className="size-4" /> New benchmark
            </Link>
          </Button>
        }
      />
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(row) => row.benchmark.id}
        onRowClick={(row) =>
          navigate(`/app/benchmarks/${row.benchmark.id}/overview`)
        }
        emptyState="No benchmarks yet. Create a benchmark version to define a reproducible evaluation suite."
      />
    </div>
  );
}
