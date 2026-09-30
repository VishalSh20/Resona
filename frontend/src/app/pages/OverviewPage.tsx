import { useMemo, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CheckCircle2, FilePlus2, PlayCircle, Plus } from "lucide-react";

import { DataTable, type DataTableColumn } from "@/components/data/DataTable";
import { ProgressBar } from "@/components/data/ProgressBar";
import { PageHeader } from "@/components/domain/PageHeader";
import { EmptyState, ErrorState, LoadingState } from "@/components/domain/States";
import { StatusBadge } from "@/components/status/StatusBadge";
import { Button } from "@/components/ui/button";
import { useAgents } from "@/features/agents/queries";
import { useAllRuns, useRunComposite } from "@/features/overview/queries";
import { useRunCallRuns } from "@/features/runs/queries";
import { useSimulations } from "@/features/simulations/queries";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { formatRelativeTime } from "@/lib/formatters/format";
import type { RunDto, SimulationDto } from "@/types/api";

type ActivityKind = "created" | "started" | "completed";

interface ActivityItem {
  id: string;
  kind: ActivityKind;
  label: string;
  at: string;
}

const ACTIVITY_ICONS: Record<ActivityKind, typeof PlayCircle> = {
  created: FilePlus2,
  started: PlayCircle,
  completed: CheckCircle2,
};

function buildActivity(
  runs: RunDto[],
  simulations: SimulationDto[],
  simulationNames: Map<string, string>,
): ActivityItem[] {
  const items: ActivityItem[] = [];

  for (const simulation of simulations) {
    if (simulation.created_at) {
      items.push({
        id: `simulation-created-${simulation.id}`,
        kind: "created",
        label: `Simulation "${simulation.name}" created`,
        at: simulation.created_at,
      });
    }
  }

  for (const run of runs) {
    const name = simulationNames.get(run.simulation_id) ?? "Simulation";
    if (run.started_at) {
      items.push({
        id: `run-started-${run.id}`,
        kind: "started",
        label: `${name} · run started`,
        at: run.started_at,
      });
    }
    if (run.status === "completed" && run.finished_at) {
      items.push({
        id: `run-completed-${run.id}`,
        kind: "completed",
        label: `${name} · run completed`,
        at: run.finished_at,
      });
    }
  }

  return items
    .sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime())
    .slice(0, 6);
}

function StatCard({
  label,
  value,
  to,
}: {
  label: string;
  value: ReactNode;
  to: string;
}) {
  return (
    <Link
      to={to}
      className="rounded-lg border border-border bg-surface p-5 transition-colors hover:bg-muted/50"
    >
      <p className="text-label uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="mt-2 text-display-md font-medium tabular-nums">{value}</p>
    </Link>
  );
}

function SectionHeading({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      <h2 className="text-label uppercase tracking-wide text-muted-foreground">
        {children}
      </h2>
      <div className="h-px flex-1 bg-border" />
    </div>
  );
}

function ActiveRunProgress({ runId }: { runId: string }) {
  const callRunsQuery = useRunCallRuns(runId);

  if (callRunsQuery.isLoading) {
    return <span className="text-micro text-muted-foreground">Loading…</span>;
  }

  const calls = callRunsQuery.data ?? [];
  if (calls.length === 0) {
    return <span className="text-micro text-muted-foreground">No calls yet</span>;
  }

  return (
    <ProgressBar
      total={calls.length}
      completed={calls.filter((call) => call.status === "completed").length}
      running={calls.filter((call) => call.status === "running").length}
      failed={
        calls.filter((call) => call.status === "infrastructure_failed").length
      }
      className="w-56"
    />
  );
}

function RecentResultScore({ runId }: { runId: string }) {
  const compositeQuery = useRunComposite(runId);

  if (compositeQuery.isLoading) {
    return <span className="text-micro text-muted-foreground">…</span>;
  }

  const score = compositeQuery.data?.score_0_100;
  if (score == null) {
    return <span className="text-muted-foreground">—</span>;
  }
  return <span className="font-medium tabular-nums">{Math.round(score)}%</span>;
}

