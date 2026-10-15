import { useNavigate } from "react-router-dom";

import { DataTable, type DataTableColumn } from "@/components/data/DataTable";
import { ErrorState, LoadingState } from "@/components/domain/States";
import type { SimulationDto } from "@/types/api";

const columns: DataTableColumn<SimulationDto>[] = [
  {
    key: "name",
    header: "Simulation",
    render: (row) => (
      <div className="flex flex-col">
        <span className="font-medium">{row.name}</span>
        {row.description && (
          <span className="line-clamp-1 text-micro text-muted-foreground">
            {row.description}
          </span>
        )}
      </div>
    ),
  },
  {
    key: "evaluator_count",
    header: "Evaluators",
    align: "right",
    render: (row) => row.evaluator_count.toString(),
  },
  {
    key: "metrics",
    header: "Metrics",
    align: "right",
    render: (row) => row.metric_set.length.toString(),
  },
  {
    key: "personalities",
    header: "Personalities",
    align: "right",
    render: (row) => row.personalities.length.toString(),
  },
];

interface SimulationsSectionProps {
  simulations: SimulationDto[];
  isLoading?: boolean;
  isError?: boolean;
  error?: unknown;
  onRetry?: () => void;
  emptyMessage: string;
}

export function SimulationsSection({
  simulations,
  isLoading,
  isError,
  error,
  onRetry,
  emptyMessage,
}: SimulationsSectionProps) {
  const navigate = useNavigate();

  return (
    <section className="space-y-3">
      {isError ? (
        <ErrorState
          error={error}
          title="Could not load simulations."
          onRetry={onRetry}
        />
      ) : isLoading ? (
        <LoadingState label="Loading simulations…" />
      ) : (
        <DataTable
          columns={columns}
          rows={simulations}
          rowKey={(row) => row.id}
          onRowClick={(row) => navigate(`/app/simulations/${row.id}`)}
          emptyState={emptyMessage}
        />
      )}
    </section>
  );
}
