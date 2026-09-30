import { Link, useParams } from "react-router-dom";
import { Snowflake } from "lucide-react";

import { DataTable, type DataTableColumn } from "@/components/data/DataTable";
import { CopyableId } from "@/components/domain/CopyableId";
import { HashBadge } from "@/components/domain/HashBadge";
import { ImmutableBadge } from "@/components/domain/ImmutableBadge";
import { JsonInspector } from "@/components/domain/JsonInspector";
import { MetaList } from "@/components/domain/MetaList";
import { PageHeader } from "@/components/domain/PageHeader";
import { ErrorState, LoadingState } from "@/components/domain/States";
import { StatusBadge } from "@/components/status/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  type BenchmarkCaseView,
  casesFromManifest,
} from "@/features/benchmarks/cases";
import {
  useBenchmark,
  useBenchmarkVersion,
  useFreezeBenchmarkVersion,
} from "@/features/benchmarks/queries";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { newIdempotencyKey } from "@/lib/api/idempotency";
import { formatTimestamp } from "@/lib/formatters/format";

const caseColumns: DataTableColumn<BenchmarkCaseView>[] = [
  { key: "sequenceNo", header: "#", align: "right" },
  { key: "caseKey", header: "Case key" },
  {
    key: "personality",
    header: "Personality",
    render: (row) => row.personality.join(", ") || "—",
  },
];

export function BenchmarkVersionPage() {
  const { benchmarkId = "", versionId = "" } = useParams();
  useDocumentTitle("Benchmark version");
  const benchmarkQuery = useBenchmark(benchmarkId);
  const versionQuery = useBenchmarkVersion(versionId);
  const freezeVersion = useFreezeBenchmarkVersion(benchmarkId);

  if (versionQuery.isLoading) {
    return <LoadingState label="Loading version…" />;
  }
  if (versionQuery.isError) {
    return (
      <ErrorState
        error={versionQuery.error}
        title="Could not load benchmark version."
        onRetry={() => void versionQuery.refetch()}
      />
    );
  }

  const version = versionQuery.data!;
  const frozen = version.status === "frozen";
  const cases = casesFromManifest(version.manifest);

  return (
    <div className="space-y-6">
      <PageHeader
        title={`${benchmarkQuery.data?.name ?? "Benchmark"} · v${version.version}`}
        description={
          <Link
            to={`/benchmarks/${benchmarkId}/overview`}
            className="hover:text-foreground"
          >
            Back to benchmark
          </Link>
        }
        meta={
          <>
            <StatusBadge status={version.status} />
            {frozen && <ImmutableBadge label="FROZEN" />}
            <CopyableId id={version.id} />
            <HashBadge hash={version.manifest_hash} />
          </>
        }
        actions={
          !frozen ? (
            <Button
              disabled={freezeVersion.isPending}
              onClick={() =>
                void freezeVersion.mutateAsync({
                  versionId,
                  idempotencyKey: newIdempotencyKey("benchmark:freeze"),
                })
              }
            >
              <Snowflake className="size-4" />
              {freezeVersion.isPending ? "Freezing…" : "Freeze version"}
            </Button>
          ) : undefined
        }
      />

      {freezeVersion.isError && (
        <ErrorState
          error={freezeVersion.error}
          title="Could not freeze version."
        />
      )}

      <Card className="gap-4 p-6">
        <MetaList
          items={[
            { label: "Version", value: <span className="font-mono">{version.version}</span> },
            { label: "Status", value: <StatusBadge status={version.status} /> },
            { label: "Cases", value: cases.length.toString() },
            { label: "Frozen at", value: formatTimestamp(version.frozen_at) },
            {
              label: "Manifest hash",
              value: <HashBadge hash={version.manifest_hash} />,
            },
          ]}
        />
      </Card>

      <section className="space-y-3">
        <h2 className="text-title-sm font-medium">Cases</h2>
        <DataTable
          columns={caseColumns}
          rows={cases}
          rowKey={(row) => `${row.sequenceNo}-${row.caseKey}`}
          emptyState="No cases in this version's manifest."
        />
      </section>

      <section className="space-y-3">
        <h2 className="text-title-sm font-medium">Manifest</h2>
        <JsonInspector value={version.manifest ?? {}} label="manifest" />
      </section>
    </div>
  );
}