function ActivityFeed({ items }: { items: ActivityItem[] }) {
  if (items.length === 0) {
    return <EmptyState message="No activity yet." />;
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface">
      <ul>
        {items.map((item) => {
          const Icon = ACTIVITY_ICONS[item.kind];
          return (
            <li
              key={item.id}
              className="flex items-center gap-3 border-b border-border px-4 py-3 last:border-b-0"
            >
              <Icon className="size-4 shrink-0 text-muted-foreground" />
              <span className="min-w-0 flex-1 truncate text-body-sm">
                {item.label}
              </span>
              <span className="shrink-0 text-micro text-muted-foreground">
                {formatRelativeTime(item.at)}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function OverviewPage() {
  useDocumentTitle("Overview");
  const navigate = useNavigate();

  const agentsQuery = useAgents();
  const simulationsQuery = useSimulations();
  const runsData = useAllRuns();

  const simulations = simulationsQuery.data ?? [];
  const runs = runsData.runs;

  const simulationNames = useMemo(
    () => new Map(simulations.map((simulation) => [simulation.id, simulation.name])),
    [simulations],
  );

  const activeRuns = useMemo(
    () =>
      runs
        .filter((run) => run.status === "queued" || run.status === "running")
        .sort((a, b) => (b.started_at ?? "").localeCompare(a.started_at ?? "")),
    [runs],
  );

  const recentRuns = useMemo(
    () =>
      runs
        .filter((run) => run.status === "completed")
        .sort((a, b) => (b.finished_at ?? "").localeCompare(a.finished_at ?? ""))
        .slice(0, 5),
    [runs],
  );

  const activity = useMemo(
    () => buildActivity(runs, simulations, simulationNames),
    [runs, simulations, simulationNames],
  );

  if (simulationsQuery.isLoading) {
    return <LoadingState label="Loading overview…" />;
  }

  if (simulationsQuery.isError) {
    return (
      <ErrorState
        error={simulationsQuery.error}
        title="Could not load overview."
        onRetry={() => void simulationsQuery.refetch()}
      />
    );
  }

  const runName = (run: RunDto) =>
    simulationNames.get(run.simulation_id) ?? "Simulation";
  const goToRun = (run: RunDto) =>
    navigate(`/app/simulations/${run.simulation_id}/runs/${run.id}`);

  const activeColumns: DataTableColumn<RunDto>[] = [
    {
      key: "name",
      header: "Simulation",
      render: (run) => <span className="font-medium">{runName(run)}</span>,
    },
    {
      key: "progress",
      header: "Progress",
      render: (run) => <ActiveRunProgress runId={run.id} />,
    },
    {
      key: "status",
      header: "Status",
      align: "right",
      render: (run) => <StatusBadge status={run.status} />,
    },
  ];

  const resultColumns: DataTableColumn<RunDto>[] = [
    {
      key: "name",
      header: "Simulation",
      render: (run) => <span className="font-medium">{runName(run)}</span>,
    },
    {
      key: "score",
      header: "Score",
      align: "right",
      render: (run) => <RecentResultScore runId={run.id} />,
    },
    {
      key: "finished",
      header: "Completed",
      align: "right",
      render: (run) => (
        <span className="text-muted-foreground">
          {formatRelativeTime(run.finished_at)}
        </span>
      ),
    },
  ];

  const runsFallback = runsData.isError ? (
    <ErrorState
      error={runsData.error}
      title="Could not load runs."
      onRetry={runsData.refetch}
    />
  ) : runsData.isLoading ? (
    <LoadingState label="Loading runs…" />
  ) : null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Overview"
        description="What your agents have been doing."
        actions={
          <Button asChild>
            <Link to="/app/simulations/new">
              <Plus className="size-4" />
              New simulation
            </Link>
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <StatCard
          label="Agents"
          value={agentsQuery.data ? agentsQuery.data.length : "—"}
          to="/app/agents"
        />
        <StatCard label="Simulations" value={simulations.length} to="/app/simulations" />
      </div>

      <section className="space-y-3">
        <SectionHeading>Active simulations</SectionHeading>
        {runsFallback ?? (
          <DataTable
            columns={activeColumns}
            rows={activeRuns}
            rowKey={(run) => run.id}
            onRowClick={goToRun}
            emptyState="No simulations are running right now."
          />
        )}
      </section>

      <section className="space-y-3">
        <SectionHeading>Recent results</SectionHeading>
        {runsFallback ?? (
          <DataTable
            columns={resultColumns}
            rows={recentRuns}
            rowKey={(run) => run.id}
            onRowClick={goToRun}
            emptyState="No completed runs yet."
          />
        )}
      </section>

      <section className="space-y-3">
        <SectionHeading>Recent activity</SectionHeading>
        <ActivityFeed items={activity} />
      </section>
    </div>
  );
}
