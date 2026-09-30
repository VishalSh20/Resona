import { Link, useNavigate, useParams } from "react-router-dom";
import { Plus } from "lucide-react";

import { DataTable, type DataTableColumn } from "@/components/data/DataTable";
import { HashBadge } from "@/components/domain/HashBadge";
import { MetaList } from "@/components/domain/MetaList";
import { PageHeader } from "@/components/domain/PageHeader";
import { ErrorState, LoadingState } from "@/components/domain/States";
import { StatusBadge } from "@/components/status/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { casesFromManifest } from "@/features/benchmarks/cases";
import {
  latestVersion,
  useBenchmark,
  useBenchmarkVersions,
} from "@/features/benchmarks/queries";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { formatTimestamp } from "@/lib/formatters/format";
import type { BenchmarkVersionDto } from "@/types/api";

const columns: DataTableColumn<BenchmarkVersionDto>[] = [
  {
    key: "version",
    header: "Version",
    render: (row) => <span className="font-mono">{row.version}</span>,
  },
  {
    key: "status",
    header: "Status",
    render: (row) => <StatusBadge status={row.status} />,
  },
  {
    key: "cases",
    header: "Cases",
    align: "right",
    render: (row) => {
      const cases = casesFromManifest(row.manifest);
      return cases.length > 0 ? cases.length.toString() : "—";
    },
  },
  {
    key: "manifest_hash",
    header: "Manifest hash",
    render: (row) => <HashBadge hash={row.manifest_hash} />,
  },
  {
    key: "frozen_at",
    header: "Frozen",
    render: (row) => formatTimestamp(row.frozen_at),
  },
];

export function BenchmarkOverviewPage() {
  const { benchmarkId = "" } = useParams();
  useDocumentTitle("Benchmark");
  const navigate = useNavigate();
  const benchmarkQuery = useBenchmark(benchmarkId);
  const versionsQuery = useBenchmarkVersions(benchmarkId);

  if (benchmarkQuery.isLoading) {
    return <LoadingState label="Loading benchmark…" />;
  }
  if (benchmarkQuery.isError) {
    return (
      <ErrorState
        error={benchmarkQuery.error}
        title="Could not load benchmark."
        onRetry={() => void benchmarkQuery.refetch()}
      />
    );
  }

  const benchmark = benchmarkQuery.data!;
  const versions = versionsQuery.data ?? [];
  const latest = latestVersion(versions);

  return (
    <div className="space-y-6">
      <PageHeader
        title={benchmark.name}
        description={benchmark.benchmark_key}
        actions={
          <Button asChild>
            <Link to={`/benchmarks/${benchmark.id}/versions/new`}>
              <Plus className="size-4" /> New version
            </Link>
          </Button>
        }
      />

      <Card className="gap-4 p-6">
        <h2 className="text-title-sm font-medium">Benchmark</h2>
        <MetaList
          items={[
            { label: "Key", value: benchmark.benchmark_key },
            { label: "Versions", value: versions.length.toString() },
            {
              label: "Latest version",
              value: latest ? (
                <span className="flex items-center gap-2">
                  <span className="font-mono">{latest.version}</span>
                  <StatusBadge status={latest.status} />
                </span>
              ) : (
                "—"
              ),
            },
          ]}
        />
      </Card>

      <section className="space-y-3">
        <h2 className="text-title-sm font-medium">Versions</h2>
        <DataTable
          columns={columns}
          rows={versions}
          rowKey={(row) => row.id}
          onRowClick={(row) =>
            navigate(`/app/benchmarks/${benchmark.id}/versions/${row.id}`)
          }
          emptyState="No versions yet. Create a version to define a reproducible suite."
        />
      </section>
    </div>
  );
}
